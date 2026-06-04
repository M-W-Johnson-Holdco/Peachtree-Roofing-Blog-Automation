#!/usr/bin/env python3
"""CLI entry: generate a blog draft (serverless Together models)."""
from __future__ import annotations

import _entry  # noqa: F401

from peachtree_blog.write.write_serverless import main

if __name__ == "__main__":
    main()
