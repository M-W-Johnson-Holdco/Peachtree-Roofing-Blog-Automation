"""Slack approval workflow for generated blog drafts.

Commands:
    python approve.py post --latest
    python approve.py post output/drafts/example.md
    python approve.py listen

Required environment for posting:
    SLACK_BOT_TOKEN
    SLACK_APPROVAL_CHANNEL

Required environment for Socket Mode listening:
    SLACK_APP_TOKEN
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DRAFT_DIR = PROJECT_ROOT / "output" / "drafts"
DEFAULT_APPROVAL_DIR = PROJECT_ROOT / "output" / "approvals"
APPROVE_REACTIONS = {"white_check_mark", "heavy_check_mark"}
REJECT_REACTIONS = {"x", "negative_squared_cross_mark"}
MAX_MAIN_DRAFT_CHARS = 3200
MAX_THREAD_CHUNK_CHARS = 3500


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def save_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[approve] Saved {path}")


def get_slack_client():
    try:
        from slack_sdk import WebClient
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: slack_sdk. Install dependencies with "
            "`python -m pip install -r requirements.txt`."
        ) from exc

    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise EnvironmentError("SLACK_BOT_TOKEN is not set.")
    return WebClient(token=token)


def get_approval_channel() -> str:
    channel = os.getenv("SLACK_APPROVAL_CHANNEL")
    if not channel:
        raise EnvironmentError("SLACK_APPROVAL_CHANNEL is not set.")
    return channel


def latest_draft_path(draft_dir: Path = DEFAULT_DRAFT_DIR) -> Path:
    drafts = sorted(
        path
        for path in draft_dir.glob("*.md")
        if not path.name.endswith("-validation.md")
    )
    if not drafts:
        raise FileNotFoundError(f"No Markdown drafts found in {draft_dir}")
    return drafts[-1]


def approval_path_for_draft(draft_path: Path) -> Path:
    return DEFAULT_APPROVAL_DIR / f"{draft_path.stem}.json"


def title_from_markdown(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Blog draft"


def chunk_text(text: str, limit: int) -> list[str]:
    chunks = []
    remaining = text.strip()
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at < limit // 2:
            split_at = remaining.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = limit

        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    return chunks


def post_draft(draft_path: Path, rewritten_from: str | None = None) -> Path:
    client = get_slack_client()
    channel = get_approval_channel()
    markdown = draft_path.read_text(encoding="utf-8")
    title = title_from_markdown(markdown)
    preview = markdown[:MAX_MAIN_DRAFT_CHARS].strip()
    truncated = len(markdown) > MAX_MAIN_DRAFT_CHARS
    relative_path = draft_path.relative_to(PROJECT_ROOT)

    intro = [
        f"*Blog draft ready for approval:* {title}",
        f"`{relative_path}`",
        "",
        "React to this message with :white_check_mark: to approve or :x: to request revisions.",
    ]
    if rewritten_from:
        intro.insert(1, f"Revision generated from `{rewritten_from}`.")

    text = "\n".join(intro) + f"\n\n```{preview}```"
    if truncated:
        text += "\n\nFull draft continues in this thread."

    response = client.chat_postMessage(channel=channel, text=text)
    if not response.get("ok"):
        raise RuntimeError(f"Slack post failed: {response}")

    message_ts = response["ts"]
    if truncated:
        for index, chunk in enumerate(chunk_text(markdown[MAX_MAIN_DRAFT_CHARS:], MAX_THREAD_CHUNK_CHARS), start=1):
            client.chat_postMessage(
                channel=channel,
                thread_ts=message_ts,
                text=f"*Draft continued {index}:*\n```{chunk}```",
            )

    record = {
        "draft_path": str(relative_path),
        "channel": channel,
        "message_ts": message_ts,
        "status": "pending",
        "posted_at": utc_now(),
        "approved_at": None,
        "approved_by": None,
        "rejected_at": None,
        "rejected_by": None,
        "feedback_requested_at": None,
        "rewritten_from": rewritten_from,
        "revision_draft_path": None,
        "feedback": [],
    }
    approval_path = approval_path_for_draft(draft_path)
    save_json(record, approval_path)
    print(f"[approve] Posted draft to Slack channel {channel} at {message_ts}")
    return approval_path


def find_record_for_message(channel: str, ts: str) -> tuple[Path, dict[str, Any]] | None:
    for path in DEFAULT_APPROVAL_DIR.glob("*.json"):
        record = load_json(path)
        if record.get("channel") == channel and record.get("message_ts") == ts:
            return path, record
    return None


def update_status(path: Path, record: dict[str, Any], status: str, user: str) -> None:
    record["status"] = status
    if status == "approved":
        record["approved_at"] = utc_now()
        record["approved_by"] = user
    elif status == "needs_feedback":
        record["rejected_at"] = utc_now()
        record["rejected_by"] = user
        record["feedback_requested_at"] = utc_now()
    save_json(record, path)


def request_feedback(client: Any, record: dict[str, Any]) -> None:
    client.chat_postMessage(
        channel=record["channel"],
        thread_ts=record["message_ts"],
        text="Got it. Please reply in this thread with the changes you want, and I will save the feedback for a rewrite.",
    )


def append_feedback(path: Path, record: dict[str, Any], user: str, text: str, event_ts: str | None) -> None:
    feedback = record.setdefault("feedback", [])
    if not isinstance(feedback, list):
        feedback = []
        record["feedback"] = feedback

    feedback.append(
        {
            "user": user,
            "text": text.strip(),
            "event_ts": event_ts,
            "created_at": utc_now(),
        }
    )
    record["status"] = "feedback_received"
    save_json(record, path)


def regenerate_from_feedback(record_path: Path, record: dict[str, Any], mock: bool) -> Path:
    command = [sys.executable, "write.py", "--feedback-json", str(record_path)]
    if mock:
        command.append("--mock")

    print(f"[approve] Regenerating draft: {' '.join(command)}")
    completed = subprocess.run(command, cwd=PROJECT_ROOT)
    if completed.returncode != 0:
        raise RuntimeError(f"write.py failed with exit code {completed.returncode}")

    new_draft_path = latest_draft_path()
    record["status"] = "revision_generated"
    record["revision_draft_path"] = str(new_draft_path.relative_to(PROJECT_ROOT))
    record["revision_generated_at"] = utc_now()
    save_json(record, record_path)
    return new_draft_path


def handle_reaction(event: dict[str, Any], client: Any) -> None:
    item = event.get("item", {})
    if item.get("type") != "message":
        return

    channel = item.get("channel")
    ts = item.get("ts")
    reaction = event.get("reaction")
    user = event.get("user", "unknown")
    if not channel or not ts or not reaction:
        return

    found = find_record_for_message(channel, ts)
    if not found:
        return

    path, record = found
    if reaction in APPROVE_REACTIONS:
        update_status(path, record, "approved", user)
        client.chat_postMessage(channel=channel, thread_ts=ts, text=f"Approved by <@{user}>.")
    elif reaction in REJECT_REACTIONS:
        update_status(path, record, "needs_feedback", user)
        request_feedback(client, record)


def handle_message(event: dict[str, Any], client: Any, auto_rewrite: bool, mock: bool) -> None:
    if event.get("subtype") == "bot_message":
        return

    channel = event.get("channel")
    thread_ts = event.get("thread_ts")
    text = str(event.get("text", "")).strip()
    user = event.get("user", "unknown")
    if not channel or not thread_ts or not text:
        return

    found = find_record_for_message(channel, thread_ts)
    if not found:
        return

    path, record = found
    if record.get("status") not in {"needs_feedback", "feedback_received"}:
        return

    append_feedback(path, record, user, text, event.get("event_ts"))
    client.chat_postMessage(channel=channel, thread_ts=thread_ts, text="Feedback saved.")

    if auto_rewrite:
        new_draft_path = regenerate_from_feedback(path, record, mock=mock)
        new_record_path = post_draft(new_draft_path, rewritten_from=str(path.relative_to(PROJECT_ROOT)))
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f"Revision generated and posted for approval: `{new_record_path.relative_to(PROJECT_ROOT)}`",
        )


def listen(auto_rewrite: bool, mock: bool) -> None:
    try:
        from slack_sdk.socket_mode import SocketModeClient
        from slack_sdk.socket_mode.response import SocketModeResponse
    except ImportError as exc:
        raise RuntimeError(
            "Missing Socket Mode dependency from slack_sdk. Install with "
            "`python -m pip install -r requirements.txt`."
        ) from exc

    app_token = os.getenv("SLACK_APP_TOKEN")
    if not app_token:
        raise EnvironmentError("SLACK_APP_TOKEN is not set.")

    web_client = get_slack_client()
    socket_client = SocketModeClient(app_token=app_token, web_client=web_client)

    def process(client: Any, request: Any) -> None:
        if request.type != "events_api":
            return

        client.send_socket_mode_response(SocketModeResponse(envelope_id=request.envelope_id))
        event = request.payload.get("event", {})
        event_type = event.get("type")
        if event_type == "reaction_added":
            handle_reaction(event, web_client)
        elif event_type == "message":
            handle_message(event, web_client, auto_rewrite=auto_rewrite, mock=mock)

    socket_client.socket_mode_request_listeners.append(process)
    print("[approve] Listening for Slack approval reactions and feedback...")
    socket_client.connect()

    import time

    while True:
        time.sleep(60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Post and process Slack approval requests for blog drafts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    post_parser = subparsers.add_parser("post", help="Post a draft to Slack for approval.")
    post_parser.add_argument("draft", nargs="?", type=Path, help="Draft Markdown path to post.")
    post_parser.add_argument("--latest", action="store_true", help="Post the latest Markdown draft from output/drafts.")

    listen_parser = subparsers.add_parser("listen", help="Listen for Slack reactions and feedback with Socket Mode.")
    listen_parser.add_argument(
        "--no-auto-rewrite",
        action="store_true",
        help="Save feedback but do not rerun write.py automatically.",
    )
    listen_parser.add_argument("--mock", action="store_true", help="Use write.py --mock when auto-rewriting.")

    args = parser.parse_args()
    load_dotenv(PROJECT_ROOT / ".env")

    if args.command == "post":
        if args.latest:
            draft_path = latest_draft_path()
        elif args.draft:
            draft_path = args.draft
            if not draft_path.is_absolute():
                draft_path = PROJECT_ROOT / draft_path
        else:
            raise SystemExit("Provide a draft path or use --latest.")

        post_draft(draft_path)
    elif args.command == "listen":
        listen(auto_rewrite=not args.no_auto_rewrite, mock=args.mock)


if __name__ == "__main__":
    main()
