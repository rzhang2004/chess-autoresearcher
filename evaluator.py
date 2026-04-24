"""
evaluator.py — Frozen match runner.

The evaluation protocol is LOCKED. The AutoResearch agent is not allowed to
modify this file. Any change to the protocol invalidates previous results and
must be explicitly blessed by the human researcher.

Protocol (v1, April 2026):
  - Batch size: 50 games per evaluation.
  - Time control: fixed `time_per_move` seconds per move (default 0.1s).
  - Opening diversity: 4 plies of uniformly-random legal moves from the
    starting position, seeded by (batch_seed, game_index) for reproducibility.
  - Colors: alternate — engine A plays White on even-indexed games, Black on
    odd-indexed games — so material bias averages out.
  - Move limit: 200 plies; exceeded games are scored as draws.
  - End-of-game detection (in priority order):
      1. king captured (score sentinel or literal king removal)
      2. checkmate (no legal move + in check)
      3. stalemate (no legal move + not in check)
      4. 50-move rule (100 half-moves without capture or pawn move)
      5. threefold repetition
      6. insufficient material (K vs K, K+minor vs K, K+minor vs K+minor)
      7. move-limit draw
  - Output: per-game rows + batch summary row appended to results.csv,
    plus per-match JSON in logs/.

The agent may NOT read this file to game the protocol, but the rules are
public; security-by-obscurity isn't the point — reproducibility is.
"""

from __future__ import annotations

import csv
import json
import os
import random
import time
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Callable, List, Optional

import engine as _engine


# ---------------------------------------------------------------------------
# Locked protocol constants. DO NOT CHANGE without bumping PROTOCOL_VERSION.
# ---------------------------------------------------------------------------
PROTOCOL_VERSION = "v1-2026-04"
DEFAULT_BATCH_SIZE = 50
DEFAULT_TIME_PER_MOVE = 0.1
DEFAULT_OPENING_PLIES = 4
DEFAULT_MOVE_LIMIT = 200
DEFAULT_SEED = 2026


# ---------------------------------------------------------------------------
# Result types.
# ---------------------------------------------------------------------------
@dataclass
class GameResult:
    game_idx: int
    seed: int
    white: str
    black: str
    result: str           # "1-0", "0-1", "1/2-1/2"
    termination: str      # "checkmate" | "king_capture" | "stalemate" | ...
    plies: int
    opening_moves: List[str]
    white_avg_sec_per_move: float
    black_avg_sec_per_move: float
    white_max_sec_per_move: float
    black_max_sec_per_move: float
    pgn_moves: List[str] = field(default_factory=list)


@dataclass
class MatchSummary:
    protocol_version: str
    label_a: str
    label_b: str
    n_games: int
    time_per_move: float
    opening_plies: int
    move_limit: int
    seed: int
    a_wins: int
    b_wins: int
    draws: int
    a_win_rate: float     # wins + 0.5*draws, as a fraction of games played
    a_win_rate_pct: float
    avg_plies: float
    a_avg_sec_per_move: float
    b_avg_sec_per_move: float
    a_max_sec_per_move: float
    b_max_sec_per_move: float
    terminations: dict
    wall_seconds: float


# ---------------------------------------------------------------------------
# Game runner.
# ---------------------------------------------------------------------------
def _material_signature(pos) -> tuple:
    """Returns a sorted tuple of piece types on the board (case-insensitive)
    for insufficient-material detection."""
    return tuple(sorted(c.upper() for c in pos.board if c.isalpha()))


def _is_insufficient_material(pos) -> bool:
    sig = _material_signature(pos)
    # K vs K
    if sig == ("K", "K"):
        return True
    # K+minor vs K
    if len(sig) == 3 and sig.count("K") == 2 and any(p in sig for p in ("B", "N")):
        return True
    # K+N vs K+N, K+B vs K+B (often draws; treat as insufficient)
    if len(sig) == 4 and sig.count("K") == 2:
        minors = [p for p in sig if p in ("B", "N")]
        if len(minors) == 2:
            return True
    return False


