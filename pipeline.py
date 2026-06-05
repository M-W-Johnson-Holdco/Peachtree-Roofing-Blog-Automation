#!/usr/bin/env python3
"""Peachtree blog pipeline entry point (runs stages from src/peachtree_blog).

Examples:
    python pipeline.py              # interactive menu (default)
    python pipeline.py --all          # search → evaluate → write (CI)
    python pipeline.py --stage write
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
_cache = _SRC / "__pycache__"
_cache.mkdir(parents=True, exist_ok=True)
os.environ["PYTHONPYCACHEPREFIX"] = str(_cache.resolve())
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from peachtree_blog.paths import remove_legacy_package_dirs

for _legacy in remove_legacy_package_dirs():
    pass  # cleanup empty approve/search/write/evaluate dirs from old layout

from peachtree_blog.pipeline.cli import main

if __name__ == "__main__":
    main()
