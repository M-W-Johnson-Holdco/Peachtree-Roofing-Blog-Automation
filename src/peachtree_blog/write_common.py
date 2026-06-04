"""Shared blog draft generation helpers for write.py and write_serverless.py."""

from __future__ import annotations

from peachtree_blog.paths import PROJECT_ROOT

import json
import os
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from peachtree_blog.cli_progress import run_with_progress
from peachtree_blog.used_sources import normalize_source_url, record_used_sources, sources_used_payload, used_source_urls
from peachtree_blog.draft_pdf import save_draft_pdf



DEFAULT_INPUT_PATH = PROJECT_ROOT / "output" / "sources" / "kept_sources.json"
PROMPT_PATH = PROJECT_ROOT / "prompts" / "blog.txt"
STYLE_NOTES_PATH = PROJECT_ROOT / "feedback" / "style_notes.txt"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "drafts"
DRAFTS_MD_DIRNAME = "drafts_md"
DRAFTS_PDF_DIRNAME = "drafts_pdf"
DRAFTS_JSON_DIRNAME = "drafts_json"

DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct-Turbo"
SERVERLESS_FALLBACK_MODEL = "Qwen/Qwen2.5-7B-Instruct-Turbo"
DEFAULT_AUTHOR_NAME = "Jonathan Gil"
DEFAULT_AUTHOR_CREDENTIALS = "Licensed Roofing Contractor, Metro Atlanta"

# Together serverless pricing (USD per 1M tokens). Source: docs.together.ai/docs/serverless/models
TOGETHER_MODEL_PRICING_PER_MILLION: dict[str, dict[str, float]] = {
    "meta-llama/Llama-3.3-70B-Instruct-Turbo": {"input": 1.04, "output": 1.04},
    "Qwen/Qwen3.5-397B-A17B": {"input": 0.60, "output": 3.60},
    "Qwen/Qwen3-235B-A22B-Instruct-2507-tput": {"input": 0.20, "output": 0.60},
    "openai/gpt-oss-120b": {"input": 0.15, "output": 0.60},
    "Qwen/Qwen2.5-7B-Instruct-Turbo": {"input": 0.30, "output": 0.30},
    "Qwen/Qwen2.5-72B-Instruct-Turbo": {"input": 0.90, "output": 0.90},
}

METRO_LOCATIONS = [
    "Atlanta",
    "Fulton",
    "DeKalb",
    "Cobb",
    "Gwinnett",
    "Cherokee",
    "Henry",
    "Buckhead",
    "Midtown",
    "Marietta",
    "Alpharetta",
    "Dunwoody",
    "Woodstock",
    "East Cobb",
    "Vinings",
    "Chamblee",
    "Sandy Springs",
    "Roswell",
    "Decatur",
    "Lawrenceville",
    "Smyrna",
]

GENERIC_OPENERS = [
    "In today's world",
    "As a homeowner",
    "When it comes to",
    "Storm season is here",
]

SOURCE_STRATEGIES = ("auto", "best", "combine")
WRITE_RUNNER_ENV = "WRITE_RUNNER"
DEFAULT_WRITE_RUNNER = "write.py"


def write_log_prefix() -> str:
    runner = os.getenv(WRITE_RUNNER_ENV, DEFAULT_WRITE_RUNNER)
    if runner.endswith("write_serverless.py"):
        return "[write_serverless]"
    return "[write]"


def write_runner_name() -> str:
    return os.getenv(WRITE_RUNNER_ENV, DEFAULT_WRITE_RUNNER)


def tag_generation_report(
    generation_report: dict[str, Any],
    *,
    mode: str,
) -> dict[str, Any]:
    generation_report["runner"] = write_runner_name()
    generation_report["mode"] = mode
    return generation_report


def load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}")

    return data


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_feedback_json(path: Path | None) -> str:
    return load_approval_rewrite_context(path)["approval_feedback"]


REVISION_MODE_EDITORIAL = "editorial"
REVISION_MODE_FACTUAL = "factual"
REVISION_MODES = (REVISION_MODE_EDITORIAL, REVISION_MODE_FACTUAL)

FEEDBACK_PREFIX_TO_MODE: dict[str, str] = {
    "edit": REVISION_MODE_EDITORIAL,
    "editorial": REVISION_MODE_EDITORIAL,
    "sources": REVISION_MODE_FACTUAL,
    "stats": REVISION_MODE_FACTUAL,
    "factual": REVISION_MODE_FACTUAL,
}

FACTUAL_FEEDBACK_PATTERNS = (
    r"\bstat(?:istic)?s?\b",
    r"\bcitations?\b",
    r"\bcite\b",
    r"\bcited\b",
    r"\bsources?\b",
    r"\barticles?\b",
    r"\bpercent(?:age)?\b",
    r"\bfigures?\b",
    r"\bnumbers?\b",
    r"\bdata\b",
    r"\bclaims?\b",
    r"\bfacts?\b",
    r"\bfrom the (?:story|article|source|report)\b",
    r"\badd(?:ing)? (?:a |another )?(?:stat|figure|number|citation)\b",
    r"\$\d",
    r"\b\d+\s*(?:%|percent)\b",
)

EDITORIAL_FEEDBACK_PATTERNS = (
    r"\btone\b",
    r"\bwordy\b",
    r"\bshorter\b",
    r"\blonger\b",
    r"\bconcise\b",
    r"\bopening\b",
    r"\bintro(?:duction)?\b",
    r"\bparagraph\b",
    r"\bheadings?\b",
    r"\bh2\b",
    r"\bfaq\b",
    r"\bsalesy\b",
    r"\bpromotional\b",
    r"\brephrase\b",
    r"\breword\b",
    r"\bwording\b",
    r"\bless repetitive\b",
    r"\brepetitive\b",
    r"\bgeneric\b",
    r"\bbyline\b",
    r"\bcta\b",
    r"\bvalidation\b",
)


