"""Score validated blog drafts across writing templates and pick a winner."""

from __future__ import annotations

import json
import re
import time
from typing import Any

from peachtree_blog.write_common import (
    METRO_LOCATIONS,
    build_generation_report,
    estimate_token_cost_usd,
    extract_opening_paragraph,
    extract_usage,
    get_together_client,
    is_together_model_not_available_error,
    serverless_model_attempt_sequence,
    together_chat_completion_kwargs,
)

SCORER_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507-tput"
TIEBREAKER_ORDER = ["scenario", "geo", "explainer"]
SCORE_DIMENSIONS = [
    "title_quality",
    "opening_quality",
    "neighborhood_prose",
    "table_specificity",
    "faq_depth",
    "geo_quotability",
]
MAX_SCORE = len(SCORE_DIMENSIONS) * 10
MAX_TOTAL_WITH_BONUS = MAX_SCORE + 2

TEMPLATE_IDS = ("geo", "scenario", "explainer")


def _extract_title(markdown: str) -> str:
    match = re.search(r"^#\s+(.+)$", markdown, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_h2_headings(markdown: str) -> list[str]:
    return re.findall(r"^##\s+(.+)$", markdown, flags=re.MULTILINE)


def _extract_neighborhood_section_text(markdown: str) -> str:
    h2_matches = list(re.finditer(r"^##\s+(.+)$", markdown, flags=re.MULTILINE))
    for index, match in enumerate(h2_matches):
        heading = match.group(1).lower()
        if "neighborhood" in heading or "counties" in heading or "county" in heading:
            start = match.end()
            end = h2_matches[index + 1].start() if index + 1 < len(h2_matches) else len(markdown)
            return markdown[start:end].strip()[:400]
    return ""


def _extract_table_preview(markdown: str, *, max_rows: int = 6) -> list[str]:
    rows: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if re.match(r"^\|\s*:?-+", stripped):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")][:3]
        rows.append(" | ".join(cells))
        if len(rows) >= max_rows:
            break
    return rows


def _extract_faq_answer_first_sentences(markdown: str) -> list[str]:
    faq_match = re.search(r"(^##+ FAQ\b.*)", markdown, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
    if not faq_match:
        return []

    faq_section = faq_match.group(1)
    headings = list(re.finditer(r"^#{3,6}\s+(.+)$", faq_section, flags=re.MULTILINE))
    sentences: list[str] = []
    for index, heading in enumerate(headings):
        start = heading.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(faq_section)
        answer_text = faq_section[start:end].strip().split("\n\n", maxsplit=1)[0].strip()
        if not answer_text:
            sentences.append("")
            continue
        first_sentence = re.split(r"(?<=[.!?])\s+", answer_text, maxsplit=1)[0].strip()
        sentences.append(first_sentence[:200])
    return sentences


def _locations_found(markdown: str) -> list[str]:
    return sorted(
        location
        for location in METRO_LOCATIONS
        if re.search(rf"\b{re.escape(location)}\b", markdown)
    )


def build_draft_summary(
    draft: str,
    validation_report: dict[str, Any],
    template_id: str,
) -> dict[str, Any]:
    title = _extract_title(draft)
    opening = extract_opening_paragraph(draft, writing_prompt_id=template_id)
    checks = validation_report.get("checks") or {}
    failed_checks = [name for name, passed in checks.items() if not passed]

    return {
        "template_id": template_id,
        "title": title,
        "title_char_count": len(title),
        "opening_preview": opening[:200],
        "opening_word_count": len(opening.split()),
        "h2_headings": _extract_h2_headings(draft),
        "locations_found": _locations_found(draft),
        "citation_count": validation_report.get("citation_count", 0),
        "cta_count": validation_report.get("cta_count", 0),
        "faq_count": validation_report.get("faq_count", 0),
        "has_comparison_table": bool(validation_report.get("checks", {}).get("has_comparison_table")),
        "validation_passed": bool(validation_report.get("passed")),
        "failed_checks": failed_checks,
        "neighborhood_section_preview": _extract_neighborhood_section_text(draft),
        "table_rows_preview": _extract_table_preview(draft),
        "faq_answer_first_sentences": _extract_faq_answer_first_sentences(draft),
    }


def build_scorer_prompt(summaries: list[dict[str, Any]]) -> str:
    summaries_block = json.dumps(summaries, indent=2, ensure_ascii=False)
    return f"""You are scoring blog drafts for Peachtree Roofing & Exteriors.
Score each draft on exactly 6 dimensions, 0-10 each.
Return ONLY valid JSON — no preamble, no commentary.

SCORING DIMENSIONS (0-10 each):
1. title_quality: Is the title <=70 characters? Does it include a Metro Atlanta location and specific topic? Is it search-query shaped (not generic)?
2. opening_quality: Does the opening paragraph name a news outlet and date in sentence one? Does it answer the reader's question directly? Is it 50-120 words?
3. neighborhood_prose: Is the neighborhood section written in prose paragraphs (not bullet points)? Does each location mention carry a specific concrete reason (terrain, housing era, drainage issue)?
4. table_specificity: Do table rows name specific Metro Atlanta locations + housing types + concrete mechanisms? Are rows distinct and individually quotable? Penalize generic rows (e.g., "Risk Factor | Impact | Prevention").
5. faq_depth: Do FAQ questions cover varied topics (not the same question 8 ways)? Does the first sentence of each answer fully answer the question? Are at least 3 questions location-specific?
6. geo_quotability: Can you quote a single sentence from the opening or any H2 section and have it stand alone as a useful answer? Are H2 first sentences direct answers, not setup sentences?

VALIDATION BONUS: Add 2 points to the total if validation_passed is true. Subtract 2 if title_char_count > 70.

DRAFT SUMMARIES:
{summaries_block}

Return this exact JSON structure:
{{
  "scores": {{
    "geo": {{
      "title_quality": <0-10>,
      "opening_quality": <0-10>,
      "neighborhood_prose": <0-10>,
      "table_specificity": <0-10>,
      "faq_depth": <0-10>,
      "geo_quotability": <0-10>,
      "validation_bonus": <-2, 0, or 2>,
      "total": <sum of above>
    }},
    "scenario": {{ ... }},
    "explainer": {{ ... }}
  }},
  "winner": "<template_id with highest total>",
  "tiebreaker_applied": <true or false>,
  "reason": "<1-2 sentence explanation of why winner scored highest>"
}}

Only include score objects for template_ids present in DRAFT SUMMARIES.
"""


def _parse_scorer_response(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Scorer response was not a JSON object.")
    return parsed


def score_drafts(
    summaries: list[dict[str, Any]],
    *,
    model: str = SCORER_MODEL,
    allow_serverless_fallback: bool = True,
) -> dict[str, Any]:
    client = get_together_client()
    prompt = build_scorer_prompt(summaries)
    started_at = time.monotonic()
    model_requested = model
    model_used = model
    models_to_try = serverless_model_attempt_sequence(
        model,
        allow_serverless_fallback=allow_serverless_fallback,
    )

    response = None
    last_exc: Exception | None = None
    for attempt_index, active_model in enumerate(models_to_try):
        try:
            if attempt_index > 0:
                print(
                    f"[draft_scorer] Model unavailable on Together serverless. "
                    f"Retrying with {active_model}."
                )
            response = client.chat.completions.create(
                model=active_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=800,
                response_format={"type": "json_object"},
                **together_chat_completion_kwargs(active_model),
            )
            model_used = active_model
            break
        except Exception as exc:
            last_exc = exc
            if not allow_serverless_fallback or not is_together_model_not_available_error(exc):
                raise
            if attempt_index >= len(models_to_try) - 1:
                raise

    if response is None:
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Scorer call failed without a response.")

    elapsed_seconds = time.monotonic() - started_at
    content = response.choices[0].message.content or ""
    parsed = _parse_scorer_response(content)
    usage = extract_usage(response)
    metadata = build_generation_report(
        model_requested=model_requested,
        model_used=model_used,
        model_returned_by_api=getattr(response, "model", None),
        elapsed_seconds=elapsed_seconds,
        usage=usage,
    )
    return {"result": parsed, "usage": usage, "model": model_used, "generation": metadata}


def apply_tiebreaker(score_result: dict[str, Any]) -> dict[str, Any]:
    parsed = score_result.get("result")
    if not isinstance(parsed, dict):
        return score_result

    scores = parsed.get("scores")
    if not isinstance(scores, dict) or not scores:
        return score_result

    totals: dict[str, float] = {}
    for template_id, entry in scores.items():
        if isinstance(entry, dict):
            totals[str(template_id)] = float(entry.get("total") or 0)

    if not totals:
        return score_result

    max_total = max(totals.values())
    leaders = [template_id for template_id, total in totals.items() if max_total - total <= 2]
    winner = parsed.get("winner")
    tiebreaker_applied = False

    if len(leaders) > 1:
        for preferred in TIEBREAKER_ORDER:
            if preferred in leaders:
                winner = preferred
                tiebreaker_applied = True
                break
    elif not winner or winner not in totals:
        winner = max(totals, key=totals.get)

    parsed["winner"] = winner
    parsed["tiebreaker_applied"] = tiebreaker_applied
    score_result["result"] = parsed
    return score_result


def validation_check_score(validation_report: dict[str, Any]) -> int:
    checks = validation_report.get("checks") or {}
    return sum(1 for passed in checks.values() if passed)


def run_scoring(
    drafts: dict[str, tuple[str, dict[str, Any]]],
    *,
    model: str = SCORER_MODEL,
) -> dict[str, Any]:
    summaries = [
        build_draft_summary(draft_text, validation_report, template_id)
        for template_id, (draft_text, validation_report) in drafts.items()
    ]
    score_payload = score_drafts(summaries, model=model)
    score_payload = apply_tiebreaker(score_payload)
    parsed = score_payload.get("result") or {}
    generation = score_payload.get("generation") or {}
    usage = score_payload.get("usage") or {}
    token_cost = estimate_token_cost_usd(model, usage) if usage else {}

    return {
        "winner": parsed.get("winner"),
        "scores": parsed.get("scores") or {},
        "tiebreaker_applied": bool(parsed.get("tiebreaker_applied")),
        "reason": str(parsed.get("reason") or "").strip(),
        "scorer_usage": usage,
        "scorer_model": model,
        "scorer_generation": generation,
        "scorer_estimated_cost_usd": token_cost.get("total"),
    }
