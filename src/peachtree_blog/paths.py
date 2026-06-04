"""Repository paths shared across the blog automation package."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = SRC_DIR.parent

PROMPTS_DIR = PROJECT_ROOT / "prompts"
FEEDBACK_DIR = PROJECT_ROOT / "feedback"
OUTPUT_DIR = PROJECT_ROOT / "output"
SOURCES_DIR = OUTPUT_DIR / "sources"
DRAFTS_DIR = OUTPUT_DIR / "drafts"
APPROVALS_DIR = OUTPUT_DIR / "approvals"
