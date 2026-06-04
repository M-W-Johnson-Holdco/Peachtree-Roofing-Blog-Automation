"""Slack approval workflow for generated blog drafts.

Commands:
    python approve.py post --latest
    python approve.py post output/drafts/drafts_md/example.md
    python approve.py listen

Posting uploads the existing PDF from `output/drafts/drafts_pdf/` (matching stem as the `.md`
file in `output/drafts/drafts_md/`). Run `write.py` or `write_serverless.py` first to generate the PDF.

Required environment for posting:
    SLACK_APPROVAL_BOT_TOKEN
    SLACK_APPROVAL_CHANNEL

Required environment for Socket Mode listening:
    SLACK_APPROVAL_TOKEN
"""

from __future__ import annotations

from peachtree_blog.paths import PROJECT_ROOT

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from peachtree_blog.write_common import (
    DEFAULT_OUTPUT_DIR,
    draft_pdf_path,
    latest_markdown_draft,
    update_record_revision_mode,
)



DEFAULT_DRAFT_DIR = DEFAULT_OUTPUT_DIR
DEFAULT_APPROVAL_DIR = PROJECT_ROOT / "output" / "approvals"
REWRITE_SCRIPT = "write_serverless.py"
APPROVE_REACTIONS = {"white_check_mark", "heavy_check_mark"}
REJECT_REACTIONS = {"x", "negative_squared_cross_mark"}
IGNORE_MESSAGE_SUBTYPES = {
    "bot_message",
    "message_changed",
    "message_deleted",
    "channel_join",
    "channel_leave",
    "file_share",
    "file_comment",
}


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

    token = os.getenv("SLACK_APPROVAL_BOT_TOKEN")
    if not token:
        raise EnvironmentError("SLACK_APPROVAL_BOT_TOKEN is not set.")
    return WebClient(token=token)


def get_approval_channel() -> str:
    channel = os.getenv("SLACK_APPROVAL_CHANNEL")
    if not channel:
        raise EnvironmentError("SLACK_APPROVAL_CHANNEL is not set.")
    return channel


def latest_draft_path(draft_dir: Path = DEFAULT_DRAFT_DIR) -> Path:
    return latest_markdown_draft(draft_dir)


def approval_path_for_draft(draft_path: Path) -> Path:
    return DEFAULT_APPROVAL_DIR / f"{draft_path.stem}.json"


def clear_approvals_directory(approval_dir: Path = DEFAULT_APPROVAL_DIR) -> list[Path]:
    """Remove existing approval JSON files before a new approval post."""
    approval_dir.mkdir(parents=True, exist_ok=True)
    removed: list[Path] = []
    for path in sorted(approval_dir.iterdir()):
        if path.is_file():
            path.unlink()
            removed.append(path)
    return removed


def prepare_new_approval_post() -> None:
    removed = clear_approvals_directory()
    if removed:
        print(f"[approve] Cleared {len(removed)} file(s) from {DEFAULT_APPROVAL_DIR}")


