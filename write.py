"""Generate a GEO-optimized blog draft with Together AI.

This stage reads `output/drafts/kept_sources.json`, injects the current
blog prompt plus editor feedback, calls Together AI, and saves a Markdown
draft plus a lightweight validation report.

Run live:
    python write.py

Run without Together credits:
    python write.py --mock
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "output" / "drafts" / "kept_sources.json"
PROMPT_PATH = PROJECT_ROOT / "prompts" / "blog.txt"
STYLE_NOTES_PATH = PROJECT_ROOT / "feedback" / "style_notes.txt"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "drafts"

DEFAULT_MODEL = "Qwen/Qwen2.5-72B-Instruct-Turbo"
DEFAULT_AUTHOR_NAME = "Jonathan Gil"
DEFAULT_AUTHOR_CREDENTIALS = "Licensed Roofing Contractor, Metro Atlanta"

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
]


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


def build_prompt(
    prompt_template: str,
    sources: list[dict[str, Any]],
    style_notes: str,
    author_name: str,
    author_credentials: str,
) -> str:
    sources_block = format_sources_block(sources)
    style_block = style_notes.strip() or "No editor feedback recorded yet."

    base_prompt = prompt_template.format(
        sources_block=sources_block,
        today=date.today().isoformat(),
        author_name=author_name,
        author_credentials=author_credentials,
    )

    return (
        f"{base_prompt}\n\n---\n\n"
        "RECENT EDITOR FEEDBACK TO APPLY:\n"
        f"{style_block}\n\n"
        "---\n\n"
        "IMPORTANT SOURCE USE RULES:\n"
        "- Do not invent facts, statistics, dates, credentials, review counts, project counts, or license numbers.\n"
        "- Use exactly 3 to 5 cited statistics from the provided sources. The current sources include figures such as 24%, 30%, 25%, $1,000, $2,500, 10 to 20 percent, May 18, 2026, 20-story, three unsecured gaps, and 8x8 concrete pavers when relevant.\n"
        "- Keep all headings and FAQ questions in question format.\n"
        "- Use the exact FAQ format: ## FAQ, then exactly eight H3 question headings and paragraph answers.\n"
        "- Do not format the author byline as a heading.\n"
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


def generate_with_together(prompt: str, model: str) -> str:
    client = get_together_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior home-services content strategist. "
                    "Return only the complete Markdown blog draft."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.35,
        max_tokens=3400,
    )
    return response.choices[0].message.content.strip()


def generate_mock_draft(sources: list[dict[str, Any]], author_name: str, author_credentials: str) -> str:
    primary = sources[0] if sources else {}
    angle = primary.get("recommended_angle") or "What should Metro Atlanta homeowners check before roof repairs?"
    title = angle.rstrip("?")

    return f"""# {title}

Metro Atlanta homeowners should treat recent roof-safety and insurance news as a reminder to inspect vulnerable roof areas before small issues become expensive claims. Start with visible damage, roof penetrations, attic moisture, and policy details. If you see active leaks, displaced flashing, storm damage, or unsafe exterior conditions, document the issue with photos and schedule a licensed inspection before authorizing repairs.

## What changed in Atlanta roofing and home insurance news?

Recent local reporting points to two practical concerns: building safety and rising home insurance costs. FOX 5 Atlanta reported an unsafe Midtown Atlanta high-rise inspection, while 11Alive shared Consumer Reports guidance that older roofs and storm damage can affect insurance costs (Source: FOX 5 Atlanta, May 2026; Source: 11Alive, May 2026).

## What should homeowners inspect first?

Start with the roof areas most likely to leak: pipe boots, chimney flashing, valleys, skylights, gutters, and attic decking. Homeowners in Fulton, DeKalb, Cobb, Gwinnett, Cherokee, and Chamblee should also check for storm debris, soft decking, and ceiling stains after heavy rain.

| Area to check | What to look for | Why it matters |
|---|---|---|
| Pipe boots | Cracked rubber or lifted sealant | Common leak entry point |
| Flashing | Gaps, rust, or displaced metal | Lets wind-driven rain enter |
| Attic decking | Dark stains or soft wood | Shows hidden moisture |

