"""Generate all three writing templates in parallel, score them, and save the winner."""

from __future__ import annotations

import peachtree_blog._pycache_prefix  # noqa: F401

from peachtree_blog.paths import OUTPUT_DIR, PROJECT_ROOT

import argparse
import concurrent.futures
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from peachtree_blog.draft_scorer import (
    MAX_TOTAL_WITH_BONUS,
    SCORER_MODEL,
    TEMPLATE_IDS,
    run_scoring,
    validation_check_score,
)
from peachtree_blog.pipeline.write_serverless import DEFAULT_SERVERLESS_MODEL, model_label
from peachtree_blog.pipeline_costs import summarize_multi_run_inference_costs
from peachtree_blog.write_common import (
    DEFAULT_AUTHOR_CREDENTIALS,
    DEFAULT_AUTHOR_NAME,
    DEFAULT_INPUT_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_VALIDATION_MAX_ATTEMPTS,
    STYLE_NOTES_PATH,
    build_draft_prompt,
    clear_drafts_directory,
    ensure_draft_subdirs,
    generate_validated_draft,
    load_json,
    read_text,
    save_draft_outputs,
    save_json,
    save_text,
    select_sources_for_draft,
    tag_generation_report,
    write_log_prefix,
)
from peachtree_blog.writing_prompts import (
    WRITING_PROMPT_VARIANTS,
    get_writing_prompt_variant,
    load_writing_prompt_text,
    writing_prompt_metadata,
)

WRITE_RUNNER = "peachtree_blog.pipeline.write_multi"
MULTI_RUN_SUBDIR = "multi_run"


def generate_one_template(
    *,
    template_id: str,
    sources: list[dict[str, Any]],
    selected_sources: list[dict[str, Any]],
    style_notes: str,
    author_name: str,
    author_credentials: str,
    model: str,
    max_attempts: int,
    output_dir: Path,
) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    log = write_log_prefix()
    started_at = time.monotonic()
    prompt_variant = get_writing_prompt_variant(template_id)
    prompt = build_draft_prompt(
        load_writing_prompt_text(prompt_variant),
        selected_sources,
        style_notes,
        author_name,
        author_credentials,
        writing_prompt_id=template_id,
    )
    draft, validation_report, generation_report = generate_validated_draft(
        prompt,
        model,
        allow_serverless_fallback=True,
        max_attempts=max_attempts,
        author_name=author_name,
        author_credentials=author_credentials,
        writing_prompt_id=template_id,
        selected_sources=selected_sources,
    )
    elapsed = round(time.monotonic() - started_at, 2)
    generation_report["template_elapsed_seconds"] = elapsed
    generation_report["writing_prompt_id"] = template_id

    template_dir = output_dir / template_id
    md_dir, _, json_dir = ensure_draft_subdirs(template_dir)
    slug_source = draft.splitlines()[0] if draft else template_id
    run_stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    draft_path = md_dir / f"{run_stamp}-{template_id}.md"
    report_path = json_dir / f"{run_stamp}-{template_id}-validation.json"

    validation_report = dict(validation_report)
    validation_report["generated_at"] = datetime.now().isoformat()
    validation_report["model"] = model
    validation_report["generation"] = generation_report
    validation_report["writing_prompt"] = writing_prompt_metadata(prompt_variant)
    validation_report["draft_path"] = str(draft_path)

    save_text(draft, draft_path, log_prefix=log)
    save_json(validation_report, report_path, log_prefix=log)

    status = "passed" if validation_report.get("passed") else "failed"
    print(
        f"{log} [{template_id}] Validation {status} in {elapsed}s "
        f"({generation_report.get('validation_attempts', 1)} API call(s))"
    )
    return template_id, draft, validation_report, generation_report


def generate_all_templates_parallel(
    *,
    sources: list[dict[str, Any]],
    selected_sources: list[dict[str, Any]],
    style_notes: str,
    author_name: str,
    author_credentials: str,
    model: str,
    max_attempts: int,
    multi_run_dir: Path,
) -> dict[str, tuple[str, dict[str, Any], dict[str, Any]]]:
    log = write_log_prefix()
    results: dict[str, tuple[str, dict[str, Any], dict[str, Any]]] = {}
    errors: dict[str, str] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                generate_one_template,
                template_id=variant.id,
                sources=sources,
                selected_sources=selected_sources,
                style_notes=style_notes,
                author_name=author_name,
                author_credentials=author_credentials,
                model=model,
                max_attempts=max_attempts,
                output_dir=multi_run_dir,
            ): variant.id
            for variant in WRITING_PROMPT_VARIANTS
        }
        for future in concurrent.futures.as_completed(futures):
            template_id = futures[future]
            try:
                resolved_id, draft, validation_report, generation_report = future.result()
                results[resolved_id] = (draft, validation_report, generation_report)
            except Exception as exc:
                errors[template_id] = str(exc)
                print(f"{log} [{template_id}] Generation failed: {exc}")

    if errors:
        print(f"{log} Warning: {len(errors)} template(s) failed to generate.")

    return results


