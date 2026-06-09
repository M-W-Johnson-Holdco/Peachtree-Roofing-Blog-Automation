"""Pipeline orchestrator and interactive stage picker."""

from __future__ import annotations

import peachtree_blog._pycache_prefix  # noqa: F401

import argparse

from peachtree_blog.pipeline.approve_listen import run_approve_post_and_listen
from peachtree_blog.pipeline.runner import run_module, run_modules, run_pipeline_restart
from peachtree_blog.paths import PROJECT_ROOT
from dotenv import load_dotenv

MENU_OPTIONS: list[tuple[str, str]] = [
    ("search", "Search"),
    ("evaluate", "Evaluate sources"),
    ("write", "Write draft (serverless)"),
    ("approve", "Approve (post latest draft to Slack, then listen)"),
    ("full", "Full pipeline (search → evaluate → write → approve)"),
    ("exit", "Exit"),
]


def print_stage_menu() -> None:
    print("\nSelect part of the pipeline you want to initiate:\n")
    for index, (_, label) in enumerate(MENU_OPTIONS, start=1):
        print(f"  {index}. {label}")
    print()


def read_menu_choice() -> int:
    while True:
        raw = input("Enter number: ").strip()
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(MENU_OPTIONS):
                return choice
        print(f"Please enter a number from 1 to {len(MENU_OPTIONS)}.")


def run_full_pipeline_and_approve() -> None:
    """search → evaluate → write, then post to Slack and listen for approval."""
    load_dotenv(PROJECT_ROOT / ".env")
    code = run_pipeline_restart()
    if code != 0:
        print("[pipeline] Stopped before approve — fix the failed stage and try again.")
        return
    run_approve_post_and_listen(interactive_model_prompt=True)


def run_menu_choice(choice: int) -> None:
    """Run one menu stage, then return so the interactive menu can show again."""
    stage_key = MENU_OPTIONS[choice - 1][0]

    if stage_key == "search":
        run_module("search")
    elif stage_key == "evaluate":
        run_module("evaluate")
    elif stage_key == "write":
        run_module("write_serverless")
    elif stage_key == "approve":
        load_dotenv(PROJECT_ROOT / ".env")
        run_approve_post_and_listen(interactive_model_prompt=True)
    elif stage_key == "full":
        run_full_pipeline_and_approve()


def run_interactive_menu() -> None:
    while True:
        print_stage_menu()
        choice = read_menu_choice()
        if MENU_OPTIONS[choice - 1][0] == "exit":
            print("[pipeline] Exiting.")
            return
        run_menu_choice(choice)


def run_full_pipeline(*, send_to_slack: bool) -> None:
    # run_pipeline_restart uses incremental search+evaluate by default.
    code = run_pipeline_restart()
    if code != 0:
        raise SystemExit(code)
    if send_to_slack:
        run_module("approve_listen", "post", "--latest")
    print("[pipeline] Pipeline completed successfully")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Peachtree blog pipeline — interactive menu by default."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run full pipeline non-interactively: search → evaluate → write (for CI/scripts).",
    )
    parser.add_argument(
        "--send-to-slack",
        action="store_true",
        help="With --all: post the draft to Slack after writing.",
    )
    parser.add_argument(
        "--stage",
        choices=("search", "evaluate", "write", "approve_post", "approve_listen", "clean"),
        help="Run one stage non-interactively (skips the menu).",
    )
    args = parser.parse_args(argv)

    if args.all:
        run_full_pipeline(send_to_slack=args.send_to_slack)
        return

    if args.stage:
        if args.stage == "search":
            run_module("search")
        elif args.stage == "evaluate":
            run_module("evaluate")
        elif args.stage == "write":
            run_module("write_serverless")
        elif args.stage == "approve_post":
            run_module("approve_listen", "post", "--latest")
        elif args.stage == "approve_listen":
            run_module("approve_listen")
        elif args.stage == "clean":
            run_module("clean_output")
        return

    run_interactive_menu()


if __name__ == "__main__":
    main()
