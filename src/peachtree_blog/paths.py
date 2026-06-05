"""Repository paths shared across the blog automation package."""

from __future__ import annotations

import shutil
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = SRC_DIR.parent

# Single bytecode cache tree under src/ (see peachtree_blog._pycache_prefix).
BYTECODE_CACHE_DIR = SRC_DIR / "__pycache__"


def configure_bytecode_cache() -> Path:
    """Ensure ``PYTHONPYCACHEPREFIX`` points at ``src/__pycache__/``."""
    from peachtree_blog._pycache_prefix import apply

    return apply()


# Empty dirs left after moving stages into peachtree_blog/pipeline/.
LEGACY_PACKAGE_DIR_NAMES = ("approve", "evaluate", "search", "write")


def remove_legacy_package_dirs() -> list[Path]:
    """Delete obsolete approve/search/write/evaluate folders under peachtree_blog."""
    removed: list[Path] = []
    for name in LEGACY_PACKAGE_DIR_NAMES:
        path = PACKAGE_DIR / name
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(path)
    return removed


PROMPTS_DIR = PROJECT_ROOT / "prompts"
FEEDBACK_DIR = PROJECT_ROOT / "feedback"
OUTPUT_DIR = PROJECT_ROOT / "output"
SOURCES_DIR = OUTPUT_DIR / "sources"
DRAFTS_DIR = OUTPUT_DIR / "drafts"
APPROVALS_DIR = OUTPUT_DIR / "approvals"
