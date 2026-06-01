"""Master orchestrator for the Peachtree blog pipeline.

Implementation order:
1. Search with Tavily.
2. Evaluate sources with Together AI.
3. Write a draft with Together AI.
4. Slack approval request.
5. Post after approval.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def run_stage(command: list[str], label: str) -> None:
    print(f"[pipeline] Starting {label}: {' '.join(command)}")
    completed = subprocess.run(command, cwd=PROJECT_ROOT)
    if completed.returncode != 0:
        raise SystemExit(f"[pipeline] {label} failed with exit code {completed.returncode}")
    print(f"[pipeline] Finished {label}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the blog automation pipeline in order.")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run evaluate.py and write.py in mock mode after a successful search stage.",
    )
    parser.add_argument(
        "--send-to-slack",
        action="store_true",
        help="Post the generated draft to Slack for approval after write.py completes.",
    )
    args = parser.parse_args()

    python = sys.executable
    run_stage([python, "search.py"], "search")

    evaluate_command = [python, "evaluate.py"]
    write_command = [python, "write.py"]
    if args.mock:
        evaluate_command.append("--mock")
        write_command.append("--mock")

    run_stage(evaluate_command, "evaluate")
    run_stage(write_command, "write")
    if args.send_to_slack:
        run_stage([python, "approve.py", "post", "--latest"], "slack approval")

    print("[pipeline] Pipeline completed successfully")


if __name__ == "__main__":
    main()