## How can roof condition affect insurance costs?

Roof age and storm-damage history can affect premiums and claim outcomes. 11Alive reported that Consumer Reports found home insurance costs rose an average of 24% over three years and that some insurers add surcharges of 10 to 20 percent or more for older roofs (Source: 11Alive, May 2026).

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


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "blog-draft"


def first_heading(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "blog-draft"


def output_paths(markdown: str, output_dir: Path) -> tuple[Path, Path]:
    today = date.today().isoformat()
    slug = slugify(first_heading(markdown))
    draft_path = output_dir / f"{today}-{slug}.md"
    report_path = output_dir / f"{today}-{slug}-validation.json"
    return draft_path, report_path


def count_faq_pairs(markdown: str) -> int:
    faq_match = re.search(r"(^##+ FAQ\b.*)", markdown, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
    if not faq_match:
        return 0
    faq_section = faq_match.group(1)
    return len(re.findall(r"^#{3,6}\s+\S.*\?", faq_section, flags=re.MULTILINE))


def validate_draft(markdown: str) -> dict[str, Any]:
    h2s = re.findall(r"^##\s+(.+)$", markdown, flags=re.MULTILINE)
    citations = re.findall(r"\(Source:\s*[^)]+\)", markdown)
    tables = bool(re.search(r"^\|.+\|\s*$", markdown, flags=re.MULTILINE))
    locations = sorted({loc for loc in METRO_LOCATIONS if re.search(rf"\b{re.escape(loc)}\b", markdown)})
    body_without_title = re.sub(r"^# .+\n+", "", markdown).strip()
    opening_match = re.split(r"\n\s*\n|^##\s+", body_without_title, maxsplit=1, flags=re.MULTILINE)
    opening_text = opening_match[0] if opening_match else ""
    opening_words = len(opening_text.split())
    generic_openers = [phrase for phrase in GENERIC_OPENERS if phrase.lower() in markdown[:250].lower()]

    checks = {
        "has_h1": bool(re.search(r"^#\s+\S", markdown, flags=re.MULTILINE)),
        "answer_first_opening_roughly_50_to_120_words": 50 <= opening_words <= 120,
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
        "locations_found": locations,
        "faq_count": count_faq_pairs(markdown),
        "generic_openers_found": generic_openers,
    }


def save_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"[write] Saved {path}")


def save_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[write] Saved {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a GEO blog draft from kept sources.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model", default=os.getenv("TOGETHER_WRITING_MODEL", DEFAULT_MODEL))
    parser.add_argument("--mock", action="store_true", help="Write a local mock draft instead of calling Together AI.")
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    sources = load_json(args.input)
    if not sources:
        raise ValueError(f"No kept sources found in {args.input}. Run search.py and evaluate.py first.")

    author_name = os.getenv("AUTHOR_NAME", DEFAULT_AUTHOR_NAME)
    author_credentials = os.getenv("AUTHOR_CREDENTIALS", DEFAULT_AUTHOR_CREDENTIALS)

    if args.mock:
        draft = generate_mock_draft(sources, author_name, author_credentials)
    else:
        prompt = build_prompt(
            read_text(PROMPT_PATH),
            sources,
            read_text(STYLE_NOTES_PATH),
            author_name,
            author_credentials,
        )
        print(f"[write] Generating draft with {args.model}")
        draft = generate_with_together(prompt, args.model)

    draft_path, report_path = output_paths(draft, args.output_dir)
    report = validate_draft(draft)
    report["generated_at"] = datetime.now().isoformat()
    report["source_count"] = len(sources)
    report["model"] = "mock" if args.mock else args.model
    report["draft_path"] = str(draft_path)

    save_text(draft, draft_path)
    save_json(report, report_path)

    print(f"[write] Validation passed: {report['passed']}")
    if not report["passed"]:
        failed = [name for name, passed in report["checks"].items() if not passed]
        print(f"[write] Failed checks: {', '.join(failed)}")


if __name__ == "__main__":
    main()
