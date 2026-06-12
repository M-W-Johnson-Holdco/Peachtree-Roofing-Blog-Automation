"""Track search (Tavily) and evaluate inference costs for Slack approval summaries."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from peachtree_blog.paths import PROJECT_ROOT

DEFAULT_PIPELINE_COSTS_PATH = PROJECT_ROOT / "output" / "sources" / "pipeline_costs.json"
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


def inference_cost_usd(validation_report: dict[str, Any]) -> float | None:
    """Sum write + evaluate token inference costs when available."""
    totals: list[float] = []

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


def format_approval_summary_slack_lines(
    validation_report: dict[str, Any],
    *,
    model_display: str | None = None,
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

    inference_total = inference_cost_usd(validation_report)
    if inference_total is not None:
        lines.append(f"• Est. inference cost: ${inference_total:.4f} USD")

    tavily_total = tavily_cost_usd(validation_report)
    if tavily_total is not None:
        lines.append(f"• Est. Tavily cost: ${tavily_total:.4f} USD")

    source_count = validation_report.get("source_count")
    if source_count is not None:
        lines.append(f"• Sources used: {source_count}")

    return lines
