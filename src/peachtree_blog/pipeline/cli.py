"""Pipeline orchestrator and interactive stage picker."""

from __future__ import annotations

import peachtree_blog._pycache_prefix  # noqa: F401

import argparse

from peachtree_blog.pipeline.approve_listen import run_approve_post_and_listen
from peachtree_blog.pipeline.runner import run_module, run_modules
from peachtree_blog.paths import PROJECT_ROOT
from dotenv import load_dotenv

MENU_OPTIONS: list[tuple[str, str]] = [
    ("search", "Search"),
    ("evaluate", "Evaluate sources"),
    ("write", "Write draft (serverless)"),
    ("approve", "Approve (post latest draft to Slack, then listen)"),
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


def ask_mock() -> bool:
    raw = input("Use mock mode? [y/N]: ").strip().lower()
    return raw in {"y", "yes"}


def run_menu_choice(choice: int) -> bool:
    """Run one menu stage. Returns True when approve listen exited via ``e`` (show menu again)."""
    stage_key = MENU_OPTIONS[choice - 1][0]

    if stage_key == "exit":
        print("[pipeline] Exiting.")
        return False

    mock = False
    if stage_key in {"evaluate", "write"}:
        mock = ask_mock()

    if stage_key == "search":
        run_module("search")
    elif stage_key == "evaluate":
        run_module("evaluate", *(["--mock"] if mock else ()))
    elif stage_key == "write":
        run_module("write_serverless", *(["--mock"] if mock else ()))
    elif stage_key == "approve":
        load_dotenv(PROJECT_ROOT / ".env")
        return run_approve_post_and_listen(interactive_model_prompt=True)
    return False


def run_interactive_menu() -> None:
    while True:
        print_stage_menu()
        choice = read_menu_choice()
        if MENU_OPTIONS[choice - 1][0] == "exit":
            print("[pipeline] Exiting.")
            return
        back_to_menu = run_menu_choice(choice)
        if back_to_menu:
            continue
        again = input("\nRun another stage? [y/N]: ").strip().lower()
        if again not in {"y", "yes"}:
            return


def run_full_pipeline(*, mock: bool, send_to_slack: bool) -> None:
    stages: list[tuple[str, tuple[str, ...]]] = [
        ("search", ()),
        ("evaluate", ("--mock",) if mock else ()),
        ("write_serverless", ("--mock",) if mock else ()),
    ]
    if send_to_slack:
        stages.append(("approve_listen", ("post", "--latest")))
    run_modules(stages)
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
        "--mock",
        action="store_true",
        help="With --all: run evaluate and write in mock mode.",
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
        run_full_pipeline(mock=args.mock, send_to_slack=args.send_to_slack)
        return

    if args.stage:
        if args.stage == "search":
            run_module("search")
        elif args.stage == "evaluate":
            run_module("evaluate", *(["--mock"] if args.mock else ()))
        elif args.stage == "write":
            run_module("write_serverless", *(["--mock"] if args.mock else ()))
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
