"""
test_engine.py — Minimal smoke test. FROZEN.

Run with: python test_engine.py

Checks:
  1. engine.py imports cleanly and builds with defaults.
  2. Starting position has 20 legal moves.
  3. Engine picks a legal move from the start within a tight time budget.
  4. A 2-game mini-match Sunfish-vs-Random finishes and produces a winner
     or a draw (no crashes, no hangs).
"""

from __future__ import annotations

import random
import sys

import engine
import evaluator


def check(cond, msg):
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"ok  : {msg}")


def main() -> int:
    # (1) Build.
    e = engine.build_engine()
    check(e is not None, "engine.build_engine() returns an engine")

    # (2) Legal moves from starting position.
    pos = engine.starting_position()
    n = sum(1 for _ in engine.legal_moves(pos))
    check(n == 20, f"starting position has 20 legal moves (got {n})")
    check(not engine.in_check(pos), "starting position is not in check")

    # (3) Think picks a legal move.
    move, stats = e.think(pos, time_budget=0.05)
    check(move is not None, "engine returns a move")
    legal = set(engine.legal_moves(pos))
    check(move in legal, f"engine move {engine.move_to_alg(move, False)} is legal")

    # (4) Mini-match vs random.
    def mk_sunfish():
        return engine.build_engine()

    def mk_random():
        return engine.RandomEngine(rng=random.Random(0))

    summary = evaluator.run_match(
        mk_sunfish, mk_random,
        label_a="sunfish", label_b="random",
        n_games=2, time_per_move=0.03,
        opening_plies=2, move_limit=80, seed=0,
    )
    check(summary.n_games == 2, "mini-match produced 2 game results")
    check(summary.a_wins + summary.b_wins + summary.draws == 2,
          "mini-match results sum to 2")

    print("\nall smoke tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
