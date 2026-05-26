"""Master orchestrator for the Peachtree blog pipeline.

Implementation order:
1. Search with Tavily.
2. Evaluate sources with Together AI.
3. Write a draft with Together AI.
4. Email for approval.
5. Post after approval.
"""


def main() -> None:
    raise NotImplementedError("pipeline.py will be implemented after search/evaluate/write are working.")


if __name__ == "__main__":
    main()
