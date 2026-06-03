"""Post the latest draft PDF to Slack and start the approval listener (Qwen3.5 397B rewrites).

Expects the latest draft in `output/drafts/drafts_md/` to already have a matching `.pdf`
in `output/drafts/drafts_pdf/` from `write_serverless_qwen397b.py`.

Run live:
    python approve_listen_qwen397b.py

Save feedback without auto-rewrite:
    python approve_listen_qwen397b.py --no-auto-rewrite

Use mock rewrites:
    python approve_listen_qwen397b.py --mock
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from approve import PROJECT_ROOT, latest_draft_path, listen, post_draft, prepare_new_approval_post

REWRITE_SCRIPT = "write_serverless_qwen397b.py"
LOG_PREFIX = "approve_listen_qwen397b"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Post the latest blog draft to Slack and listen for approval reactions (Qwen 397B rewrites)."
    )
    parser.add_argument(
        "--no-auto-rewrite",
        action="store_true",
        help=f"Save thread feedback without rerunning {REWRITE_SCRIPT}.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help=f"Use {REWRITE_SCRIPT} --mock when auto-rewriting after feedback.",
    )
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    draft_path = latest_draft_path()
    print(f"[{LOG_PREFIX}] Using latest draft: {draft_path.relative_to(PROJECT_ROOT)}")
    print(f"[{LOG_PREFIX}] Auto-rewrite script: {REWRITE_SCRIPT}")
    prepare_new_approval_post()
    post_draft(draft_path)
    listen(
        auto_rewrite=not args.no_auto_rewrite,
        mock=args.mock,
        rewrite_script=REWRITE_SCRIPT,
    )


if __name__ == "__main__":
    main()
