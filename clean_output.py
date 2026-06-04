#!/usr/bin/env python3
"""CLI entry: clean generated output directories."""
from __future__ import annotations

import _entry  # noqa: F401

from peachtree_blog.tools.clean_output import main

if __name__ == "__main__":
    main()