def parse_feedback_prefix(text: str) -> tuple[str, str | None]:
    """Return cleaned feedback text and optional explicit revision mode from a prefix."""
    match = re.match(
        r"^(edit|editorial|sources|stats|factual)\s*:\s*(.*)$",
        text.strip(),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return text.strip(), None
    mode = FEEDBACK_PREFIX_TO_MODE[match.group(1).lower()]
    cleaned = match.group(2).strip()
    return cleaned or text.strip(), mode


def classify_revision_mode(feedback_texts: list[str]) -> tuple[str, str]:
    """Pick editorial vs factual revision mode from Slack feedback."""
    explicit_modes: list[str] = []
    cleaned_texts: list[str] = []
    for text in feedback_texts:
        cleaned, explicit_mode = parse_feedback_prefix(text)
        if cleaned:
            cleaned_texts.append(cleaned)
        if explicit_mode:
            explicit_modes.append(explicit_mode)

    if REVISION_MODE_FACTUAL in explicit_modes:
        return REVISION_MODE_FACTUAL, "explicit prefix (sources/stats/factual)"
    if explicit_modes:
        return REVISION_MODE_EDITORIAL, "explicit prefix (edit/editorial)"

    combined = "\n".join(cleaned_texts).lower()
    if not combined.strip():
        return REVISION_MODE_EDITORIAL, "default"

    factual_score = sum(1 for pattern in FACTUAL_FEEDBACK_PATTERNS if re.search(pattern, combined))
    editorial_score = sum(1 for pattern in EDITORIAL_FEEDBACK_PATTERNS if re.search(pattern, combined))

    if factual_score > editorial_score and factual_score > 0:
        return REVISION_MODE_FACTUAL, f"keyword match (factual={factual_score}, editorial={editorial_score})"
    if editorial_score > 0:
        return REVISION_MODE_EDITORIAL, f"keyword match (factual={factual_score}, editorial={editorial_score})"
    return REVISION_MODE_EDITORIAL, "default"


def feedback_items_to_texts(feedback: Any) -> list[str]:
    texts: list[str] = []
    if not isinstance(feedback, list):
        return texts
    for item in feedback:
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
        else:
            text = str(item).strip()
        if text:
            texts.append(text)
    return texts


def format_approval_feedback_lines(feedback_texts: list[str]) -> str:
    lines: list[str] = []
    for index, text in enumerate(feedback_texts, start=1):
        cleaned, _ = parse_feedback_prefix(text)
        if cleaned:
            lines.append(f"{index}. {cleaned}")
    return "\n".join(lines)


def classify_revision_mode_from_record(record: dict[str, Any]) -> tuple[str, str]:
    return classify_revision_mode(feedback_items_to_texts(record.get("feedback", [])))


def update_record_revision_mode(record: dict[str, Any]) -> tuple[str, str]:
    mode, reason = classify_revision_mode_from_record(record)
    record["revision_mode"] = mode
    record["revision_mode_reason"] = reason
    return mode, reason


def load_approval_rewrite_context(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "approval_feedback": "",
            "previous_draft": "",
            "replace_draft_path": None,
            "revision_mode": "",
            "revision_mode_reason": "",
        }
    if not path.exists():
        raise FileNotFoundError(f"Feedback JSON not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    feedback_texts = feedback_items_to_texts(data.get("feedback", []))
    approval_feedback = format_approval_feedback_lines(feedback_texts)
    revision_mode, revision_mode_reason = classify_revision_mode(feedback_texts)

    replace_draft_path = resolve_replace_draft_path(data)
    previous_draft = ""
    if replace_draft_path and replace_draft_path.is_file():
        previous_draft = replace_draft_path.read_text(encoding="utf-8")
    elif replace_draft_path:
        print(
            f"{write_log_prefix()} Warning: Previous draft not found at {replace_draft_path}. "
            "Rewrite will use Slack feedback only."
        )

    return {
        "approval_feedback": approval_feedback,
        "previous_draft": previous_draft,
        "replace_draft_path": replace_draft_path,
        "revision_mode": revision_mode if approval_feedback else "",
        "revision_mode_reason": revision_mode_reason if approval_feedback else "",
    }


def resolve_replace_draft_path(record: dict[str, Any]) -> Path | None:
    """Return the draft file that a rewrite should replace, if known."""
    for key in ("revision_draft_path", "draft_path"):
        draft_rel = str(record.get(key, "")).strip()
        if not draft_rel:
            continue
        draft_path = Path(draft_rel)
        if not draft_path.is_absolute():
            draft_path = PROJECT_ROOT / draft_path
        if draft_path.is_file():
            return draft_path
    return None


def persist_revision_mode_to_approval_json(path: Path, mode: str, reason: str) -> None:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data["revision_mode"] = mode
    data["revision_mode_reason"] = reason
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def source_display_name(source: dict[str, Any]) -> str:
    domain = source.get("domain") or ""
    if "fox5atlanta" in domain:
        return "FOX 5 Atlanta"
    if "11alive" in domain:
        return "11Alive"
    if "wsbtv" in domain:
        return "WSB-TV"
    if "ajc" in domain:
        return "AJC"
    if "weather.gov" in domain:
        return "NWS Atlanta"
    if "legis.ga.gov" in domain:
        return "Georgia General Assembly"
    return domain or "Source"


def format_sources_block(evaluated_sources: list[dict[str, Any]]) -> str:
    blocks = []

    for index, item in enumerate(evaluated_sources, start=1):
        source = item.get("source", item)
        content = str(source.get("content", "")).strip()
        excerpt = re.sub(r"\s+", " ", content)[:1800]
        title = source.get("title") or item.get("title", "")
        published_date = source.get("published_date", "")
        outlet = source_display_name(source)

        blocks.append(
            "\n".join(
                [
                    f"Source {index}: {title}",
                    f"Outlet: {outlet}",
                    f"URL: {source.get('url', item.get('url', ''))}",
                    f"Published: {published_date}",
                    f"Strategy cluster: {item.get('strategy_cluster', source.get('strategy_cluster', ''))}",
                    f"Pillar topic: {item.get('pillar_topic', source.get('pillar_topic', ''))}",
                    f"Recommended angle: {item.get('recommended_angle', '')}",
                    f"Evaluation reason: {item.get('reason', '')}",
                    f"Excerpt: {excerpt}",
                ]
            )
        )

    return "\n\n---\n\n".join(blocks)


def source_sort_key(item: dict[str, Any]) -> tuple[float, int, int, int, int]:
    scores = item.get("scores") if isinstance(item.get("scores"), dict) else {}
    return (
        float(item.get("weighted_score") or 0),
        int(scores.get("roofing_relevance") or 0),
        int(scores.get("actionability") or 0),
        int(scores.get("source_authority") or 0),
        int(scores.get("local_relevance") or 0),
    )


def source_title(item: dict[str, Any]) -> str:
    return str(item.get("title") or item.get("source", {}).get("title") or "Untitled source")


def select_sources_for_draft(
    sources: list[dict[str, Any]],
    strategy: str = "auto",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pick whether to combine sources or focus one draft on the best source."""
    if strategy not in SOURCE_STRATEGIES:
        raise ValueError(f"Unknown source strategy: {strategy}")
    if not sources:
        return [], {
            "strategy": strategy,
            "mode": "none",
            "reason": "No kept sources were provided.",
            "available_source_count": 0,
            "selected_source_count": 0,
            "selected_titles": [],
        }

    ranked = sorted(sources, key=source_sort_key, reverse=True)
    best = ranked[0]

    if strategy == "best":
        selected = [best]
        mode = "best"
        reason = "Forced best-source mode selected the strongest evaluated source."
    elif strategy == "combine":
        selected = ranked
        mode = "combine"
        reason = "Forced combine mode included all kept sources in one draft."
    elif len(ranked) == 1:
        selected = [best]
        mode = "best"
        reason = "Only one kept source was available."
    else:
        best_cluster = best.get("strategy_cluster")
        same_cluster = [source for source in ranked if source.get("strategy_cluster") == best_cluster]
        second = ranked[1]
        score_gap = float(best.get("weighted_score") or 0) - float(second.get("weighted_score") or 0)

        if len(same_cluster) >= 2 and score_gap <= 1.5:
            selected = same_cluster
            mode = "combine"
            reason = (
                "Auto mode combined sources because multiple strong candidates share "
                f"the {best_cluster} strategy cluster."
            )
        else:
            selected = [best]
            mode = "best"
            reason = (
                "Auto mode selected one source because the kept sources point to "
                "different blog angles or strategy clusters."
            )

    decision = {
        "strategy": strategy,
        "mode": mode,
        "reason": reason,
        "available_source_count": len(sources),
        "selected_source_count": len(selected),
        "selected_titles": [source_title(source) for source in selected],
        "available_titles": [source_title(source) for source in ranked],
    }
    return selected, decision


def validation_checklist_block(author_name: str, author_credentials: str) -> str:
    return (
        "- One H1 title at the top.\n"
        "- Opening paragraph before the Quick Answer block is 50-120 words, answer-first, news-anchored.\n"
        "- Quick Answer block after opening with **The short answer:**, **Who this affects:**, **What to do:**, **Timeline:**.\n"
        "- Every ## heading is a question ending with ?, except the exact heading `## FAQ`.\n"
        "- At least one markdown comparison table.\n"
        "- Exactly 3-5 inline citations formatted `(Source: Outlet Name, Month Year)`.\n"
        "- At least 6 named Metro Atlanta locations woven into the prose.\n"
        "- Exactly 8 FAQ questions as ### H3 headings under `## FAQ` (answers 3-5 sentences each).\n"
        f'- Exact author byline: "Written by {author_name}, {author_credentials}. Peachtree Roofing & Exteriors serves homeowners across Metro Atlanta."\n'
        '- Exact CTA: "Contact Peachtree Roofing & Exteriors for a free inspection."\n'
        "- No generic openers such as In today's world, As a homeowner, When it comes to, or Storm season is here."
    )


def build_first_draft_prompt(
    prompt_template: str,
    sources: list[dict[str, Any]],
    style_notes: str,
    author_name: str,
    author_credentials: str,
    approval_feedback: str = "",
) -> str:
    sources_block = format_sources_block(sources)
    feedback_parts = [style_notes.strip()]
    if approval_feedback.strip():
        feedback_parts.append("Slack approval feedback:\n" + approval_feedback.strip())
    style_block = "\n\n".join(part for part in feedback_parts if part) or "No editor feedback recorded yet."

    base_prompt = prompt_template.format(
        sources_block=sources_block,
        today=date.today().isoformat(),
        author_name=author_name,
        author_credentials=author_credentials,
    )

    checklist = validation_checklist_block(author_name, author_credentials)
    indented_checklist = "\n".join(f"  {line}" for line in checklist.splitlines())
    return (
        f"{base_prompt}\n\n---\n\n"
        "RECENT EDITOR FEEDBACK TO APPLY:\n"
        f"{style_block}\n\n"
        "---\n\n"
        "IMPORTANT SOURCE USE RULES:\n"
        "- Do not invent facts, statistics, dates, credentials, review counts, project counts, or license numbers.\n"
        "- Use exactly 3 to 5 cited statistics from the provided sources.\n"
        "- Keep all headings and FAQ questions in question format.\n"
        "- Use the exact FAQ format: ## FAQ, then exactly eight H3 question headings and 3-5 sentence answers.\n"
        "- After the opening paragraph, include the Quick Answer block with all four labeled lines.\n"
        "- Do not format the author byline as a heading.\n"
        "- Pass every automated validation check:\n"
        f"{indented_checklist}\n"
    )


def build_editorial_revision_prompt(
    *,
    style_notes: str,
    author_name: str,
    author_credentials: str,
    approval_feedback: str,
    previous_draft: str,
) -> str:
    checklist = validation_checklist_block(author_name, author_credentials)
    style_block = style_notes.strip() or "No standing style notes recorded yet."
    return (
        "You are revising an existing Peachtree Roofing & Exteriors blog draft for Metro Atlanta homeowners.\n\n"
        f"AUTHOR: {author_name}, {author_credentials}\n"
        f"TODAY'S DATE: {date.today().isoformat()}\n\n"
        "REVISION TYPE: EDITORIAL — fix wording, structure, tone, and validation issues only.\n\n"
        "EDITOR FEEDBACK (apply every item):\n"
        f"{approval_feedback.strip()}\n\n"
        "STANDING STYLE NOTES:\n"
        f"{style_block}\n\n"
        "GROUNDING RULES:\n"
        "- Do not invent new statistics, dates, credentials, or citations.\n"
        "- Keep existing facts and citations unless feedback explicitly asks to change them.\n"
        "- Preserve sections that already satisfy the feedback; change only what is needed.\n\n"
        "VALIDATION CHECKLIST (every item is required):\n"
        f"{checklist}\n\n"
        "Return the complete revised Markdown draft only. No preamble or meta-commentary.\n\n"
        "PREVIOUS DRAFT TO REVISE:\n"
        f"```\n{previous_draft.strip()}\n```\n"
    )


def build_factual_revision_prompt(
    sources: list[dict[str, Any]],
    style_notes: str,
    author_name: str,
    author_credentials: str,
    approval_feedback: str,
    previous_draft: str,
) -> str:
    sources_block = format_sources_block(sources)
    checklist = validation_checklist_block(author_name, author_credentials)
    style_block = style_notes.strip() or "No standing style notes recorded yet."
    return (
        "You are revising an existing Peachtree Roofing & Exteriors blog draft using source material.\n\n"
        f"AUTHOR: {author_name}, {author_credentials}\n"
        f"TODAY'S DATE: {date.today().isoformat()}\n\n"
        "REVISION TYPE: FACTUAL — update statistics, citations, and claims using the sources below.\n\n"
        "EDITOR FEEDBACK (apply every item):\n"
        f"{approval_feedback.strip()}\n\n"
        "STANDING STYLE NOTES:\n"
        f"{style_block}\n\n"
        "SOURCES TO DRAW FROM:\n"
        f"{sources_block}\n\n"
        "SOURCE USE RULES:\n"
        "- Update statistics and citations only where feedback requests it.\n"
        "- Do not invent facts, statistics, dates, credentials, or license numbers.\n"
        "- Use 3 to 5 cited statistics total, formatted `(Source: Outlet Name, Month Year)`.\n"
        "- Keep unchanged sections verbatim where possible; do not rewrite unrelated prose.\n\n"
        "VALIDATION CHECKLIST (every item is required):\n"
        f"{checklist}\n\n"
        "Return the complete revised Markdown draft only. No preamble or meta-commentary.\n\n"
        "PREVIOUS DRAFT TO REVISE:\n"
        f"```\n{previous_draft.strip()}\n```\n"
    )


def build_draft_prompt(
    prompt_template: str,
    sources: list[dict[str, Any]],
    style_notes: str,
    author_name: str,
    author_credentials: str,
    approval_feedback: str = "",
    previous_draft: str = "",
    revision_mode: str | None = None,
) -> str:
    is_rewrite = bool(previous_draft.strip() and approval_feedback.strip())
    if not is_rewrite:
        return build_first_draft_prompt(
            prompt_template,
            sources,
            style_notes,
            author_name,
            author_credentials,
            approval_feedback,
        )

    mode = revision_mode or REVISION_MODE_EDITORIAL
    if mode == REVISION_MODE_FACTUAL:
        return build_factual_revision_prompt(
            sources,
            style_notes,
            author_name,
            author_credentials,
            approval_feedback,
            previous_draft,
        )
    return build_editorial_revision_prompt(
        style_notes=style_notes,
        author_name=author_name,
        author_credentials=author_credentials,
        approval_feedback=approval_feedback,
        previous_draft=previous_draft,
    )


def build_prompt(
    prompt_template: str,
    sources: list[dict[str, Any]],
    style_notes: str,
    author_name: str,
    author_credentials: str,
    approval_feedback: str = "",
    previous_draft: str = "",
    revision_mode: str | None = None,
) -> str:
    return build_draft_prompt(
        prompt_template,
        sources,
        style_notes,
        author_name,
        author_credentials,
        approval_feedback,
        previous_draft,
        revision_mode,
    )


def get_together_client():
    try:
        from together import Together
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: together. Install dependencies with "
            "`python -m pip install -r requirements.txt`."
        ) from exc

    api_key = os.getenv("TOGETHER_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "TOGETHER_API_KEY is not set. Add it to .env, or run `python write.py --mock`."
        )

    return Together(api_key=api_key)


def extract_usage(response) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": 0,
        }

    return {
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        "cached_tokens": int(getattr(usage, "cached_tokens", 0) or 0),
    }


def estimate_token_cost_usd(model: str, usage: dict[str, int]) -> dict[str, Any]:
    pricing = TOGETHER_MODEL_PRICING_PER_MILLION.get(model)
    if not pricing:
        return {
            "total": None,
            "input": None,
            "output": None,
            "currency": "USD",
            "pricing_per_million_tokens": None,
            "pricing_source": "unavailable",
            "note": "No catalog pricing for this model. Dedicated endpoints may bill per minute separately.",
        }

    input_tokens = max(0, usage["prompt_tokens"] - usage["cached_tokens"])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    cached_cost = (usage["cached_tokens"] / 1_000_000) * pricing.get("cached_input", pricing["input"])
    output_cost = (usage["completion_tokens"] / 1_000_000) * pricing["output"]
    total = input_cost + cached_cost + output_cost

    return {
        "total": round(total, 6),
        "input": round(input_cost + cached_cost, 6),
        "output": round(output_cost, 6),
        "currency": "USD",
        "pricing_per_million_tokens": pricing,
        "pricing_source": "together_catalog",
    }


def build_generation_report(
    *,
    model_requested: str,
    model_used: str,
    model_returned_by_api: str | None,
    elapsed_seconds: float,
    usage: dict[str, int] | None,
    endpoint_session_seconds: float | None = None,
    endpoint_management_used: bool = False,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "model_requested": model_requested,
        "model_used": model_used,
        "model_returned_by_api": model_returned_by_api,
        "elapsed_seconds": round(elapsed_seconds, 2),
        "endpoint_management_used": endpoint_management_used,
    }

    if usage is not None:
        report["usage"] = usage
        report["estimated_cost_usd"] = {
            "tokens": estimate_token_cost_usd(model_used, usage),
        }
    else:
        report["usage"] = None
        report["estimated_cost_usd"] = None

    if endpoint_management_used and endpoint_session_seconds is not None:
        report["endpoint_session_seconds"] = round(endpoint_session_seconds, 2)
        per_minute = os.getenv("TOGETHER_ENDPOINT_COST_PER_MINUTE", "").strip()
        if per_minute:
            endpoint_cost = (endpoint_session_seconds / 60.0) * float(per_minute)
            report.setdefault("estimated_cost_usd", {})["endpoint"] = {
                "total": round(endpoint_cost, 4),
                "currency": "USD",
                "cost_per_minute": float(per_minute),
                "pricing_source": "env:TOGETHER_ENDPOINT_COST_PER_MINUTE",
                "note": "Endpoint uptime cost is separate from token usage.",
            }
            if report["estimated_cost_usd"].get("tokens", {}).get("total") is not None:
                report["estimated_cost_usd"]["combined_total"] = round(
                    report["estimated_cost_usd"]["tokens"]["total"] + endpoint_cost,
                    4,
                )

    return report


def generate_with_together(
    prompt: str,
    model: str,
    *,
    allow_serverless_fallback: bool = True,
) -> tuple[str, dict[str, Any]]:
    client = get_together_client()
    messages = [
        {
            "role": "system",
            "content": (
                "You are a senior home-services content strategist. "
                "Return only the complete Markdown blog draft."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    def call_model(active_model: str):
        return client.chat.completions.create(
            model=active_model,
            messages=messages,
            temperature=0.35,
            max_tokens=3400,
        )

    estimated_seconds = float(os.getenv("WRITE_GENERATION_ESTIMATE_SECONDS", "180"))
    started_at = time.monotonic()
    model_requested = model
    model_used = model

    try:
        response = run_with_progress(
            f"{write_log_prefix()} Generating draft",
            lambda: call_model(model),
            estimated_seconds=estimated_seconds,
        )
    except Exception as exc:
        if (
            "model_not_available" not in str(exc)
            or model == SERVERLESS_FALLBACK_MODEL
            or not allow_serverless_fallback
        ):
            raise

        print(
            f"{write_log_prefix()} Model unavailable on Together serverless. "
            f"Retrying with {SERVERLESS_FALLBACK_MODEL}."
        )
        model_used = SERVERLESS_FALLBACK_MODEL
        response = run_with_progress(
            f"{write_log_prefix()} Generating draft ({SERVERLESS_FALLBACK_MODEL})",
            lambda: call_model(SERVERLESS_FALLBACK_MODEL),
            estimated_seconds=estimated_seconds,
        )

    elapsed_seconds = time.monotonic() - started_at
    usage = extract_usage(response)
    metadata = build_generation_report(
        model_requested=model_requested,
        model_used=model_used,
        model_returned_by_api=getattr(response, "model", None),
        elapsed_seconds=elapsed_seconds,
        usage=usage,
    )

    return response.choices[0].message.content.strip(), metadata


def generate_mock_draft(sources: list[dict[str, Any]], author_name: str, author_credentials: str) -> str:
    primary = sources[0] if sources else {}
    angle = primary.get("recommended_angle") or "What should Metro Atlanta homeowners check before roof repairs?"
    title = angle.rstrip("?")

    return f"""# {title}

Metro Atlanta homeowners should treat recent roof-safety and insurance news as a reminder to inspect vulnerable roof areas before small issues become expensive claims. Start with visible damage, roof penetrations, attic moisture, and policy details. If you see active leaks, displaced flashing, storm damage, or unsafe exterior conditions, document the issue with photos and schedule a licensed inspection before authorizing repairs.

## What changed in Atlanta roofing and home insurance news?

Recent local reporting points to two practical concerns: building safety and rising home insurance costs. FOX 5 Atlanta reported an unsafe Midtown Atlanta high-rise inspection (Source: FOX 5 Atlanta, May 2026). 11Alive shared Consumer Reports guidance that older roofs and storm damage can affect insurance costs (Source: 11Alive, May 2026). Consumer Reports also found home insurance costs rose an average of 24% over three years (Source: Consumer Reports, May 2026).

## What should homeowners inspect first?

Start with the roof areas most likely to leak: pipe boots, chimney flashing, valleys, skylights, gutters, and attic decking. Homeowners in Fulton, DeKalb, Cobb, Gwinnett, Cherokee, and Chamblee should also check for storm debris, soft decking, and ceiling stains after heavy rain.

| Area to check | What to look for | Why it matters |
|---|---|---|
| Pipe boots | Cracked rubber or lifted sealant | Common leak entry point |
| Flashing | Gaps, rust, or displaced metal | Lets wind-driven rain enter |
| Attic decking | Dark stains or soft wood | Shows hidden moisture |

## How can roof condition affect insurance costs?

Roof age and storm-damage history can affect premiums and claim outcomes. Some insurers add surcharges of 10 to 20 percent or more for older roofs (Source: 11Alive, May 2026).

## FAQ

### Should I inspect my roof after a storm in Atlanta?
Yes. Check visible roof surfaces, gutters, attic decking, and ceiling stains within 48 to 72 hours.

### Can an older roof raise home insurance costs?
Yes. Some insurers apply surcharges when roof age increases claim risk.

### What should I photograph before filing a claim?
Photograph exterior damage, interior stains, attic moisture, and any fallen limbs or debris.

### Do I need a roofer before calling insurance?
You can call insurance first, but a written inspection helps you understand the damage before an adjuster visit.

### Which Metro Atlanta areas see storm-related roof issues?
Fulton, DeKalb, Cobb, Gwinnett, Cherokee, Sandy Springs, Decatur, and Marietta all see wind and rain exposure.

### What roof areas leak most often?
Pipe boots, flashing, valleys, skylights, and poorly draining gutters are common leak points.

### Should I replace my roof just because it is old?
Not always. If the damage is isolated and decking is sound, repair may be enough.

### When should I call Peachtree Roofing & Exteriors?
Call when you see leaks, storm damage, missing shingles, soft decking, or insurance questions tied to roof condition.

Written by {author_name}, {author_credentials}. Peachtree Roofing & Exteriors serves homeowners across Metro Atlanta.

Contact Peachtree Roofing & Exteriors for a free inspection.
"""


def draft_subdirs(output_dir: Path = DEFAULT_OUTPUT_DIR) -> tuple[Path, Path, Path]:
    """Return Markdown, PDF, and validation JSON directories under the drafts root."""
    return (
        output_dir / DRAFTS_MD_DIRNAME,
        output_dir / DRAFTS_PDF_DIRNAME,
        output_dir / DRAFTS_JSON_DIRNAME,
    )


def ensure_draft_subdirs(output_dir: Path = DEFAULT_OUTPUT_DIR) -> tuple[Path, Path, Path]:
    md_dir, pdf_dir, json_dir = draft_subdirs(output_dir)
    for directory in (md_dir, pdf_dir, json_dir):
        directory.mkdir(parents=True, exist_ok=True)
    return md_dir, pdf_dir, json_dir


def resolve_drafts_root(path: Path) -> Path:
    if path.parent.name in {DRAFTS_MD_DIRNAME, DRAFTS_PDF_DIRNAME, DRAFTS_JSON_DIRNAME}:
        return path.parent.parent
    if path.parent.name == "drafts" or path.parent == DEFAULT_OUTPUT_DIR:
        return path.parent
    return DEFAULT_OUTPUT_DIR


def draft_stem_from_path(draft_path: Path) -> str:
    name = draft_path.name
    if name.endswith("-validation.json"):
        return name[: -len("-validation.json")]
    return draft_path.stem


def draft_pdf_path(markdown_path: Path) -> Path:
    stem = draft_stem_from_path(markdown_path)
    _, pdf_dir, _ = draft_subdirs(resolve_drafts_root(markdown_path))
    return pdf_dir / f"{stem}.pdf"


def draft_validation_json_path(draft_path: Path) -> Path:
    stem = draft_stem_from_path(draft_path)
    _, _, json_dir = draft_subdirs(resolve_drafts_root(draft_path))
    return json_dir / f"{stem}-validation.json"


def markdown_draft_paths(output_dir: Path = DEFAULT_OUTPUT_DIR) -> list[Path]:
    """List Markdown drafts in the typed subdir, with legacy flat-directory fallback."""
    md_dir, _, _ = draft_subdirs(output_dir)
    drafts = sorted(md_dir.glob("*.md")) if md_dir.exists() else []
    if drafts:
        return drafts
    return sorted(
        path
        for path in output_dir.glob("*.md")
        if path.is_file() and not path.name.endswith("-validation.md")
    )


def latest_markdown_draft(output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    drafts = markdown_draft_paths(output_dir)
    if not drafts:
        raise FileNotFoundError(f"No Markdown drafts found under {output_dir}")

    for draft_path in reversed(drafts):
        if draft_pdf_path(draft_path).is_file():
            return draft_path

    latest = drafts[-1]
    expected_pdf = draft_pdf_path(latest)
    raise FileNotFoundError(
        f"No PDF found for the latest draft under {output_dir}. "
        f"Expected {expected_pdf}. Run write.py or write_serverless.py first."
    )


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "blog-draft"


def first_heading(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "blog-draft"


def output_paths(markdown: str, output_dir: Path) -> tuple[Path, Path, Path]:
    md_dir, pdf_dir, json_dir = ensure_draft_subdirs(output_dir)
    run_stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    slug = slugify(first_heading(markdown))
    base = f"{run_stamp}-{slug}"
    return (
        md_dir / f"{base}.md",
        pdf_dir / f"{base}.pdf",
        json_dir / f"{base}-validation.json",
    )


def count_faq_pairs(markdown: str) -> int:
    faq_match = re.search(r"(^##+ FAQ\b.*)", markdown, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
    if not faq_match:
        return 0
    faq_section = faq_match.group(1)
    return len(re.findall(r"^#{3,6}\s+\S.*\?", faq_section, flags=re.MULTILINE))


def extract_opening_paragraph(markdown: str) -> str:
    """First paragraph only — excludes Quick Answer block and body H2s."""
    body_without_title = re.sub(r"^# .+\n+", "", markdown).strip()
    before_first_h2 = re.split(r"\n^##\s+", body_without_title, maxsplit=1, flags=re.MULTILINE)[0]
    if "**The short answer:**" in before_first_h2:
        return before_first_h2.split("**The short answer:**", maxsplit=1)[0].strip()
    return before_first_h2.split("\n\n", maxsplit=1)[0].strip()


def has_quick_answer_block(markdown: str) -> bool:
    labels = (
        r"\*\*The short answer:\*\*",
        r"\*\*Who this affects:\*\*",
        r"\*\*What to do:\*\*",
        r"\*\*Timeline:\*\*",
    )
    return all(re.search(label, markdown, flags=re.IGNORECASE) for label in labels)


def validate_draft(markdown: str) -> dict[str, Any]:
    h2s = re.findall(r"^##\s+(.+)$", markdown, flags=re.MULTILINE)
    citations = re.findall(r"\(Source:\s*[^)]+\)", markdown)
    tables = bool(re.search(r"^\|.+\|\s*$", markdown, flags=re.MULTILINE))
    locations = sorted({loc for loc in METRO_LOCATIONS if re.search(rf"\b{re.escape(loc)}\b", markdown)})
    opening_text = extract_opening_paragraph(markdown)
    opening_words = len(opening_text.split())
    generic_openers = [phrase for phrase in GENERIC_OPENERS if phrase.lower() in markdown[:250].lower()]

    checks = {
        "has_h1": bool(re.search(r"^#\s+\S", markdown, flags=re.MULTILINE)),
        "answer_first_opening_roughly_50_to_120_words": 50 <= opening_words <= 120,
        "has_quick_answer_block": has_quick_answer_block(markdown),
        "all_h2_headings_are_questions": bool(h2s) and all(h2.strip().endswith("?") or h2.strip().lower() == "faq" for h2 in h2s),
        "has_comparison_table": tables,
        "citation_count_3_to_5": 3 <= len(citations) <= 5,
        "location_count_at_least_6": len(locations) >= 6,
        "faq_exactly_8": count_faq_pairs(markdown) == 8,
        "has_author_byline": "Written by " in markdown and "Peachtree Roofing & Exteriors serves homeowners across Metro Atlanta." in markdown,
        "has_final_cta": "Contact Peachtree Roofing & Exteriors for a free inspection." in markdown,
        "no_generic_openers": not generic_openers,
    }

    return {
        "passed": all(checks.values()),
        "checks": checks,
        "h2_headings": h2s,
        "citation_count": len(citations),
        "opening_word_count": opening_words,
        "locations_found": locations,
        "faq_count": count_faq_pairs(markdown),
        "generic_openers_found": generic_openers,
    }


DEFAULT_VALIDATION_MAX_ATTEMPTS = 3

VALIDATION_CHECK_HINTS: dict[str, str] = {
    "has_h1": "Start with one H1 title line: `# Your Title Here`.",
    "answer_first_opening_roughly_50_to_120_words": (
        "The opening paragraph before the Quick Answer block must be 50-120 words, news-anchored, answer-first."
    ),
    "has_quick_answer_block": (
        "Immediately after the opening paragraph, include **The short answer:**, **Who this affects:**, "
        "**What to do:**, and **Timeline:** on separate lines."
    ),
    "all_h2_headings_are_questions": (
        "Every ## H2 heading must be a question ending with ?, except the exact heading `## FAQ`."
    ),
    "has_comparison_table": "Include at least one markdown comparison table using | pipe | syntax.",
    "citation_count_3_to_5": (
        "Include exactly 3-5 inline citations formatted `(Source: Outlet Name, Month Year)`."
    ),
    "location_count_at_least_6": (
        "Name at least 6 Metro Atlanta locations naturally in the prose, such as Atlanta, Cobb, Marietta, Decatur, Sandy Springs, and Gwinnett."
    ),
    "faq_exactly_8": (
        "Under the exact heading `## FAQ`, include exactly 8 H3 question headings ending with ? and 3-5 sentence answers."
    ),
    "has_final_cta": (
        'End with this exact sentence: "Contact Peachtree Roofing & Exteriors for a free inspection."'
    ),
    "no_generic_openers": (
        "Do not use generic openers such as In today's world, As a homeowner, When it comes to, or Storm season is here in the first paragraph."
    ),
}


def format_failed_validation_feedback(
    report: dict[str, Any],
    *,
    author_name: str,
    author_credentials: str,
) -> str:
    failed = [name for name, passed in report["checks"].items() if not passed]
    lines = [
        "The previous draft failed automated validation. Return the complete revised Markdown draft only.",
        "",
        "Fix every failed check below:",
    ]

    for name in failed:
        if name == "has_author_byline":
            hint = (
                f'Include this exact sentence as normal paragraph text, not as a heading: '
                f'"Written by {author_name}, {author_credentials}. Peachtree Roofing & Exteriors serves homeowners across Metro Atlanta."'
            )
        else:
            hint = VALIDATION_CHECK_HINTS.get(name, name.replace("_", " "))
        lines.append(f"- {hint}")

    if report.get("generic_openers_found"):
        lines.append(f"- Remove these generic openers: {', '.join(report['generic_openers_found'])}")
    if report.get("citation_count") is not None and not report["checks"].get("citation_count_3_to_5"):
        lines.append(f"- Current citation count: {report['citation_count']} (need 3-5).")
    if report.get("opening_word_count") is not None and not report["checks"].get(
        "answer_first_opening_roughly_50_to_120_words"
    ):
        lines.append(f"- Current opening word count: {report['opening_word_count']} (need 50-120).")
    if report.get("faq_count") is not None and not report["checks"].get("faq_exactly_8"):
        lines.append(f"- Current FAQ question count: {report['faq_count']} (need exactly 8).")
    if report.get("locations_found") is not None and not report["checks"].get("location_count_at_least_6"):
        found = ", ".join(report["locations_found"]) or "none"
        lines.append(f"- Current named locations: {len(report['locations_found'])} ({found}). Need at least 6.")
    non_question_h2s = [
        heading
        for heading in report.get("h2_headings", [])
        if not heading.strip().endswith("?") and heading.strip().lower() != "faq"
    ]
    if non_question_h2s:
        lines.append(f"- These H2 headings are not questions: {', '.join(non_question_h2s)}")

    return "\n".join(lines)


def merge_generation_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not reports:
        return {}
    if len(reports) == 1:
        return dict(reports[0])

    merged = dict(reports[-1])
    merged["validation_attempt"] = len(reports)
    merged["elapsed_seconds"] = round(
        sum(float(report.get("elapsed_seconds") or 0) for report in reports),
        2,
    )

    total_usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
    }
    for report in reports:
        usage = report.get("usage") or {}
        for key in total_usage:
            total_usage[key] += int(usage.get(key) or 0)

    merged["usage"] = total_usage
    model_used = str(merged.get("model_used") or "")
    if model_used:
        merged["estimated_cost_usd"] = {
            "tokens": estimate_token_cost_usd(model_used, total_usage),
        }

    return merged


def _format_token_count(value: int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:,}"


def print_generation_cost_summary(
    generation_report: dict[str, Any],
    *,
    model_used: str,
    log_prefix: str | None = None,
) -> None:
    """Print Together token usage and estimated USD cost after a draft run."""
    log = log_prefix or write_log_prefix()
    mode = str(generation_report.get("mode") or "").strip()

    if mode == "mock" or model_used == "mock":
        elapsed = generation_report.get("elapsed_seconds")
        if elapsed is not None:
            print(f"{log} Generation time: {elapsed}s (mock — no Together API usage)")
        else:
            print(f"{log} Mock run — no Together API tokens or cost")
        return

    print(f"{log} Model: {generation_report.get('model_used', model_used)}")

    elapsed = generation_report.get("elapsed_seconds")
    api_calls = generation_report.get("validation_attempts") or generation_report.get("validation_attempt")
    if elapsed is not None:
        call_note = f" ({api_calls} API call{'s' if api_calls != 1 else ''})" if api_calls else ""
        print(f"{log} Generation time: {elapsed}s{call_note}")

    if generation_report.get("validation_passed") is False:
        print(f"{log} Validation passed on generation: no (see validation JSON)")
    elif generation_report.get("validation_passed") is True:
        print(f"{log} Validation passed on generation: yes")

    usage = generation_report.get("usage") or {}
    if usage:
        print(
            f"{log} Tokens: "
            f"{_format_token_count(usage.get('prompt_tokens'))} in / "
            f"{_format_token_count(usage.get('completion_tokens'))} out / "
            f"{_format_token_count(usage.get('total_tokens'))} total"
        )
        cached = int(usage.get("cached_tokens") or 0)
        if cached:
            print(f"{log} Cached input tokens: {_format_token_count(cached)}")

    cost_block = generation_report.get("estimated_cost_usd") or {}
    token_cost = cost_block.get("tokens") or {}
    total_usd = token_cost.get("total")
    if total_usd is not None:
        input_usd = float(token_cost.get("input") or 0)
        output_usd = float(token_cost.get("output") or 0)
        print(
            f"{log} Estimated inference cost: ${total_usd:.4f} USD "
            f"(input ${input_usd:.4f}, output ${output_usd:.4f})"
        )
    elif usage:
        note = token_cost.get("note") or "No catalog pricing for this model."
        print(f"{log} Estimated inference cost: unavailable — {note}")

    endpoint_cost = cost_block.get("endpoint") or {}
    if endpoint_cost.get("total") is not None:
        print(f"{log} Estimated endpoint uptime cost: ${endpoint_cost['total']:.4f} USD")

    combined = cost_block.get("combined_total")
    if combined is not None:
        print(f"{log} Estimated combined cost: ${combined:.4f} USD")


def generate_validated_draft(
    prompt: str,
    model: str,
    *,
    allow_serverless_fallback: bool = True,
    max_attempts: int = DEFAULT_VALIDATION_MAX_ATTEMPTS,
    author_name: str = DEFAULT_AUTHOR_NAME,
    author_credentials: str = DEFAULT_AUTHOR_CREDENTIALS,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Generate a draft and retry with validation feedback until checks pass or attempts run out."""
    log = write_log_prefix()
    max_attempts = max(1, max_attempts)
    draft = ""
    validation_report: dict[str, Any] = {"passed": False, "checks": {}}
    generation_reports: list[dict[str, Any]] = []
    revision_feedback = ""

    for attempt in range(1, max_attempts + 1):
        if attempt == 1:
            current_prompt = prompt
        else:
            current_prompt = (
                f"{prompt}\n\n---\n\n"
                f"VALIDATION REVISION REQUIRED (attempt {attempt} of {max_attempts}):\n"
                f"{revision_feedback}\n\n"
                f"PREVIOUS DRAFT TO REVISE:\n```\n{draft.strip()}\n```"
            )

        draft, generation_report = generate_with_together(
            current_prompt,
            model,
            allow_serverless_fallback=allow_serverless_fallback,
        )
        generation_report["validation_attempt"] = attempt
        generation_reports.append(generation_report)

        validation_report = validate_draft(draft)
        if validation_report["passed"]:
            print(f"{log} Validation passed on attempt {attempt}.")
            break

        failed = [name for name, passed in validation_report["checks"].items() if not passed]
        print(f"{log} Validation failed on attempt {attempt}: {', '.join(failed)}")
        if attempt < max_attempts:
            revision_feedback = format_failed_validation_feedback(
                validation_report,
                author_name=author_name,
                author_credentials=author_credentials,
            )
        else:
            print(f"{log} Warning: Draft still failing validation after {max_attempts} attempt(s).")

    merged_report = merge_generation_reports(generation_reports)
    merged_report["validation_passed"] = validation_report["passed"]
    merged_report["validation_attempts"] = len(generation_reports)
    return draft, validation_report, merged_report


def save_text(text: str, path: Path, *, log_prefix: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"{log_prefix or write_log_prefix()} Saved {path}")


def save_json(data: dict[str, Any], path: Path, *, log_prefix: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"{log_prefix or write_log_prefix()} Saved {path}")


def clear_drafts_directory(output_dir: Path) -> list[Path]:
    """Remove existing draft files from typed subdirectories and legacy flat files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    removed: list[Path] = []
    md_dir, pdf_dir, json_dir = draft_subdirs(output_dir)
    targets = [md_dir, pdf_dir, json_dir, output_dir]
    for directory in targets:
        if not directory.exists():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            if directory == output_dir and path.name in {
                DRAFTS_MD_DIRNAME,
                DRAFTS_PDF_DIRNAME,
                DRAFTS_JSON_DIRNAME,
            }:
                continue
            path.unlink()
            removed.append(path)
    return removed


def draft_artifact_paths(draft_path: Path) -> list[Path]:
    """Return the Markdown, PDF, and validation JSON paths for one draft stem."""
    stem = draft_stem_from_path(draft_path)
    output_dir = resolve_drafts_root(draft_path)
    md_dir, pdf_dir, json_dir = draft_subdirs(output_dir)
    paths = [
        md_dir / f"{stem}.md",
        pdf_dir / f"{stem}.pdf",
        json_dir / f"{stem}-validation.json",
    ]
    if draft_path.parent == output_dir:
        paths.extend(
            [
                output_dir / f"{stem}.md",
                output_dir / f"{stem}.pdf",
                output_dir / f"{stem}-validation.json",
            ]
        )
    return paths


def remove_draft_artifacts(draft_path: Path) -> list[Path]:
    """Remove one draft's Markdown, PDF, and validation JSON files."""
    removed: list[Path] = []
    seen: set[str] = set()
    for path in draft_artifact_paths(draft_path):
        key = str(path.resolve())
        if key in seen or not path.is_file():
            continue
        seen.add(key)
        path.unlink()
        removed.append(path)
    return removed


def save_draft_outputs(
    *,
    draft: str,
    output_dir: Path,
    selected_sources: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    source_decision: dict[str, Any],
    model_used: str,
    generation_report: dict[str, Any],
    skip_pdf: bool = False,
) -> dict[str, Any]:
    """Validate, save Markdown/PDF/JSON outputs, and print summary lines."""
    log = write_log_prefix()
    draft_path, pdf_path, report_path = output_paths(draft, output_dir)
    report = validate_draft(draft)
    report["generated_at"] = datetime.now().isoformat()
    report["source_count"] = len(selected_sources)
    report["available_source_count"] = len(sources)
    report["source_selection"] = source_decision
    report["model"] = model_used
    report["generation"] = generation_report
    report["draft_path"] = str(draft_path)
    report["sources_used"] = sources_used_payload(selected_sources)
    if generation_report.get("validation_attempts") is not None:
        report["validation_attempts"] = generation_report["validation_attempts"]
    if generation_report.get("validation_passed") is not None:
        report["validation_passed_on_generation"] = generation_report["validation_passed"]

    save_text(draft, draft_path, log_prefix=log)
    if skip_pdf:
        report["pdf_path"] = None
    else:
        try:
            save_draft_pdf(draft, pdf_path)
            print(f"{log} Saved {pdf_path}")
            report["pdf_path"] = str(pdf_path)
        except Exception as exc:
            report["pdf_path"] = None
            report["pdf_error"] = str(exc)
            print(f"{log} Warning: PDF export failed: {exc}")
    save_json(report, report_path, log_prefix=log)

    print(f"{log} Validation passed: {report['passed']}")
    print_generation_cost_summary(
        generation_report,
        model_used=model_used,
        log_prefix=log,
    )
    if not report["passed"]:
        failed = [name for name, passed in report["checks"].items() if not passed]
        print(f"{log} Failed checks: {', '.join(failed)}")

    recorded = record_used_sources(
        selected_sources,
        draft_path=draft_path,
        runner=write_runner_name(),
        mode=str(generation_report.get("mode") or ""),
    )
    if recorded:
        print(f"{log} Recorded {len(recorded)} used source URL(s) in output/sources/used_sources.json")

    return report