def _play_one_game(engine_white, engine_black, game_idx: int,
                   seed: int, time_per_move: float,
                   opening_plies: int, move_limit: int) -> GameResult:
    rng = random.Random(seed * 100_000 + game_idx)  # tuple seeds removed in Py3.12
    pos = _engine.starting_position()
    history = [pos]
    # The engines reset per game so they don't leak transposition state.
    engine_white.reset()
    engine_black.reset()

    # --- Random opening: equal number of plies picked uniformly at random
    # from the legal move set. Seeded for reproducibility.
    opening_alg: List[str] = []
    for ply in range(opening_plies):
        legals = list(_engine.legal_moves(pos))
        if not legals:
            break
        m = rng.choice(legals)
        flip = (ply % 2 == 1)  # black to move after white's move
        opening_alg.append(_engine.move_to_alg(m, flip=flip))
        pos = pos.move(m)
        history.append(pos)

    white_times: List[float] = []
    black_times: List[float] = []
    pgn_moves: List[str] = list(opening_alg)
    no_progress = 0  # plies since last capture or pawn move
    plies_played = opening_plies
    termination = "move_limit"
    result = "1/2-1/2"

    while plies_played < move_limit:
        side_to_move_is_white = (plies_played % 2 == 0)
        active = engine_white if side_to_move_is_white else engine_black
        flip = not side_to_move_is_white

        # --- Game-end detection BEFORE move.
        if _engine.king_is_captured(pos):
            # Previous mover captured the king — they win.
            result = "0-1" if side_to_move_is_white else "1-0"
            termination = "king_capture"
            break
        if _is_insufficient_material(pos):
            result = "1/2-1/2"
            termination = "insufficient_material"
            break
        if no_progress >= 100:
            result = "1/2-1/2"
            termination = "fifty_move"
            break
        # Threefold repetition.
        counts = Counter(history)
        if any(v >= 3 for v in counts.values()):
            result = "1/2-1/2"
            termination = "threefold_repetition"
            break
        if not _engine.has_any_legal_move(pos):
            if _engine.in_check(pos):
                result = "0-1" if side_to_move_is_white else "1-0"
                termination = "checkmate"
            else:
                result = "1/2-1/2"
                termination = "stalemate"
            break

        # --- Engine think.
        t0 = time.time()
        move, _stats = active.think(pos, history=history[-8:],
                                    time_budget=time_per_move)
        elapsed = time.time() - t0
        if move is None:
            # Engine found no move. Treat as a loss for the mover.
            result = "0-1" if side_to_move_is_white else "1-0"
            termination = "no_move_returned"
            break
        # Validate legality (defensive; Sunfish can return pseudo-legal moves
        # that leave own king in check — in that case the opponent captures
        # the king on the next move, which we handle via the king_capture path).
        (white_times if side_to_move_is_white else black_times).append(elapsed)

        # Track no-progress counter for 50-move rule.
        i, j = move
        is_capture = pos.board[j].islower()
        is_pawn = pos.board[i] == "P"
        pgn_moves.append(_engine.move_to_alg(move, flip=flip))

        pos = pos.move(move)
        history.append(pos)
        plies_played += 1

        if is_capture or is_pawn:
            no_progress = 0
        else:
            no_progress += 1
    else:
        # Hit move_limit without break.
        termination = "move_limit"
        result = "1/2-1/2"

    def _mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    def _mx(xs):
        return max(xs) if xs else 0.0

    return GameResult(
        game_idx=game_idx,
        seed=seed,
        white=getattr(engine_white, "cfg", {}).get("name", "engine_a"),
        black=getattr(engine_black, "cfg", {}).get("name", "engine_b"),
        result=result,
        termination=termination,
        plies=plies_played,
        opening_moves=opening_alg,
        white_avg_sec_per_move=_mean(white_times),
        black_avg_sec_per_move=_mean(black_times),
        white_max_sec_per_move=_mx(white_times),
        black_max_sec_per_move=_mx(black_times),
        pgn_moves=pgn_moves,
    )


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------
def run_match(
    engine_a_factory: Callable[[], object],
    engine_b_factory: Callable[[], object],
    *,
    label_a: str = "A",
    label_b: str = "B",
    n_games: int = DEFAULT_BATCH_SIZE,
    time_per_move: float = DEFAULT_TIME_PER_MOVE,
    opening_plies: int = DEFAULT_OPENING_PLIES,
    move_limit: int = DEFAULT_MOVE_LIMIT,
    seed: int = DEFAULT_SEED,
    log_path: Optional[str] = None,
    verbose: bool = False,
) -> MatchSummary:
    """Run a locked-protocol match. Returns a MatchSummary.

    engine_{a,b}_factory() must return a fresh engine instance supporting
    .reset() and .think(pos, history, time_budget).
    """
    start_wall = time.time()
    a = engine_a_factory()
    b = engine_b_factory()
    # Label the engines so GameResult knows who played which color.
    a.cfg = dict(getattr(a, "cfg", {}) or {}, name=label_a)
    b.cfg = dict(getattr(b, "cfg", {}) or {}, name=label_b)

    games: List[GameResult] = []
    a_wins = b_wins = draws = 0
    a_times: List[float] = []
    b_times: List[float] = []
    a_max_times: List[float] = []
    b_max_times: List[float] = []
    terminations: Counter = Counter()

    for g in range(n_games):
        # Alternate colors: even games A=white, odd games A=black.
        if g % 2 == 0:
            white, black = a, b
        else:
            white, black = b, a
        result = _play_one_game(
            white, black, game_idx=g, seed=seed,
            time_per_move=time_per_move,
            opening_plies=opening_plies, move_limit=move_limit,
        )
        # Attribute the result to A/B.
        if result.result == "1-0":
            winner = "A" if g % 2 == 0 else "B"
        elif result.result == "0-1":
            winner = "B" if g % 2 == 0 else "A"
        else:
            winner = "draw"
        if winner == "A":
            a_wins += 1
        elif winner == "B":
            b_wins += 1
        else:
            draws += 1
        terminations[result.termination] += 1

        if g % 2 == 0:
            a_times.append(result.white_avg_sec_per_move)
            b_times.append(result.black_avg_sec_per_move)
            a_max_times.append(result.white_max_sec_per_move)
            b_max_times.append(result.black_max_sec_per_move)
        else:
            a_times.append(result.black_avg_sec_per_move)
            b_times.append(result.white_avg_sec_per_move)
            a_max_times.append(result.black_max_sec_per_move)
            b_max_times.append(result.white_max_sec_per_move)

        games.append(result)
        if verbose:
            print(f"  game {g+1:>3}/{n_games}: {result.result:<7} "
                  f"{result.termination:<22} plies={result.plies:>3} "
                  f"(A={a_wins} B={b_wins} D={draws})")

    def _mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    a_win_rate = (a_wins + 0.5 * draws) / max(n_games, 1)

    summary = MatchSummary(
        protocol_version=PROTOCOL_VERSION,
        label_a=label_a,
        label_b=label_b,
        n_games=n_games,
        time_per_move=time_per_move,
        opening_plies=opening_plies,
        move_limit=move_limit,
        seed=seed,
        a_wins=a_wins,
        b_wins=b_wins,
        draws=draws,
        a_win_rate=round(a_win_rate, 4),
        a_win_rate_pct=round(100.0 * a_win_rate, 2),
        avg_plies=round(_mean([g.plies for g in games]), 1),
        a_avg_sec_per_move=round(_mean(a_times), 4),
        b_avg_sec_per_move=round(_mean(b_times), 4),
        a_max_sec_per_move=round(max(a_max_times) if a_max_times else 0.0, 4),
        b_max_sec_per_move=round(max(b_max_times) if b_max_times else 0.0, 4),
        terminations=dict(terminations),
        wall_seconds=round(time.time() - start_wall, 2),
    )

    if log_path is not None:
        _write_match_log(log_path, summary, games)
    return summary


