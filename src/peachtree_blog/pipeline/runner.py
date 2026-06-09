"""Run pipeline stages from ``src/peachtree_blog`` via ``python -m``."""

from __future__ import annotations

from peachtree_blog.paths import BYTECODE_CACHE_DIR, PROJECT_ROOT, SRC_DIR

import os
import subprocess
import sys
from datetime import datetime, timezone
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
    env["PYTHONUNBUFFERED"] = "1"
    src = str(SRC_DIR)
    existing = env.get("PYTHONPATH", "")
    if src not in existing.split(os.pathsep):
        env["PYTHONPATH"] = src if not existing else f"{src}{os.pathsep}{existing}"
    return env


def build_module_command(module_key: str, *args: str) -> list[str]:
    """Argv to run a package module from the repo root (``PYTHONPATH=src``)."""
    return [sys.executable, "-u", "-m", module_name(module_key), *args]


STAGE_BANNER_WIDTH = 60


def print_stage_banner(*, stage_index: int, stage_total: int, label: str) -> None:
    line = "=" * STAGE_BANNER_WIDTH
    print(f"\n{line}", flush=True)
    print(f"[pipeline] Stage {stage_index}/{stage_total}: {label}", flush=True)
    print(line, flush=True)


def run_module(module_key: str, *args: str, label: str | None = None) -> int:
    command = build_module_command(module_key, *args)
    stage_label = label or module_key
    print(f"[pipeline] Running {stage_label}...", flush=True)
    print(f"[pipeline] Command: {' '.join(command)}", flush=True)
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=pipeline_subprocess_env(),
    )
    if completed.returncode != 0:
        print(f"[pipeline] {stage_label} failed (exit {completed.returncode})", flush=True)
    else:
        print(f"[pipeline] {stage_label} finished", flush=True)
    return completed.returncode


def run_modules(stages: Sequence[tuple[str, tuple[str, ...]]]) -> None:
    for module_key, args in stages:
        code = run_module(module_key, *args)
        if code != 0:
            raise SystemExit(code)


def run_pipeline_restart(
    *,
    write_model: str | None = None,
    clear_drafts: bool = True,
    preferred_cluster: str | None = None,
    rotation_offset: int = 1,
) -> int:
    """Run incremental search+evaluate → write_serverless. Returns last stage exit code."""
    search_args: list[str] = []
    if preferred_cluster:
        search_args.extend(["--preferred-cluster", preferred_cluster])
    if rotation_offset:
        week = datetime.now(timezone.utc).isocalendar().week + rotation_offset
        search_args.extend(["--rotation-week", str(week)])

    write_args: list[str] = []
    if clear_drafts:
        write_args.append("--clear-drafts")
    if write_model:
        write_args.extend(["--model", write_model])

    search_args = list(search_args)
    if "--incremental-evaluate" not in search_args and "--no-incremental-evaluate" not in search_args:
        search_args.append("--incremental-evaluate")

    stages: list[tuple[str, tuple[str, ...], str]] = [
        ("search", tuple(search_args), "Search + evaluate (incremental)"),
        ("write_serverless", tuple(write_args), "Write draft"),
    ]

    line = "=" * STAGE_BANNER_WIDTH
    print(f"\n{line}", flush=True)
    print("[pipeline] Full restart: search+evaluate → write", flush=True)
    if preferred_cluster:
        print(f"[pipeline] Preferred cluster: {preferred_cluster}", flush=True)
    print(line, flush=True)

    for index, (module_key, module_args, label) in enumerate(stages, start=1):
        print_stage_banner(stage_index=index, stage_total=len(stages), label=label)
        if run_module(module_key, *module_args, label=label) != 0:
            print(f"\n[pipeline] Stopped after failed stage: {label}", flush=True)
            return 1

    print(f"\n{line}", flush=True)
    print("[pipeline] Full restart completed successfully", flush=True)
    print(f"{line}\n", flush=True)
    return 0
