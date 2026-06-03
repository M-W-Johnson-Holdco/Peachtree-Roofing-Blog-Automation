"""Post the latest draft PDF to Slack and start the approval listener.

Expects the latest draft in `output/drafts/drafts_md/` to already have a matching `.pdf`
in `output/drafts/drafts_pdf/` from `write.py` or `write_serverless.py`.

Shortcut for:
    python approve.py post --latest --then-listen

Run live:
    python approve_listen.py

Save feedback without auto-rewrite:
    python approve_listen.py --no-auto-rewrite

Use mock rewrites:
    python approve_listen.py --mock
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from approve import PROJECT_ROOT, latest_draft_path, listen, post_draft, prepare_new_approval_post


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Post the latest blog draft to Slack and listen for approval reactions."
    )
    parser.add_argument(
        "--no-auto-rewrite",
        action="store_true",
        help="Save thread feedback without rerunning write_serverless.py.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use write_serverless.py --mock when auto-rewriting after feedback.",
    )
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    draft_path = latest_draft_path()
    print(f"[approve_listen] Using latest draft: {draft_path.relative_to(PROJECT_ROOT)}")
    prepare_new_approval_post()
    post_draft(draft_path)
    listen(auto_rewrite=not args.no_auto_rewrite, mock=args.mock)


if __name__ == "__main__":
    main()