def _pick_best_failed(
    results: dict[str, tuple[str, dict[str, Any], dict[str, Any]]],
) -> str:
    ranked = sorted(
        results.items(),
        key=lambda item: validation_check_score(item[1][1]),
        reverse=True,
    )
    return ranked[0][0]


def _build_multi_run_report(
    *,
    winner_id: str,
    results: dict[str, tuple[str, dict[str, Any], dict[str, Any]]],
    score_data: dict[str, Any],
    scorer_model: str,
    generation_model: str,
) -> dict[str, Any]:
    cost_summary = summarize_multi_run_inference_costs(
        results,
        scorer_estimated_cost_usd=score_data.get("scorer_estimated_cost_usd"),
    )
    return {
        "winner": winner_id,
        "scores": score_data.get("scores") or {},
        "tiebreaker_applied": bool(score_data.get("tiebreaker_applied")),
        "reason": score_data.get("reason") or "",
        "scorer_model": score_data.get("scorer_model") or scorer_model,
        "scorer_usage": score_data.get("scorer_usage"),
        "generation_model": generation_model,
        "all_templates_passed": [
            template_id
            for template_id, (_, validation_report, _) in results.items()
            if validation_report.get("passed")
        ],
        "scoring_skipped": bool(score_data.get("scoring_skipped")),
        **cost_summary,
    }


def _print_score_summary(
    *,
    winner_id: str,
    score_data: dict[str, Any],
    results: dict[str, tuple[str, dict[str, Any], dict[str, Any]]],
) -> None:
    log = write_log_prefix()
    print(f"{log} Winner template: {winner_id}")
    if score_data.get("scoring_skipped"):
        print(f"{log} Scoring skipped (no templates passed validation).")
        return

    scores = score_data.get("scores") or {}
    for template_id in TEMPLATE_IDS:
        entry = scores.get(template_id)
        if not isinstance(entry, dict):
            if template_id in results:
                passed = results[template_id][1].get("passed")
                print(f"{log}  - {template_id}: not scored (validation {'passed' if passed else 'failed'})")
            continue
        marker = " <- winner" if template_id == winner_id else ""
        print(f"{log}  - {template_id}: {entry.get('total', '?')}/{MAX_TOTAL_WITH_BONUS}{marker}")
    if score_data.get("reason"):
        print(f"{log} Scorer reason: {score_data['reason']}")
    if score_data.get("tiebreaker_applied"):
        print(f"{log} Tiebreaker applied (scores were within 2 points).")


