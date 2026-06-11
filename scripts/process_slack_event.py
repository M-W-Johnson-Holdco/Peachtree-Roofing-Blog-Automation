"""Process one Slack event in GitHub Actions (Cloudflare Worker dispatches this workflow)."""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from peachtree_blog.paths import GENERATED_DIR, PROJECT_ROOT, SOURCES_DIR
from peachtree_blog.slack_actions.processor import (
    decode_event_from_github_input,
    process_slack_event,
    should_process_slack_event,
)


def main(argv: list[str] | None = None) -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser(description="Process a Slack Events API payload.")
    parser.add_argument("--event-b64", default=os.getenv("SLACK_EVENT_B64", "").strip(), help="Base64 Slack event JSON")
    parser.add_argument("--event-json", default="", help="Raw Slack event JSON string")
    parser.add_argument(
        "--no-auto-rewrite",
        action="store_true",
        help="Do not auto-rewrite from thread feedback (not recommended in Actions)",
    )
    args = parser.parse_args(argv)

    if args.event_b64:
        event = decode_event_from_github_input(args.event_b64)
    elif args.event_json:
        event = json.loads(args.event_json)
    elif not sys.stdin.isatty():
        event = json.load(sys.stdin)
    else:
        raise SystemExit("Provide --event-b64, --event-json, or stdin JSON.")

    if not should_process_slack_event(event):
        print(json.dumps({"changed": False, "skipped": True}))
        return

    changed = process_slack_event(event, auto_rewrite=not args.no_auto_rewrite)
    print(
        json.dumps(
            {
                "changed": changed,
                "skipped": False,
                "commit_paths": [
                    str(GENERATED_DIR.relative_to(PROJECT_ROOT)),
                    str((SOURCES_DIR / "used_sources.json").relative_to(PROJECT_ROOT)),
                ],
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[process_slack_event] Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
