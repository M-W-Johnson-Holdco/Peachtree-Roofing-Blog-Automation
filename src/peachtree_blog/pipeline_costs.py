"""Track search (Tavily) and evaluate inference costs for Slack approval summaries."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from peachtree_blog.paths import PROJECT_ROOT

DEFAULT_PIPELINE_COSTS_PATH = PROJECT_ROOT / "output" / "sources" / "pipeline_costs.json"
TAVILY_SEARCH_RAN_FLAG_PATH = PROJECT_ROOT / "output" / "sources" / ".tavily_search_ran.json"
DEFAULT_TAVILY_USD_PER_CREDIT = 0.008


def tavily_usd_per_credit() -> float:
    raw = os.getenv("TAVILY_USD_PER_CREDIT", "").strip()
    if raw:
        return float(raw)
    return DEFAULT_TAVILY_USD_PER_CREDIT


def estimate_tavily_cost_usd(credits_used: int) -> float:
    return round(credits_used * tavily_usd_per_credit(), 6)


def load_pipeline_costs(path: Path = DEFAULT_PIPELINE_COSTS_PATH) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def save_pipeline_costs(data: dict[str, Any], path: Path = DEFAULT_PIPELINE_COSTS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def reset_pipeline_costs(path: Path = DEFAULT_PIPELINE_COSTS_PATH) -> None:
    save_pipeline_costs({}, path)
    if TAVILY_SEARCH_RAN_FLAG_PATH.is_file():
        TAVILY_SEARCH_RAN_FLAG_PATH.unlink()


def mark_tavily_search_ran(
    *,
    credits_used: int,
    queries_run: int,
    path: Path = TAVILY_SEARCH_RAN_FLAG_PATH,
) -> None:
    """Record that the current pipeline process completed a Tavily search stage."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "credits_used": credits_used,
        "queries_run": queries_run,
        "marked_at": datetime.now(timezone.utc).isoformat(),
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def consume_tavily_search_ran(path: Path = TAVILY_SEARCH_RAN_FLAG_PATH) -> dict[str, Any] | None:
    """Return and clear the Tavily search marker for the next write step in this pipeline."""
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    path.unlink()
    return payload if isinstance(payload, dict) else None


def record_search_cost(
    *,
    queries_run: int,
    credits_used: int,
    path: Path = DEFAULT_PIPELINE_COSTS_PATH,
) -> dict[str, Any]:
    data = load_pipeline_costs(path)
    data["search"] = {
        "queries_run": queries_run,
        "credits_used": credits_used,
        "estimated_cost_usd": estimate_tavily_cost_usd(credits_used),
        "currency": "USD",
        "pricing_per_credit": tavily_usd_per_credit(),
        "pricing_source": "tavily_catalog",
    }
    save_pipeline_costs(data, path)
    return data["search"]


def record_evaluate_cost(
    run_report: dict[str, Any],
    *,
    api_calls: int | None = None,
    path: Path = DEFAULT_PIPELINE_COSTS_PATH,
) -> dict[str, Any]:
    data = load_pipeline_costs(path)
    data["evaluate"] = {
        "model_used": run_report.get("model_used"),
        "api_calls": api_calls if api_calls is not None else run_report.get("api_calls"),
        "elapsed_seconds": run_report.get("elapsed_seconds"),
        "estimated_cost_usd": run_report.get("estimated_cost_usd"),
        "mode": run_report.get("mode"),
    }
    save_pipeline_costs(data, path)
    return data["evaluate"]


def token_cost_total(cost_block: dict[str, Any] | None) -> float | None:
    if not isinstance(cost_block, dict):
        return None
    tokens = cost_block.get("tokens")
    if not isinstance(tokens, dict):
        return None
    total = tokens.get("total")
    if total is None:
        return None
    return float(total)


def generation_report_token_cost_usd(generation_report: dict[str, Any] | None) -> float | None:
    if not isinstance(generation_report, dict):
        return None
    return token_cost_total(generation_report.get("estimated_cost_usd"))


def summarize_multi_run_inference_costs(
    results: dict[str, tuple[Any, ...]],
    *,
    scorer_estimated_cost_usd: float | None = None,
) -> dict[str, Any]:
    """Sum token inference cost across all compared templates plus the scorer call."""
    template_costs: dict[str, float] = {}
    for template_id, item in results.items():
        generation_report = item[2] if len(item) >= 3 else {}
        cost = generation_report_token_cost_usd(generation_report)
        if cost is not None:
            template_costs[str(template_id)] = round(cost, 6)

    write_total = round(sum(template_costs.values()), 6) if template_costs else None
    scorer = (
        round(float(scorer_estimated_cost_usd), 6)
        if scorer_estimated_cost_usd is not None
        else None
    )
    write_plus_scorer_parts = [value for value in (write_total, scorer) if value is not None]
    total = round(sum(write_plus_scorer_parts), 6) if write_plus_scorer_parts else None

    return {
        "template_generation_costs_usd": template_costs,
        "multi_run_write_inference_cost_usd": write_total,
        "scorer_estimated_cost_usd": scorer,
        "total_inference_cost_usd": total,
    }


