"""Generate a blog draft with Together serverless Llama 3.3 70B.

Standalone serverless writer — does not import write.py or together_endpoint.py.
Ignores `TOGETHER_DEDICATED_ENDPOINT_ID` in `.env`.

Saves Markdown, validation JSON, and a PDF (via `draft_pdf.py`) into `output/drafts/`
by default. Use `--no-pdf` to skip PDF export.

Run live:
    python write_serverless.py

Run without Together credits:
    python write_serverless.py --mock
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from write_common import (
    DEFAULT_AUTHOR_CREDENTIALS,
    DEFAULT_AUTHOR_NAME,
    DEFAULT_INPUT_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_VALIDATION_MAX_ATTEMPTS,
    PROJECT_ROOT,
    PROMPT_PATH,
    STYLE_NOTES_PATH,
    build_generation_report,
    build_prompt,
    clear_drafts_directory,
    generate_mock_draft,
    generate_validated_draft,
    generate_with_together,
    load_json,
    load_approval_rewrite_context,
    read_feedback_json,
    read_text,
    save_draft_outputs,
    select_sources_for_draft,
    tag_generation_report,
    write_log_prefix,
)

SERVERLESS_WRITING_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
WRITE_RUNNER = "write_serverless.py"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a GEO blog draft with Together serverless Llama 3.3 70B.",
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model", default=SERVERLESS_WRITING_MODEL)
    parser.add_argument(
        "--source-strategy",
        choices=("auto", "best", "combine"),
        default="auto",
        help="Choose sources for one draft: auto, best, or combine.",
    )
    parser.add_argument("--mock", action="store_true", help="Write a local mock draft instead of calling Together AI.")
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable live terminal progress bars (also set WRITE_NO_PROGRESS=1).",
    )
    parser.add_argument(
        "--feedback-json",
        type=Path,
        help="Optional Slack approval JSON whose feedback should be applied to this rewrite.",
    )
    parser.add_argument(
        "--keep-drafts",
        action="store_true",
        help="Keep existing files in --output-dir instead of clearing them before writing.",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Skip PDF export of the generated Markdown draft.",
    )
    parser.add_argument(
        "--max-validation-attempts",
        type=int,
        default=DEFAULT_VALIDATION_MAX_ATTEMPTS,
        help="Retry generation until validation passes, up to this many attempts.",
    )
    parser.add_argument(
        "--no-validation-retry",
        action="store_true",
        help="Generate once without retrying failed validation checks.",
    )
    args = parser.parse_args()

    os.environ["WRITE_RUNNER"] = WRITE_RUNNER
    load_dotenv(PROJECT_ROOT / ".env")
    if args.no_progress:
        os.environ["WRITE_NO_PROGRESS"] = "1"

    log = write_log_prefix()
    rewrite_context = load_approval_rewrite_context(args.feedback_json)
    approval_feedback = rewrite_context["approval_feedback"]
    previous_draft = rewrite_context["previous_draft"]
    if args.feedback_json:
        if approval_feedback:
            print(f"{log} Loaded Slack approval feedback from {args.feedback_json}")
        if previous_draft:
            print(f"{log} Loaded previous draft for rewrite ({len(previous_draft.split())} words)")
        if not approval_feedback:
            print(f"{log} Warning: No Slack feedback found in {args.feedback_json}")

    if not args.keep_drafts:
        removed = clear_drafts_directory(args.output_dir)
        if removed:
            print(f"{log} Cleared {len(removed)} file(s) from {args.output_dir}")

    sources = load_json(args.input)
    if not sources:
        raise ValueError(f"No kept sources found in {args.input}. Run search.py and evaluate.py first.")

    selected_sources, source_decision = select_sources_for_draft(sources, args.source_strategy)
    print(
        f"{log} Source strategy: "
        f"{source_decision['mode']} "
        f"({source_decision['selected_source_count']}/{source_decision['available_source_count']} sources)"
    )
    print(f"{log} Source decision: {source_decision['reason']}")

    author_name = os.getenv("AUTHOR_NAME", DEFAULT_AUTHOR_NAME)
    author_credentials = os.getenv("AUTHOR_CREDENTIALS", DEFAULT_AUTHOR_CREDENTIALS)

    if args.mock:
        mock_started_at = time.monotonic()
        draft = generate_mock_draft(selected_sources, author_name, author_credentials)
        model_used = "mock"
        generation_report = build_generation_report(
            model_requested="mock",
            model_used="mock",
            model_returned_by_api=None,
            elapsed_seconds=time.monotonic() - mock_started_at,
            usage=None,
            endpoint_management_used=False,
        )
        tag_generation_report(generation_report, mode="mock")
    else:
        model_used = args.model
        prompt = build_prompt(
            read_text(PROMPT_PATH),
            selected_sources,
            read_text(STYLE_NOTES_PATH),
            author_name,
            author_credentials,
            approval_feedback,
            previous_draft,
        )
        if args.no_validation_retry:
            draft, generation_report = generate_with_together(
                prompt,
                model_used,
                allow_serverless_fallback=True,
            )
        else:
            draft, _, generation_report = generate_validated_draft(
                prompt,
                model_used,
                allow_serverless_fallback=True,
                max_attempts=args.max_validation_attempts,
                author_name=author_name,
                author_credentials=author_credentials,
            )
        generation_report["endpoint_management_used"] = False
        tag_generation_report(generation_report, mode="serverless")

    save_draft_outputs(
        draft=draft,
        output_dir=args.output_dir,
        selected_sources=selected_sources,
        sources=sources,
        source_decision=source_decision,
        model_used=model_used,
        generation_report=generation_report,
        skip_pdf=args.no_pdf,
    )


if __name__ == "__main__":
    main()