def _print_multi_run_cost_summary(multi_run_report: dict[str, Any]) -> None:
    log = write_log_prefix()
    template_costs = multi_run_report.get("template_generation_costs_usd") or {}
    if template_costs:
        parts = [
            f"{template_id} ${float(cost):.4f}"
            for template_id in TEMPLATE_IDS
            if (cost := template_costs.get(template_id)) is not None
        ]
        scorer = multi_run_report.get("scorer_estimated_cost_usd")
        if scorer is not None:
            parts.append(f"scorer ${float(scorer):.4f}")
        print(f"{log} Multi-template write inference: {', '.join(parts)}")
    total = multi_run_report.get("total_inference_cost_usd")
    if total is not None:
        print(f"{log} Total write+scorer inference: ${float(total):.4f} USD")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate geo/scenario/explainer drafts in parallel, score them, and save the winner.",
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model", default=DEFAULT_SERVERLESS_MODEL, help="Together model for draft generation.")
    parser.add_argument("--scorer-model", default=SCORER_MODEL, help="Together model for rubric scoring.")
    parser.add_argument(
        "--source-strategy",
        choices=("auto", "best", "combine"),
        default="auto",
    )
    parser.add_argument("--clear-drafts", action="store_true")
    parser.add_argument("--no-pdf", action="store_true")
    parser.add_argument("--max-validation-attempts", type=int, default=DEFAULT_VALIDATION_MAX_ATTEMPTS)
    parser.add_argument("--no-progress", action="store_true")
    args = parser.parse_args()

    os.environ["WRITE_RUNNER"] = WRITE_RUNNER
    load_dotenv(PROJECT_ROOT / ".env")
    if args.no_progress:
        os.environ["WRITE_NO_PROGRESS"] = "1"

    log = write_log_prefix()
    model_used = args.model
    print(f"{log} Generation model: {model_label(model_used)}")
    print(f"{log} Scorer model: {model_label(args.scorer_model)}")

    sources = load_json(args.input)
    if not sources:
        raise ValueError(f"No kept sources found in {args.input}. Run search.py and evaluate.py first.")

    selected_sources, source_decision = select_sources_for_draft(sources, args.source_strategy)
    print(
        f"{log} Source strategy: {source_decision['mode']} "
        f"({source_decision['selected_source_count']}/{source_decision['available_source_count']} sources)"
    )
    print(f"{log} Source decision: {source_decision['reason']}")

    run_stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    multi_run_dir = OUTPUT_DIR / MULTI_RUN_SUBDIR / run_stamp
    multi_run_dir.mkdir(parents=True, exist_ok=True)
    print(f"{log} Multi-run artifacts: {multi_run_dir}")

    author_name = os.getenv("AUTHOR_NAME", DEFAULT_AUTHOR_NAME)
    author_credentials = os.getenv("AUTHOR_CREDENTIALS", DEFAULT_AUTHOR_CREDENTIALS)
    style_notes = read_text(STYLE_NOTES_PATH)

    pipeline_started_at = time.monotonic()
    results = generate_all_templates_parallel(
        sources=sources,
        selected_sources=selected_sources,
        style_notes=style_notes,
        author_name=author_name,
        author_credentials=author_credentials,
        model=model_used,
        max_attempts=args.max_validation_attempts,
        multi_run_dir=multi_run_dir,
    )
    if not results:
        raise SystemExit("All template generations failed.")

    passed_results = {
        template_id: (draft, validation_report)
        for template_id, (draft, validation_report, _) in results.items()
        if validation_report.get("passed")
    }

    if passed_results:
        score_data = run_scoring(passed_results, model=args.scorer_model)
        winner_id = str(score_data.get("winner") or "")
        if winner_id not in results:
            winner_id = next(iter(passed_results))
            score_data["winner"] = winner_id
    else:
        winner_id = _pick_best_failed(results)
        score_data = {
            "winner": winner_id,
            "scores": {},
            "tiebreaker_applied": False,
            "reason": "No templates passed validation; selected the draft with the most passing checks.",
            "scorer_usage": None,
            "scorer_model": None,
            "scoring_skipped": True,
        }
        print(f"{log} Warning: No templates passed validation; saving best partial draft ({winner_id}).")

    multi_run_report = _build_multi_run_report(
        winner_id=winner_id,
        results=results,
        score_data=score_data,
        scorer_model=args.scorer_model,
        generation_model=model_used,
    )
    score_result_path = multi_run_dir / "score_result.json"
    score_payload = {
        "winner": winner_id,
        "tiebreaker_applied": multi_run_report["tiebreaker_applied"],
        "reason": multi_run_report["reason"],
        "scorer_model": multi_run_report.get("scorer_model"),
        "all_templates_passed": multi_run_report["all_templates_passed"],
        "scores": multi_run_report["scores"],
        "scoring_skipped": multi_run_report["scoring_skipped"],
        "template_generation_costs_usd": multi_run_report.get("template_generation_costs_usd"),
        "multi_run_write_inference_cost_usd": multi_run_report.get("multi_run_write_inference_cost_usd"),
        "scorer_estimated_cost_usd": multi_run_report.get("scorer_estimated_cost_usd"),
        "total_inference_cost_usd": multi_run_report.get("total_inference_cost_usd"),
    }
    save_json(score_payload, score_result_path, log_prefix=log)
    _print_score_summary(winner_id=winner_id, score_data=score_data, results=results)
    _print_multi_run_cost_summary(multi_run_report)

    if args.clear_drafts:
        removed = clear_drafts_directory(args.output_dir)
        if removed:
            print(f"{log} Cleared {len(removed)} file(s) from {args.output_dir}")

    winner_draft, winner_validation, winner_generation = results[winner_id]
    winner_generation = dict(winner_generation)
    winner_generation["multi_run_seconds"] = round(time.monotonic() - pipeline_started_at, 2)
    winner_generation["multi_run_dir"] = str(multi_run_dir)
    tag_generation_report(winner_generation, mode="multi")

    save_draft_outputs(
        draft=winner_draft,
        output_dir=args.output_dir,
        selected_sources=selected_sources,
        sources=sources,
        source_decision=source_decision,
        model_used=model_used,
        generation_report=winner_generation,
        skip_pdf=args.no_pdf,
        writing_prompt_id=winner_id,
        report_extras={"multi_run": multi_run_report},
    )


if __name__ == "__main__":
    main()