def inference_cost_usd(validation_report: dict[str, Any]) -> float | None:
    """Sum write + evaluate token inference costs when available."""
    totals: list[float] = []

    multi = validation_report.get("multi_run")
    if isinstance(multi, dict) and multi.get("total_inference_cost_usd") is not None:
        totals.append(float(multi["total_inference_cost_usd"]))
    else:
        generation = validation_report.get("generation")
        if isinstance(generation, dict):
            write_total = token_cost_total(generation.get("estimated_cost_usd"))
            if write_total is not None:
                totals.append(write_total)

    pipeline_costs = validation_report.get("pipeline_costs")
    if isinstance(pipeline_costs, dict):
        evaluate = pipeline_costs.get("evaluate")
        if isinstance(evaluate, dict):
            evaluate_total = token_cost_total(evaluate.get("estimated_cost_usd"))
            if evaluate_total is not None:
                totals.append(evaluate_total)

    if not totals:
        return None
    return round(sum(totals), 6)


def format_inference_cost_slack_line(validation_report: dict[str, Any]) -> str | None:
    """Human-readable inference cost line for Slack approval posts."""
    inference_total = inference_cost_usd(validation_report)
    if inference_total is None:
        return None

    multi = validation_report.get("multi_run")
    if isinstance(multi, dict) and multi.get("total_inference_cost_usd") is not None:
        has_evaluate = False
        pipeline_costs = validation_report.get("pipeline_costs")
        if isinstance(pipeline_costs, dict):
            evaluate = pipeline_costs.get("evaluate")
            if isinstance(evaluate, dict) and token_cost_total(evaluate.get("estimated_cost_usd")) is not None:
                has_evaluate = True
        scope = "all templates + scorer + evaluate" if has_evaluate else "all templates + scorer"
        return f"• Est. inference cost: ${inference_total:.4f} USD ({scope})"

    return f"• Est. inference cost: ${inference_total:.4f} USD"


def tavily_cost_usd(validation_report: dict[str, Any]) -> float | None:
    pipeline_costs = validation_report.get("pipeline_costs")
    if not isinstance(pipeline_costs, dict):
        return None
    search = pipeline_costs.get("search")
    if not isinstance(search, dict):
        return None
    total = search.get("estimated_cost_usd")
    if total is None:
        return None
    return float(total)


def tavily_cost_usd_for_slack(
    validation_report: dict[str, Any],
    *,
    rewritten_from: str | None = None,
    recycled_from: str | None = None,
) -> float:
    """Tavily line for Slack: actual search cost only when search ran for this draft."""
    if rewritten_from:
        return 0.0

    search_ran = validation_report.get("tavily_search_ran")
    if search_ran is False:
        return 0.0
    if search_ran is True:
        return tavily_cost_usd(validation_report) or 0.0

    # Legacy drafts saved before tavily_search_ran existed.
    if recycled_from:
        return tavily_cost_usd(validation_report) or 0.0
    return tavily_cost_usd(validation_report) or 0.0


def format_approval_summary_slack_lines(
    validation_report: dict[str, Any],
    *,
    model_display: str | None = None,
    rewritten_from: str | None = None,
    recycled_from: str | None = None,
) -> list[str]:
    """Compact model, inference, Tavily, and source count lines for Slack approval posts."""
    generation = validation_report.get("generation")
    model_id = ""
    if isinstance(generation, dict):
        model_id = str(generation.get("model_used") or "").strip()
    if not model_id:
        model_id = str(validation_report.get("model") or "").strip()
    if not model_id:
        return []

    lines = [f"• Model: {model_display or model_id}"]

    inference_line = format_inference_cost_slack_line(validation_report)
    if inference_line:
        lines.append(inference_line)

    tavily_total = tavily_cost_usd_for_slack(
        validation_report,
        rewritten_from=rewritten_from,
        recycled_from=recycled_from,
    )
    lines.append(f"• Est. Tavily cost: ${tavily_total:.4f} USD")

    source_count = validation_report.get("source_count")
    if source_count is not None:
        lines.append(f"• Sources used: {source_count}")

    writing_prompt = validation_report.get("writing_prompt")
    if isinstance(writing_prompt, dict):
        label = str(writing_prompt.get("label") or writing_prompt.get("id") or "").strip()
        if label:
            lines.append(f"• Writing template: {label}")

    multi = validation_report.get("multi_run")
    if isinstance(multi, dict):
        from peachtree_blog.write_common import format_multi_run_slack_lines

        lines.extend(format_multi_run_slack_lines(multi))

    return lines
