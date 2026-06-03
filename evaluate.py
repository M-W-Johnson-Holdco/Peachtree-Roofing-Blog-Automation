"""Evaluate Tavily search results with Together AI.

This stage reads `output/sources/search_results.json`, scores each source for
Peachtree's GEO blog strategy, and writes:

- `output/sources/evaluated_sources.json` for all scored sources
- `output/sources/kept_sources.json` for sources worth sending to write.py

Run live:
    python evaluate.py

Run without Together credits:
    python evaluate.py --mock
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from used_sources import normalize_source_url, source_url, used_source_urls


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "output" / "sources" / "search_results_all_roofing.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "output" / "sources" / "evaluated_sources.json"
DEFAULT_KEPT_PATH = PROJECT_ROOT / "output" / "sources" / "kept_sources.json"
PROMPT_PATH = PROJECT_ROOT / "prompts" / "evaluate.txt"

DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct-Turbo"
KEEP_THRESHOLD = 6.0
MIN_KEPT_SOURCES = 2
CONTENT_SNIPPET_LIMIT = 2800

SCORE_KEYS = [
    "local_relevance",
    "roofing_relevance",
    "recency",
    "source_authority",
    "actionability",
    "territory_alignment",
    "semantic_relevance",
]

LOCAL_TERMS = {
    "atlanta",
    "metro atlanta",
    "georgia",
    "fulton",
    "dekalb",
    "cobb",
    "gwinnett",
    "cherokee",
    "henry",
    "buckhead",
    "midtown",
    "marietta",
    "alpharetta",
    "dunwoody",
    "woodstock",
    "east cobb",
    "vinings",
    "chamblee",
    "sandy springs",
    "roswell",
    "decatur",
    "lawrenceville",
    "smyrna",
}

ROOFING_TERMS = {
    "roof",
    "roofing",
    "shingle",
    "gutter",
    "siding",
    "exterior",
    "storm",
    "hail",
    "wind",
    "thunderstorm",
    "tornado",
    "insurance",
    "claim",
    "deductible",
    "rcv",
    "acv",
    "building code",
    "permit",
    "hoa",
    "fire",
    "damage",
    "inspection",
    "safety",
    "structural",
    "hvac",
    "flashing",
    "attic",
    "ventilation",
}

PRIORITY_DOMAINS = {
    "fox5atlanta.com",
    "wsbtv.com",
    "ajc.com",
    "11alive.com",
    "weather.gov",
    "legis.ga.gov",
    "dca.ga.gov",
}

SECONDARY_DOMAINS = {
    "cbs46.com",
    "atlantan.com",
    "mdjonline.com",
    "gwinnettdailypost.com",
    "rockdalenewtoncitizen.com",
    "accesswdun.com",
    "reporternewspapers.net",
    "northside-neighbor.com",
}


def source_authority_score(source: dict[str, Any]) -> int:
    domain = str(source.get("domain", "")).lower()
    if bool(source.get("priority_source")) or domain in PRIORITY_DOMAINS:
        return 9
    if bool(source.get("secondary_source")) or domain in SECONDARY_DOMAINS:
        return 7
    if bool(source.get("official_source")):
        return 8
    return 5


def load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}")

    return data


def save_json(data: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[evaluate] Saved {len(data)} records to {path}")


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def source_text(source: dict[str, Any]) -> str:
    return " ".join(
        [
            str(source.get("title", "")),
            str(source.get("url", "")),
            str(source.get("domain", "")),
            str(source.get("content", "")),
            str(source.get("strategy_cluster", "")),
            str(source.get("pillar_topic", "")),
        ]
    ).lower()


def parse_published_date(value: str) -> datetime | None:
    if not value:
        return None

    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def recency_score(published_date: str) -> int:
    parsed = parse_published_date(published_date)
    if not parsed:
        return 5

    age_days = (datetime.now(timezone.utc) - parsed).days
    if age_days <= 7:
        return 10
    if age_days <= 14:
        return 5
    return 1


def contains_any(text: str, terms: set[str]) -> bool:
    for term in terms:
        normalized = term.lower()
        if " " in normalized:
            if normalized in text:
                return True
            continue

        if re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", text):
            return True

    return False


def source_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def metadata_adjustments(source: dict[str, Any]) -> dict[str, Any]:
    territory_score = source_int(source.get("territory_alignment_score"))
    semantic_score = source_int(source.get("semantic_relevance_score"))
    multi_territory_bonus = source_int(source.get("multi_territory_bonus"))
    off_topic_penalty = source_int(source.get("off_topic_penalty"))
    duplicate_topic_penalty = source_int(source.get("duplicate_topic_penalty"))

    adjustment = round(
        min(multi_territory_bonus, 4) * 0.15
        - min(off_topic_penalty, 10) * 0.35
        - min(duplicate_topic_penalty, 4) * 0.25,
        2,
    )

    hard_reject_reasons = []
    used_urls = used_source_urls()
    if used_urls and normalize_source_url(source_url(source)) in used_urls:
        hard_reject_reasons.append("source URL was already used in a previous blog draft")
    if off_topic_penalty >= 7:
        hard_reject_reasons.append("off-topic penalty is too high")
    if semantic_score and semantic_score < 4:
        hard_reject_reasons.append("semantic relevance check did not pass")
    if duplicate_topic_penalty >= 4:
        hard_reject_reasons.append("topic overlaps a draft from the past 30 days")

    return {
        "territory_alignment_score": territory_score,
        "semantic_relevance_score": semantic_score,
        "multi_territory_bonus": multi_territory_bonus,
        "off_topic_penalty": off_topic_penalty,
        "duplicate_topic_penalty": duplicate_topic_penalty,
        "weighted_score_adjustment": adjustment,
        "hard_reject_reasons": hard_reject_reasons,
    }


def mock_evaluate_source(source: dict[str, Any]) -> dict[str, Any]:
    """Local scoring for plumbing tests when no Together key is available."""
    text = source_text(source)
    title_url_text = " ".join(
        [
            str(source.get("title", "")),
            str(source.get("url", "")),
        ]
    ).lower()
    early_article_text = " ".join(
        [
            str(source.get("title", "")),
            str(source.get("url", "")),
            str(source.get("content", ""))[:900],
        ]
    ).lower()

    headline_has_topic = contains_any(title_url_text, ROOFING_TERMS)
    early_article_has_topic = contains_any(early_article_text, ROOFING_TERMS)
    headline_has_local = contains_any(title_url_text, LOCAL_TERMS)
    article_has_local = contains_any(text, LOCAL_TERMS)

    scores = {
        "local_relevance": 9 if headline_has_local else 7 if article_has_local else 2,
        "roofing_relevance": 8 if headline_has_topic else 5 if early_article_has_topic else 1,
        "recency": recency_score(str(source.get("published_date", ""))),
        "source_authority": source_authority_score(source),
        "actionability": 8
        if contains_any(early_article_text, {"inspection", "damage", "claim", "insurance", "permit", "safety"})
        else 3,
        "territory_alignment": max(1, min(10, source_int(source.get("territory_alignment_score"), 5))),
        "semantic_relevance": max(1, min(10, source_int(source.get("semantic_relevance_score"), 5))),
    }
    weighted_score = round(
        scores["local_relevance"] * 0.24
        + scores["roofing_relevance"] * 0.24
        + scores["recency"] * 0.14
        + scores["source_authority"] * 0.08
        + scores["actionability"] * 0.10
        + scores["territory_alignment"] * 0.10
        + scores["semantic_relevance"] * 0.10,
        2,
    )
    adjustments = metadata_adjustments(source)
    adjusted_weighted_score = round(
        max(1.0, min(10.0, weighted_score + adjustments["weighted_score_adjustment"])),
        2,
    )

    keep = adjusted_weighted_score >= KEEP_THRESHOLD and not adjustments["hard_reject_reasons"]
    reason = (
        "Mock score keeps this source because it is local, recent, authoritative, and strategy-relevant."
        if keep
        else "Mock score rejects this source because it does not clearly support a Metro Atlanta roofing blog angle."
    )

    return normalize_evaluation(
        {
            "title": source.get("title", ""),
            "url": source.get("url", ""),
            "scores": scores,
            "weighted_score": weighted_score,
            "keep": keep,
            "reason": reason,
            "recommended_angle": build_fallback_angle(source),
        },
        source,
    )


def build_prompt(prompt_template: str, source: dict[str, Any]) -> str:
    return prompt_template.format(
        title=source.get("title", ""),
        url=source.get("url", ""),
        published_date=source.get("published_date", ""),
        content=str(source.get("content", ""))[:CONTENT_SNIPPET_LIMIT],
        domain=source.get("domain", ""),
        query=source.get("query", ""),
        strategy_cluster=source.get("strategy_cluster", ""),
        pillar_topic=source.get("pillar_topic", ""),
        trigger_window_hours=source.get("trigger_window_hours", ""),
        territory_alignment_score=source.get("territory_alignment_score", ""),
        matched_territories=json.dumps(source.get("matched_territories", {}), ensure_ascii=True),
        multi_territory_bonus=source.get("multi_territory_bonus", ""),
        semantic_relevance_score=source.get("semantic_relevance_score", ""),
        semantic_relevance_rules=", ".join(source.get("semantic_relevance_rules", [])),
        off_topic_penalty=source.get("off_topic_penalty", ""),
        off_topic_matches=json.dumps(source.get("off_topic_matches", {}), ensure_ascii=True),
        duplicate_topic_penalty=source.get("duplicate_topic_penalty", ""),
        duplicate_topic_match=json.dumps(source.get("duplicate_topic_match"), ensure_ascii=True),
    )


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))

    if not isinstance(parsed, dict):
        raise ValueError("Model response was valid JSON but not an object")

    return parsed


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
            "TOGETHER_API_KEY is not set. Add it to .env, or run `python evaluate.py --mock`."
        )

    return Together(api_key=api_key)


def evaluate_source_with_together(
    source: dict[str, Any],
    prompt_template: str,
    client: Any,
    model: str,
) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Return strict JSON only. Do not include markdown or commentary.",
            },
            {"role": "user", "content": build_prompt(prompt_template, source)},
        ],
        temperature=0.1,
        max_tokens=800,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    evaluation = extract_json_object(content)
    return normalize_evaluation(evaluation, source)


def normalize_score(value: Any) -> int:
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        score = 1
    return max(1, min(10, score))


def build_fallback_angle(source: dict[str, Any]) -> str:
    cluster = source.get("strategy_cluster") or "local_roofing"
    title = source.get("title") or "this local event"

    if cluster == "storm_damage":
        return "What should Metro Atlanta homeowners inspect after this storm or damage report?"
    if cluster == "ga_insurance_navigation":
        return "How does this Georgia insurance update affect roof repair or replacement claims?"
    if cluster == "roof_safety":
        return "What roof safety risks should Atlanta homeowners understand from this local report?"
    if cluster == "county_guides":
        return "What should homeowners in this county know before planning roof work?"
    return f"What should Atlanta homeowners know about {title}?"


def normalize_evaluation(evaluation: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    scores = evaluation.get("scores") if isinstance(evaluation.get("scores"), dict) else {}
    normalized_scores = {}
    for key in SCORE_KEYS:
        default = 5 if key in {"territory_alignment", "semantic_relevance"} else 1
        normalized_scores[key] = normalize_score(scores.get(key, default))
    adjustments = metadata_adjustments(source)
    if adjustments["territory_alignment_score"] and not scores.get("territory_alignment"):
        normalized_scores["territory_alignment"] = normalize_score(adjustments["territory_alignment_score"])
    if adjustments["semantic_relevance_score"] and not scores.get("semantic_relevance"):
        normalized_scores["semantic_relevance"] = normalize_score(adjustments["semantic_relevance_score"])

    weighted_score = evaluation.get("weighted_score")
    try:
        weighted_score = round(float(weighted_score), 2)
    except (TypeError, ValueError):
        weighted_score = round(
            normalized_scores["local_relevance"] * 0.24
            + normalized_scores["roofing_relevance"] * 0.24
            + normalized_scores["recency"] * 0.14
            + normalized_scores["source_authority"] * 0.08
            + normalized_scores["actionability"] * 0.10
            + normalized_scores["territory_alignment"] * 0.10
            + normalized_scores["semantic_relevance"] * 0.10,
            2,
        )

    adjusted_weighted_score = round(
        max(1.0, min(10.0, weighted_score + adjustments["weighted_score_adjustment"])),
        2,
    )
    keep = bool(evaluation.get("keep", adjusted_weighted_score >= KEEP_THRESHOLD))
    if adjusted_weighted_score < KEEP_THRESHOLD or adjustments["hard_reject_reasons"]:
        keep = False

    recommended_angle = evaluation.get("recommended_angle") or build_fallback_angle(source)
    if not keep:
        recommended_angle = ""

    reason = evaluation.get("reason") or "No reason provided."
    if adjustments["hard_reject_reasons"]:
        reason = f"{reason} Rejected because {', '.join(adjustments['hard_reject_reasons'])}."

    return {
        "title": evaluation.get("title") or source.get("title", ""),
        "url": evaluation.get("url") or source.get("url", ""),
        "strategy_cluster": source.get("strategy_cluster", ""),
        "pillar_topic": source.get("pillar_topic", ""),
        "trigger_window_hours": source.get("trigger_window_hours"),
        "scores": normalized_scores,
        "model_weighted_score": weighted_score,
        "weighted_score": adjusted_weighted_score,
        "scoring_adjustments": adjustments,
        "keep": keep,
        "reason": reason,
        "recommended_angle": recommended_angle,
        "source": source,
    }


def evaluate_sources(
    sources: list[dict[str, Any]],
    *,
    mock: bool = False,
    model: str = DEFAULT_MODEL,
) -> list[dict[str, Any]]:
    if not sources:
        return []

    if mock:
        return [mock_evaluate_source(source) for source in sources]

    load_dotenv(PROJECT_ROOT / ".env")
    client = get_together_client()
    prompt_template = load_prompt()
    evaluated = []

    for index, source in enumerate(sources, start=1):
        print(f"[evaluate] Scoring source {index}/{len(sources)}: {source.get('title', 'Untitled')}")
        evaluated.append(evaluate_source_with_together(source, prompt_template, client, model))

    return evaluated


def _promote_minimum_kept(item: dict[str, Any]) -> None:
    item["keep"] = True
    fallback_note = (
        f" Kept by minimum-kept fallback (top {MIN_KEPT_SOURCES} by weighted_score "
        f"despite threshold {KEEP_THRESHOLD})."
    )
    item["reason"] = f"{item.get('reason', '').strip()}{fallback_note}".strip()
    if not item.get("recommended_angle"):
        item["recommended_angle"] = build_fallback_angle(item.get("source", {}))


def ensure_minimum_kept(
    evaluated: list[dict[str, Any]],
    *,
    min_kept: int = MIN_KEPT_SOURCES,
) -> list[dict[str, Any]]:
    """Guarantee at least min_kept sources by promoting the highest weighted_score hits."""
    kept = [item for item in evaluated if item.get("keep")]
    if len(kept) >= min_kept:
        return sorted(kept, key=lambda item: item["weighted_score"], reverse=True)

    kept_urls = {item["url"] for item in kept}
    ranked = sorted(evaluated, key=lambda item: item["weighted_score"], reverse=True)

    def try_promote(item: dict[str, Any], *, allow_hard_reject: bool) -> bool:
        if item["url"] in kept_urls:
            return False
        hard_rejects = item.get("scoring_adjustments", {}).get("hard_reject_reasons") or []
        if hard_rejects and not allow_hard_reject:
            return False
        _promote_minimum_kept(item)
        kept.append(item)
        kept_urls.add(item["url"])
        return True

    for item in ranked:
        if len(kept) >= min_kept:
            break
        try_promote(item, allow_hard_reject=False)

    for item in ranked:
        if len(kept) >= min_kept:
            break
        try_promote(item, allow_hard_reject=True)

    return sorted(kept, key=lambda item: item["weighted_score"], reverse=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Tavily sources for GEO blog relevance.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--kept-output", type=Path, default=DEFAULT_KEPT_PATH)
    parser.add_argument("--model", default=os.getenv("TOGETHER_EVALUATION_MODEL", DEFAULT_MODEL))
    parser.add_argument("--mock", action="store_true", help="Use local heuristic scoring instead of Together AI.")
    args = parser.parse_args()

    sources = load_json(args.input)
    print(f"[evaluate] Loaded {len(sources)} source candidates from {args.input}")

    evaluated = evaluate_sources(sources, mock=args.mock, model=args.model)
    evaluated.sort(key=lambda item: item["weighted_score"], reverse=True)
    kept = ensure_minimum_kept(evaluated)

    save_json(evaluated, args.output)
    save_json(kept, args.kept_output)

    promoted = sum(
        1
        for item in kept
        if "minimum-kept fallback" in str(item.get("reason", ""))
    )
    print(
        f"[evaluate] Kept {len(kept)}/{len(evaluated)} sources "
        f"(threshold {KEEP_THRESHOLD}, minimum {MIN_KEPT_SOURCES}"
        f"{f', {promoted} promoted by fallback' if promoted else ''})"
    )


if __name__ == "__main__":
    main()
