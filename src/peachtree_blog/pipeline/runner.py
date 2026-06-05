"""Run pipeline stages from ``src/peachtree_blog`` via ``python -m``."""

from __future__ import annotations

from peachtree_blog.paths import BYTECODE_CACHE_DIR, PROJECT_ROOT, SRC_DIR

import os
import subprocess
import sys
from typing import Sequence

# Keys used by pipeline.py and approve subprocess rewrites.
PIPELINE_MODULES: dict[str, str] = {
    "search": "peachtree_blog.pipeline.search",
    "evaluate": "peachtree_blog.pipeline.evaluate",
    "write_serverless": "peachtree_blog.pipeline.write_serverless",
    "approve_listen": "peachtree_blog.pipeline.approve_listen",
    "post": "peachtree_blog.post",
    "clean_output": "peachtree_blog.tools.clean_output",
}

DEFAULT_REWRITE_MODULE_KEY = "write_serverless"


def module_name(module_key: str) -> str:
    try:
        return PIPELINE_MODULES[module_key]
    except KeyError as exc:
        raise ValueError(f"Unknown pipeline module key: {module_key}") from exc


def pipeline_subprocess_env() -> dict[str, str]:
    """Environment for child processes so ``peachtree_blog`` imports resolve."""
    cache_dir = BYTECODE_CACHE_DIR.resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(cache_dir)
    src = str(SRC_DIR)
    existing = env.get("PYTHONPATH", "")
    if src not in existing.split(os.pathsep):
        env["PYTHONPATH"] = src if not existing else f"{src}{os.pathsep}{existing}"
    return env


def build_module_command(module_key: str, *args: str) -> list[str]:
    """Argv to run a package module from the repo root (``PYTHONPATH=src``)."""
    return [sys.executable, "-m", module_name(module_key), *args]


def run_module(module_key: str, *args: str, label: str | None = None) -> int:
    command = build_module_command(module_key, *args)
    stage_label = label or module_key
    print(f"[pipeline] Starting {stage_label}: {' '.join(command)}")
    completed = subprocess.run(command, cwd=PROJECT_ROOT, env=pipeline_subprocess_env())
    if completed.returncode != 0:
        print(f"[pipeline] {stage_label} failed with exit code {completed.returncode}")
    else:
        print(f"[pipeline] Finished {stage_label}")
    return completed.returncode


def run_modules(stages: Sequence[tuple[str, tuple[str, ...]]]) -> None:
    for module_key, args in stages:
        code = run_module(module_key, *args)
        if code != 0:
            raise SystemExit(code)
