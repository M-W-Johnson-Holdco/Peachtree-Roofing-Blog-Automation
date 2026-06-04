#!/usr/bin/env python3
"""CLI entry: less strict Tavily source search."""
from __future__ import annotations

import runpy

import _entry  # noqa: F401

runpy.run_module("peachtree_blog.search.search_less_strict", run_name="__main__")
