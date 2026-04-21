"""
search.py — AutoResearch optimization loop (STUB, Week 3 deliverable).

Will implement the propose → evaluate → accept/reject loop:
  1. Read program.md for rules.
  2. Read config.py to get current parameters.
  3. Propose a small diff (e.g., ±5% on PST_SCALE, or bump a piece value).
  4. Run evaluator.run_match(candidate, baseline).
  5. If win rate > 55% (threshold), save config; else revert.
  6. Append a row to results.csv with the outcome.

This file is frozen once implemented — the agent is not allowed to edit the
search loop itself, only the config space it explores.
"""

from __future__ import annotations


def main() -> None:
    raise NotImplementedError(
        "search.py is a Week 3 deliverable. Week 2 milestone is baseline + "
        "evaluation pipeline only.")


if __name__ == "__main__":
    main()
