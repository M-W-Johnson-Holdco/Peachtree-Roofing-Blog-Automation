#!/usr/bin/env python3
"""CLI entry: strict Tavily source search."""
from __future__ import annotations

import runpy

import _entry  # noqa: F401

runpy.run_module("peachtree_blog.search.search", run_name="__main__")
