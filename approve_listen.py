#!/usr/bin/env python3
"""CLI entry: post latest draft to Slack and listen for approval."""
from __future__ import annotations

import _entry  # noqa: F401

from peachtree_blog.approve.approve_listen import main

if __name__ == "__main__":
    main()
