"""Weekly-rotating blog writing prompt variants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from peachtree_blog.paths import PROJECT_ROOT, PROMPTS_DIR

DEFAULT_WRITING_PROMPT_ID = "geo"
SUMMARY_HEADING_WHO = "Who this affects"
SUMMARY_HEADING_WHAT = "What to do"
SUMMARY_HEADING_WHEN = "Timeline"


@dataclass(frozen=True)
class WritingPromptVariant:
    id: str
    label: str
    path: Path
    summary_heading: str
    opening_style: str

    @property
    def summary_heading_markdown(self) -> str:
        return f"**{self.summary_heading}:**"


WRITING_PROMPT_VARIANTS: tuple[WritingPromptVariant, ...] = (
    WritingPromptVariant(
        id="geo",
        label="GEO news + Quick Answer",
        path=PROMPTS_DIR / "blog.txt",
        summary_heading="The short answer",
        opening_style="news-anchored",
    ),
    WritingPromptVariant(
        id="scenario",
        label="Scenario-led vignette",
        path=PROMPTS_DIR / "blog_scenario.txt",
        summary_heading="The short answer",
        opening_style="scenario-led",
    ),
    WritingPromptVariant(
        id="explainer",
        label="Definition-first explainer",
        path=PROMPTS_DIR / "blog_explainer.txt",
        summary_heading="The short answer",
        opening_style="definition-first",
    ),
)

_VARIANT_BY_ID = {variant.id: variant for variant in WRITING_PROMPT_VARIANTS}


def writing_prompt_variant_ids() -> tuple[str, ...]:
    return tuple(variant.id for variant in WRITING_PROMPT_VARIANTS)


def get_writing_prompt_variant(variant_id: str) -> WritingPromptVariant:
    key = str(variant_id or "").strip().lower()
    try:
        return _VARIANT_BY_ID[key]
    except KeyError as exc:
        known = ", ".join(writing_prompt_variant_ids())
        raise ValueError(f"Unknown writing prompt {variant_id!r}. Choose one of: {known}") from exc


def select_writing_prompt_variant(
    *,
    rotation_week: int | None = None,
    variant_id: str | None = None,
) -> WritingPromptVariant:
    if variant_id and str(variant_id).strip().lower() not in {"", "auto"}:
        return get_writing_prompt_variant(variant_id)

    week = rotation_week or datetime.now(timezone.utc).isocalendar().week
    index = (week - 1) % len(WRITING_PROMPT_VARIANTS)
    return WRITING_PROMPT_VARIANTS[index]


def describe_writing_prompt_rotation(*, rotation_week: int | None = None) -> str:
    """Human-readable note for logs: which template this ISO week maps to."""
    week = rotation_week or datetime.now(timezone.utc).isocalendar().week
    variant = select_writing_prompt_variant(rotation_week=week)
    return f"ISO week {week} → {variant.id} ({variant.label})"


def load_writing_prompt_text(variant: WritingPromptVariant) -> str:
    if not variant.path.is_file():
        raise FileNotFoundError(f"Writing prompt not found: {variant.path.relative_to(PROJECT_ROOT)}")
    return variant.path.read_text(encoding="utf-8")


def writing_prompt_metadata(variant: WritingPromptVariant) -> dict[str, str]:
    return {
        "id": variant.id,
        "label": variant.label,
        "path": str(variant.path.relative_to(PROJECT_ROOT)),
        "summary_heading": variant.summary_heading,
        "opening_style": variant.opening_style,
    }
