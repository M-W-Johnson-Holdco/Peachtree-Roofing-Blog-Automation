#!/usr/bin/env python3
"""CLI entry: broad Metro Atlanta roofing search."""
from __future__ import annotations

import runpy

import _entry  # noqa: F401

runpy.run_module("peachtree_blog.search.search_all_roofing", run_name="__main__")
