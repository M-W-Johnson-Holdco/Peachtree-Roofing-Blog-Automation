#!/usr/bin/env python3
"""CLI entry: Slack approval workflow."""
from __future__ import annotations

import _entry  # noqa: F401

from peachtree_blog.approve.approve import main

if __name__ == "__main__":
    main()