def title_from_markdown(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Blog draft"


def build_approval_intro(
    title: str,
    relative_path: Path,
    pdf_relative_path: Path,
    rewritten_from: str | None,
) -> str:
    intro = [
        f"*Blog draft ready for approval:* {title}",
        f"`{relative_path}`",
        f"PDF: `{pdf_relative_path}`",
        "",
    ]
    if rewritten_from:
        intro.insert(1, f"Revision generated from `{rewritten_from}`.")
    intro.append("The draft PDF is attached in this thread.")
    intro.append("")
    intro.append("React to this message with :white_check_mark: to approve or :x: to request revisions.")
    return "\n".join(intro)


def get_bot_user_id(client: Any) -> str | None:
    response = client.auth_test()
    if not response.get("ok"):
        print(f"[approve] Warning: auth_test failed: {response}")
        return None
    return response.get("user_id")


def add_approval_prompt_reactions(client: Any, channel: str, message_ts: str) -> None:
    for name in ("white_check_mark", "x"):
        response = client.reactions_add(channel=channel, timestamp=message_ts, name=name)
        if response.get("ok"):
            print(f"[approve] Added :{name}: reaction prompt on message {message_ts}")
        else:
            print(f"[approve] Warning: Could not add :{name}: reaction: {response}")


def upload_draft_pdf(client: Any, channel: str, thread_ts: str, pdf_path: Path, title: str) -> bool:
    response = client.files_upload_v2(
        channel=channel,
        file=str(pdf_path),
        thread_ts=thread_ts,
        title=title,
        filename=pdf_path.name,
    )
    if response.get("ok"):
        print(f"[approve] Uploaded PDF {pdf_path.name} to thread {thread_ts}")
        return True

    print(f"[approve] Warning: PDF upload failed: {response}")
    return False


def post_draft(draft_path: Path, rewritten_from: str | None = None) -> Path:
    client = get_slack_client()
    channel = get_approval_channel()
    pdf_path = draft_pdf_path(draft_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(
            f"No PDF found for {draft_path.relative_to(PROJECT_ROOT)}. "
            f"Expected {pdf_path.relative_to(PROJECT_ROOT)}. "
            "Run write.py or write_serverless.py first."
        )

    markdown = draft_path.read_text(encoding="utf-8")
    title = title_from_markdown(markdown)
    relative_path = draft_path.relative_to(PROJECT_ROOT)
    pdf_relative_path = pdf_path.relative_to(PROJECT_ROOT)
    text = build_approval_intro(title, relative_path, pdf_relative_path, rewritten_from)

    response = client.chat_postMessage(channel=channel, text=text)
    if not response.get("ok"):
        raise RuntimeError(f"Slack post failed: {response}")

    message_ts = response["ts"]
    if not upload_draft_pdf(client, channel, message_ts, pdf_path, title):
        raise RuntimeError(f"Slack PDF upload failed for {pdf_path.name}")

    record = {
        "draft_path": str(relative_path),
        "pdf_path": str(pdf_relative_path),
        "post_format": "pdf",
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
    add_approval_prompt_reactions(client, channel, message_ts)
    print(f"[approve] Posted draft PDF to Slack channel {channel} at {message_ts}")
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
        record["rejected_at"] = None
        record["rejected_by"] = None
        record["feedback_requested_at"] = None
    elif status == "needs_feedback":
        record["rejected_at"] = utc_now()
        record["rejected_by"] = user
        record["feedback_requested_at"] = utc_now()
        record["approved_at"] = None
        record["approved_by"] = None
    save_json(record, path)


def clear_approval_status(path: Path, record: dict[str, Any]) -> None:
    record["status"] = "pending"
    record["approved_at"] = None
    record["approved_by"] = None
    save_json(record, path)


def clear_rejection_status(path: Path, record: dict[str, Any]) -> None:
    record["status"] = "pending"
    record["rejected_at"] = None
    record["rejected_by"] = None
    record["feedback_requested_at"] = None
    save_json(record, path)


def request_feedback(client: Any, record: dict[str, Any]) -> None:
    client.chat_postMessage(
        channel=record["channel"],
        thread_ts=record["message_ts"],
        text=(
            "Got it. Please reply in this thread with the changes you want.\n"
            "Start with `edit:` for wording/structure fixes, or `sources:` if you need "
            "new stats/citations from the articles."
        ),
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
    update_record_revision_mode(record)
    save_json(record, path)


def regenerate_from_feedback(
    record_path: Path,
    record: dict[str, Any],
    mock: bool,
    *,
    rewrite_script: str = REWRITE_SCRIPT,
    rewrite_model: str | None = None,
) -> Path:
    command = [sys.executable, rewrite_script, "--feedback-json", str(record_path)]
    if rewrite_model:
        command.extend(["--model", rewrite_model])
    if mock:
        command.append("--mock")

    print(f"[approve] Regenerating draft: {' '.join(command)}")
    completed = subprocess.run(command, cwd=PROJECT_ROOT)
    if completed.returncode != 0:
        raise RuntimeError(f"{rewrite_script} failed with exit code {completed.returncode}")

    new_draft_path = latest_draft_path()
    record["status"] = "revision_generated"
    record["revision_draft_path"] = str(new_draft_path.relative_to(PROJECT_ROOT))
    record["revision_generated_at"] = utc_now()
    save_json(record, record_path)
    return new_draft_path


def handle_reaction(event: dict[str, Any], client: Any, bot_user_id: str | None = None) -> None:
    item = event.get("item", {})
    if item.get("type") != "message":
        return

    channel = item.get("channel")
    ts = item.get("ts")
    reaction = event.get("reaction")
    user = event.get("user", "unknown")
    if not channel or not ts or not reaction:
        return

    if bot_user_id and user == bot_user_id:
        return

    found = find_record_for_message(channel, ts)
    if not found:
        return

    path, record = found
    status = record.get("status", "pending")

    if reaction in APPROVE_REACTIONS:
        if status in {"feedback_received", "revision_generated"}:
            print(f"[approve] Ignoring approval reaction; status is {status}")
            return
        previously_approved = status == "approved"
        update_status(path, record, "approved", user)
        print(f"[approve] Draft approved by {user}")
        if previously_approved:
            print(f"[approve] Updated approval record at {path}")
        else:
            client.chat_postMessage(channel=channel, thread_ts=ts, text=f"Approved by <@{user}>.")
    elif reaction in REJECT_REACTIONS:
        if status in {"needs_feedback", "feedback_received", "revision_generated"}:
            print(f"[approve] Ignoring revision reaction; status is {status}")
            return
        update_status(path, record, "needs_feedback", user)
        print(f"[approve] Revision requested by {user}")
        request_feedback(client, record)


def handle_reaction_removed(event: dict[str, Any], client: Any, bot_user_id: str | None = None) -> None:
    item = event.get("item", {})
    if item.get("type") != "message":
        return

    channel = item.get("channel")
    ts = item.get("ts")
    reaction = event.get("reaction")
    user = event.get("user", "unknown")
    if not channel or not ts or not reaction:
        return

    if bot_user_id and user == bot_user_id:
        return

    found = find_record_for_message(channel, ts)
    if not found:
        return

    path, record = found
    status = record.get("status", "pending")

    if reaction in APPROVE_REACTIONS:
        if status != "approved":
            return
        if record.get("approved_by") != user:
            print(f"[approve] Ignoring approval removal from {user}; approver is {record.get('approved_by')}")
            return
        clear_approval_status(path, record)
        print(f"[approve] Approval removed by {user}; status reset to pending")
        client.chat_postMessage(
            channel=channel,
            thread_ts=ts,
            text=f"Approval removed by <@{user}>. Status reset to pending.",
        )
    elif reaction in REJECT_REACTIONS:
        if status != "needs_feedback":
            return
        if record.get("rejected_by") != user:
            print(f"[approve] Ignoring revision removal from {user}; rejector is {record.get('rejected_by')}")
            return
        clear_rejection_status(path, record)
        print(f"[approve] Revision request removed by {user}; status reset to pending")
        client.chat_postMessage(
            channel=channel,
            thread_ts=ts,
            text=f"Revision request removed by <@{user}>. Status reset to pending.",
        )


def is_human_thread_reply(event: dict[str, Any], bot_user_id: str | None) -> bool:
    subtype = event.get("subtype")
    if subtype in IGNORE_MESSAGE_SUBTYPES:
        return False
    if event.get("bot_id") or event.get("app_id"):
        return False

    user = event.get("user")
    if not user:
        return False
    if bot_user_id and user == bot_user_id:
        return False

    return bool(str(event.get("text", "")).strip())


def handle_message(
    event: dict[str, Any],
    client: Any,
    auto_rewrite: bool,
    mock: bool,
    bot_user_id: str | None = None,
    *,
    rewrite_script: str = REWRITE_SCRIPT,
    rewrite_model: str | None = None,
) -> None:
    if not is_human_thread_reply(event, bot_user_id):
        return

    channel = event.get("channel")
    thread_ts = event.get("thread_ts")
    text = str(event.get("text", "")).strip()
    user = event.get("user", "unknown")
    if not channel or not thread_ts:
        return

    found = find_record_for_message(channel, thread_ts)
    if not found:
        return

    path, record = found
    if record.get("status") != "needs_feedback":
        return

    append_feedback(path, record, user, text, event.get("event_ts"))
    mode = record.get("revision_mode", "editorial")
    client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=f"Feedback saved ({mode} revision).",
    )

    if auto_rewrite:
        new_draft_path = regenerate_from_feedback(
            path,
            record,
            mock=mock,
            rewrite_script=rewrite_script,
            rewrite_model=rewrite_model,
        )
        new_record_path = post_draft(new_draft_path, rewritten_from=str(path.relative_to(PROJECT_ROOT)))
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f"Revision generated and posted for approval: `{new_record_path.relative_to(PROJECT_ROOT)}`",
        )


def listen(
    auto_rewrite: bool,
    mock: bool,
    *,
    rewrite_script: str = REWRITE_SCRIPT,
    rewrite_model: str | None = None,
) -> None:
    try:
        from slack_sdk.socket_mode import SocketModeClient
        from slack_sdk.socket_mode.response import SocketModeResponse
    except ImportError as exc:
        raise RuntimeError(
            "Missing Socket Mode dependency from slack_sdk. Install with "
            "`python -m pip install -r requirements.txt`."
        ) from exc

    app_token = os.getenv("SLACK_APPROVAL_TOKEN")
    if not app_token:
        raise EnvironmentError("SLACK_APPROVAL_TOKEN is not set.")

    web_client = get_slack_client()
    bot_user_id = get_bot_user_id(web_client)
    socket_client = SocketModeClient(app_token=app_token, web_client=web_client)

    def process(client: Any, request: Any) -> None:
        if request.type != "events_api":
            return

        client.send_socket_mode_response(SocketModeResponse(envelope_id=request.envelope_id))
        event = request.payload.get("event", {})
        event_type = event.get("type")
        if event_type == "reaction_added":
            handle_reaction(event, web_client, bot_user_id=bot_user_id)
        elif event_type == "reaction_removed":
            handle_reaction_removed(event, web_client, bot_user_id=bot_user_id)
        elif event_type == "message":
            handle_message(
                event,
                web_client,
                auto_rewrite=auto_rewrite,
                mock=mock,
                bot_user_id=bot_user_id,
                rewrite_script=rewrite_script,
                rewrite_model=rewrite_model,
            )

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
    post_parser.add_argument(
        "--then-listen",
        action="store_true",
        help="After posting, start the Socket Mode listener for reactions and feedback.",
    )
    post_parser.add_argument(
        "--no-auto-rewrite",
        action="store_true",
        help="When used with --then-listen, save feedback without rerunning write_serverless.py.",
    )
    post_parser.add_argument(
        "--mock",
        action="store_true",
        help="When used with --then-listen, use write_serverless.py --mock for auto-rewrites.",
    )

    listen_parser = subparsers.add_parser("listen", help="Listen for Slack reactions and feedback with Socket Mode.")
    listen_parser.add_argument(
        "--no-auto-rewrite",
        action="store_true",
        help="Save feedback but do not rerun write_serverless.py automatically.",
    )
    listen_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use write_serverless.py --mock when auto-rewriting.",
    )

    args = parser.parse_args()
    load_dotenv(PROJECT_ROOT / ".env")

    if args.command == "post":
        prepare_new_approval_post()
        if args.latest:
            draft_path = latest_draft_path()
        elif args.draft:
            draft_path = args.draft
            if not draft_path.is_absolute():
                draft_path = PROJECT_ROOT / draft_path
        else:
            raise SystemExit("Provide a draft path or use --latest.")

        post_draft(draft_path)
        if args.then_listen:
            listen(auto_rewrite=not args.no_auto_rewrite, mock=args.mock)
    elif args.command == "listen":
        listen(auto_rewrite=not args.no_auto_rewrite, mock=args.mock)


if __name__ == "__main__":
    main()
