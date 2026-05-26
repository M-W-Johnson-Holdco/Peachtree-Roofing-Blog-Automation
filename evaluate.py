"""Evaluate Tavily search results with Together AI.

This stage reads `output/drafts/search_results.json`, scores each source for
Peachtree's GEO blog strategy, and writes:

- `output/drafts/evaluated_sources.json` for all scored sources
- `output/drafts/kept_sources.json` for sources worth sending to write.py

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


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "output" / "drafts" / "search_results.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "output" / "drafts" / "evaluated_sources.json"
DEFAULT_KEPT_PATH = PROJECT_ROOT / "output" / "drafts" / "kept_sources.json"
PROMPT_PATH = PROJECT_ROOT / "prompts" / "evaluate.txt"

DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct-Turbo"
KEEP_THRESHOLD = 6.0
CONTENT_SNIPPET_LIMIT = 2800

SCORE_KEYS = [
    "local_relevance",
    "roofing_relevance",
    "recency",
    "source_authority",
    "actionability",
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
    domain = str(source.get("domain", "")).lower()
    priority_source = bool(source.get("priority_source")) or domain in PRIORITY_DOMAINS

    headline_has_topic = contains_any(title_url_text, ROOFING_TERMS)
    early_article_has_topic = contains_any(early_article_text, ROOFING_TERMS)
    headline_has_local = contains_any(title_url_text, LOCAL_TERMS)
    article_has_local = contains_any(text, LOCAL_TERMS)

    scores = {
        "local_relevance": 9 if headline_has_local else 7 if article_has_local else 2,
        "roofing_relevance": 8 if headline_has_topic else 5 if early_article_has_topic else 1,
        "recency": recency_score(str(source.get("published_date", ""))),
        "source_authority": 9 if priority_source else 5,
        "actionability": 8
        if contains_any(early_article_text, {"inspection", "damage", "claim", "insurance", "permit", "safety"})
        else 3,
    }
    weighted_score = round(
        scores["local_relevance"] * 0.30
        + scores["roofing_relevance"] * 0.30
        + scores["recency"] * 0.20
        + scores["source_authority"] * 0.10
        + scores["actionability"] * 0.10,
        2,
    )

    keep = weighted_score >= KEEP_THRESHOLD
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
    normalized_scores = {key: normalize_score(scores.get(key)) for key in SCORE_KEYS}

    weighted_score = evaluation.get("weighted_score")
    try:
        weighted_score = round(float(weighted_score), 2)
    except (TypeError, ValueError):
        weighted_score = round(
            normalized_scores["local_relevance"] * 0.30
            + normalized_scores["roofing_relevance"] * 0.30
            + normalized_scores["recency"] * 0.20
            + normalized_scores["source_authority"] * 0.10
            + normalized_scores["actionability"] * 0.10,
            2,
        )

    keep = bool(evaluation.get("keep", weighted_score >= KEEP_THRESHOLD))
    recommended_angle = evaluation.get("recommended_angle") or build_fallback_angle(source)
    if not keep:
        recommended_angle = ""

    return {
        "title": evaluation.get("title") or source.get("title", ""),
        "url": evaluation.get("url") or source.get("url", ""),
        "strategy_cluster": source.get("strategy_cluster", ""),
        "pillar_topic": source.get("pillar_topic", ""),
        "trigger_window_hours": source.get("trigger_window_hours"),
        "scores": normalized_scores,
        "weighted_score": weighted_score,
        "keep": keep,
        "reason": evaluation.get("reason") or "No reason provided.",
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
    kept = [item for item in evaluated if item["keep"]]
    evaluated.sort(key=lambda item: item["weighted_score"], reverse=True)
    kept.sort(key=lambda item: item["weighted_score"], reverse=True)

    save_json(evaluated, args.output)
    save_json(kept, args.kept_output)

    print(f"[evaluate] Kept {len(kept)}/{len(evaluated)} sources at threshold {KEEP_THRESHOLD}")


if __name__ == "__main__":
    main()