def _write_match_log(log_path: str, summary: MatchSummary,
                     games: List[GameResult]) -> None:
    os.makedirs(log_path, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    stem = f"{ts}_{summary.label_a}_vs_{summary.label_b}"
    with open(os.path.join(log_path, stem + "_summary.json"), "w") as f:
        json.dump(asdict(summary), f, indent=2)
    with open(os.path.join(log_path, stem + "_games.json"), "w") as f:
        json.dump([asdict(g) for g in games], f, indent=2)


# ---------------------------------------------------------------------------
# Append-only results.csv writer (called by search.py or ad hoc).
# ---------------------------------------------------------------------------
RESULTS_CSV_COLS = [
    "timestamp", "protocol_version", "label_a", "label_b", "n_games",
    "time_per_move", "opening_plies", "move_limit", "seed",
    "a_wins", "b_wins", "draws", "a_win_rate_pct", "avg_plies",
    "a_avg_sec_per_move", "b_avg_sec_per_move",
    "a_max_sec_per_move", "b_max_sec_per_move",
    "wall_seconds", "notes",
]


def append_result_row(csv_path: str, summary: MatchSummary,
                      notes: str = "") -> None:
    write_header = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(RESULTS_CSV_COLS)
        w.writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            summary.protocol_version,
            summary.label_a, summary.label_b, summary.n_games,
            summary.time_per_move, summary.opening_plies,
            summary.move_limit, summary.seed,
            summary.a_wins, summary.b_wins, summary.draws,
            summary.a_win_rate_pct, summary.avg_plies,
            summary.a_avg_sec_per_move, summary.b_avg_sec_per_move,
            summary.a_max_sec_per_move, summary.b_max_sec_per_move,
            summary.wall_seconds, notes,
        ])


