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

Skip the model menu (menu 1 = default Qwen 235B tput):
    python approve_listen.py --model 1
"""

from __future__ import annotations

from peachtree_blog.paths import PROJECT_ROOT

import argparse

from dotenv import load_dotenv

from peachtree_blog.approve.approve import latest_draft_path, listen, post_draft, prepare_new_approval_post
from peachtree_blog.write.write_serverless import model_label, resolve_writing_model


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Post the latest blog draft to Slack and listen for approval reactions.",
    )
    parser.add_argument(
        "--model",
        help="Together model ID or write_serverless menu number for Slack auto-rewrites.",
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
    rewrite_model = None if args.mock else resolve_writing_model(args.model)
    if rewrite_model:
        print(f"[approve_listen] Rewrite model: {model_label(rewrite_model)}")

    draft_path = latest_draft_path()
    print(f"[approve_listen] Using latest draft: {draft_path.relative_to(PROJECT_ROOT)}")
    prepare_new_approval_post()
    post_draft(draft_path)
    listen(
        auto_rewrite=not args.no_auto_rewrite,
        mock=args.mock,
        rewrite_model=rewrite_model,
    )


if __name__ == "__main__":
    main()