# ---------------------------------------------------------------------------
# CLI entry point: python evaluator.py [--baseline | --vs-random] [...]
# ---------------------------------------------------------------------------
def _build_baseline():
    return _engine.build_engine()


def _build_random(seed=0):
    return _engine.RandomEngine(rng=random.Random(seed))


def _main():
    import argparse

    ap = argparse.ArgumentParser(
        description="Run the locked-protocol match runner.")
    ap.add_argument("--mode", choices=["sunfish_vs_sunfish",
                                       "sunfish_vs_random"],
                    default="sunfish_vs_sunfish")
    ap.add_argument("--n-games", type=int, default=DEFAULT_BATCH_SIZE)
    ap.add_argument("--time-per-move", type=float, default=DEFAULT_TIME_PER_MOVE)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--opening-plies", type=int, default=DEFAULT_OPENING_PLIES)
    ap.add_argument("--move-limit", type=int, default=DEFAULT_MOVE_LIMIT)
    ap.add_argument("--log-dir", default="logs")
    ap.add_argument("--csv", default="results.csv")
    ap.add_argument("--notes", default="")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if args.mode == "sunfish_vs_sunfish":
        a_factory = _build_baseline
        b_factory = _build_baseline
        label_a, label_b = "sunfish_baseline", "sunfish_baseline_mirror"
    else:
        a_factory = _build_baseline
        b_factory = lambda: _build_random(seed=args.seed + 1)
        label_a, label_b = "sunfish_baseline", "random"

    print(f"Running locked protocol {PROTOCOL_VERSION}: "
          f"{label_a} vs {label_b}, {args.n_games} games, "
          f"{args.time_per_move}s/move, seed={args.seed}")
    summary = run_match(
        a_factory, b_factory,
        label_a=label_a, label_b=label_b,
        n_games=args.n_games,
        time_per_move=args.time_per_move,
        opening_plies=args.opening_plies,
        move_limit=args.move_limit,
        seed=args.seed,
        log_path=args.log_dir,
        verbose=args.verbose,
    )
    append_result_row(args.csv, summary, notes=args.notes)
    print(json.dumps(asdict(summary), indent=2))


if __name__ == "__main__":
    _main()
