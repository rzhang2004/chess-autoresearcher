"""
engine.py — Lightweight Python chess engine (Sunfish-equivalent).

This is a reconstruction of Thomas Ahle's public-domain Sunfish engine
(https://github.com/thomasahle/sunfish), following its 120-square padded
board representation, PST-based evaluation, and MTD-bi iterative-deepening
search. All tunable numbers are read from config.py so the AutoResearch
agent can experiment without touching this file.

Frozen — not editable by the agent.
"""

from __future__ import annotations

import random
import time
from collections import namedtuple
from itertools import count
from typing import Callable, Iterable, Optional, Tuple

import config as _cfg_mod

# ---------------------------------------------------------------------------
# Board geometry (120-square padded board, Sunfish convention).
# ---------------------------------------------------------------------------
# The board is a 120-char string. Rows 0,1,10,11 and cols 0,9 are padding.
# Rank 8 starts at index 21 (A8). Rank 1 starts at index 91 (A1).
A1, H1, A8, H8 = 91, 98, 21, 28

INITIAL_BOARD = (
    "         \n"  #   0 -  9
    "         \n"  #  10 - 19
    " rnbqkbnr\n"  #  20 - 29   rank 8 (black)
    " pppppppp\n"  #  30 - 39   rank 7
    " ........\n"  #  40 - 49
    " ........\n"  #  50 - 59
    " ........\n"  #  60 - 69
    " ........\n"  #  70 - 79
    " PPPPPPPP\n"  #  80 - 89   rank 2
    " RNBQKBNR\n"  #  90 - 99   rank 1 (white)
    "         \n"  # 100 -109
    "         \n"  # 110 -119
)

# Compass directions, in 120-board index deltas.
N, E, S, W = -10, 1, 10, -1
DIRECTIONS = {
    "P": (N, N + N, N + W, N + E),
    "N": (N + N + E, E + N + E, E + S + E, S + S + E,
          S + S + W, W + S + W, W + N + W, N + N + W),
    "B": (N + E, S + E, S + W, N + W),
    "R": (N, E, S, W),
    "Q": (N, E, S, W, N + E, S + E, S + W, N + W),
    "K": (N, E, S, W, N + E, S + E, S + W, N + W),
}


# ---------------------------------------------------------------------------
# PST assembly. Padded 120-entry PST per piece, with piece value folded in.
# ---------------------------------------------------------------------------
def _build_pst(cfg: dict) -> dict:
    """Build the 120-entry padded PST tables from the config snapshot."""
    piece = cfg["piece_values"]
    pst_raw = {}
    for p in "PNBRQK":
        override = cfg["pst_overrides"].get(p)
        base = override if override is not None else cfg["pst_base"][p]
        scaled = tuple(int(round(x * cfg["pst_scale"])) for x in base)
        pst_raw[p] = scaled

    pst = {}
    for p, table in pst_raw.items():
        pv = piece[p]
        # Pad each 8-square row with 0s at col 0 and col 9.
        padded_rows = []
        for r in range(8):
            row = table[r * 8:(r + 1) * 8]
            padded_rows.append((0,) + tuple(x + pv for x in row) + (0,))
        flat = sum(padded_rows, ())
        # Pad 2 rows top + 2 rows bottom (each row = 10 entries).
        pst[p] = (0,) * 20 + flat + (0,) * 20
    return pst


# MATE thresholds are derived from the configured king value.
def _mate_bounds(cfg: dict) -> Tuple[int, int]:
    k = cfg["piece_values"]["K"]
    q = cfg["piece_values"]["Q"]
    return k - 10 * q, k + 10 * q  # (MATE_LOWER, MATE_UPPER)


# ---------------------------------------------------------------------------
# Position: immutable chess state.
# ---------------------------------------------------------------------------
class Position(namedtuple("Position", "board score wc bc ep kp")):
    """Chess position (Sunfish convention).

    board : 120-char string, padded. Uppercase = side to move ("us"),
            lowercase = opponent. Board is rotated after every move so the
            side to move always sees themselves on ranks 1-2.
    score : running evaluation from side-to-move's perspective.
    wc    : our castling rights, (queenside, kingside).
    bc    : opponent's castling rights, (kingside, queenside) — pre-rotated.
    ep    : en passant target square (as an index into our rotated board).
    kp    : king passant square (used to detect castling-through-check).
    """

    __slots__ = ()

    # Per-position move generation is parameterized by the static pst and
    # directions, which we pull in via module-level _PST (set at engine build).
    def gen_moves(self) -> Iterable[Tuple[int, int]]:
        board = self.board
        for i, p in enumerate(board):
            if not p.isupper():
                continue
            for d in DIRECTIONS[p]:
                j = i
                while True:
                    j += d
                    q = board[j]
                    if q.isspace() or q.isupper():
                        break
                    # Pawn-specific restrictions.
                    if p == "P":
                        if d in (N, N + N) and q != ".":
                            break
                        if d == N + N and (i < A1 + N or board[i + N] != "."):
                            break
                        if (d in (N + W, N + E) and q == "."
                                and j not in (self.ep, self.kp,
                                              self.kp - 1, self.kp + 1)):
                            break
                    yield (i, j)
                    # Sliding? Kings and knights and pawns don't slide; stop
                    # after a capture.
                    if p in "PNK" or q.islower():
                        break
                    # Castling: slide a rook next to our king.
                    if i == A1 and board[j + E] == "K" and self.wc[0]:
                        yield (j + E, j + W)
                    if i == H1 and board[j + W] == "K" and self.wc[1]:
                        yield (j + W, j + E)

    def rotate(self) -> "Position":
        return Position(
            self.board[::-1].swapcase(), -self.score,
            self.bc, self.wc,
            119 - self.ep if self.ep else 0,
            119 - self.kp if self.kp else 0,
        )

    def nullmove(self) -> "Position":
        return Position(
            self.board[::-1].swapcase(), -self.score,
            self.bc, self.wc, 0, 0,
        )

    def move(self, m) -> "Position":
        i, j = m
        p, q = self.board[i], self.board[j]

        def put(board: str, idx: int, piece: str) -> str:
            return board[:idx] + piece + board[idx + 1:]

        board = self.board
        wc, bc, ep, kp = self.wc, self.bc, 0, 0
        score = self.score + self.value(m)

        board = put(board, j, board[i])
        board = put(board, i, ".")

        # Castling rights updates.
        if i == A1:
            wc = (False, wc[1])
        if i == H1:
            wc = (wc[0], False)
        if j == A8:
            bc = (bc[0], False)
        if j == H8:
            bc = (False, bc[1])

        # Castling: slide the rook.
        if p == "K":
            wc = (False, False)
            if abs(j - i) == 2:
                kp = (i + j) // 2
                board = put(board, A1 if j < i else H1, ".")
                board = put(board, kp, "R")

        # Pawn promotion / double move / en passant capture.
        if p == "P":
            if A8 <= j <= H8:
                board = put(board, j, "Q")
            if j - i == 2 * N:
                ep = i + N
            if j == self.ep:
                board = put(board, j + S, ".")

        return Position(board, score, wc, bc, ep, kp).rotate()

    def value(self, m) -> int:
        i, j = m
        p, q = self.board[i], self.board[j]
        pst = _PST  # module-level, set at engine construction
        score = pst[p][j] - pst[p][i]
        if q.islower():
            score += pst[q.upper()][119 - j]
        if abs(j - self.kp) < 2:
            score += pst["K"][119 - j]
        if p == "K" and abs(i - j) == 2:
            score += pst["R"][(i + j) // 2]
            score -= pst["R"][A1 if j < i else H1]
        if p == "P":
            if A8 <= j <= H8:
                score += pst["Q"][j] - pst["P"][j]
            if j == self.ep:
                score += pst["P"][119 - (j + S)]
        return score


# Module-level PST / mate bounds. Populated by build_engine().
_PST: dict = {}
_MATE_LOWER: int = 0
_MATE_UPPER: int = 0


# ---------------------------------------------------------------------------
# Searcher: iterative deepening MTD-bi.
# ---------------------------------------------------------------------------
Entry = namedtuple("Entry", "lower upper")


class Searcher:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.tp_score: dict = {}
        self.tp_move: dict = {}
        self.history: set = set()
        self.nodes = 0

    def bound(self, pos: Position, gamma: int, depth: int, root: bool = True) -> int:
        """MTD-bi binary-search primitive. Returns a fail-high or fail-low
        bound on pos's score vs gamma."""
        self.nodes += 1
        depth = max(depth, 0)

        if pos.score <= -_MATE_LOWER:
            return -_MATE_UPPER

        if self.cfg["draw_test"]:
            if not root and pos in self.history:
                return 0

        entry = self.tp_score.get(
            (pos, depth, root), Entry(-_MATE_UPPER, _MATE_UPPER))
        if entry.lower >= gamma and (not root or self.tp_move.get(pos) is not None):
            return entry.lower
        if entry.upper < gamma:
            return entry.upper

        qs_limit = self.cfg["qs_limit"]
        move_ordering = self.cfg["move_ordering"]

        def moves():
            # Null-move pruning (at depth > 0, non-root, only if we have
            # non-pawn material). Gated by cfg["enable_null_move"] for ablations.
            if (self.cfg.get("enable_null_move", True)
                    and depth > 0 and not root
                    and any(c in pos.board for c in "RBNQ")):
                yield None, -self.bound(pos.nullmove(), 1 - gamma, depth - 3, root=False)
            # Stand-pat at depth 0.
            if depth == 0:
                yield None, pos.score
            # Killer move from the transposition table.
            killer = self.tp_move.get(pos)
            if killer and (depth > 0 or pos.value(killer) >= qs_limit):
                yield killer, -self.bound(pos.move(killer), 1 - gamma, depth - 1, root=False)
            # All other moves, ordered by heuristic.
            legal = list(pos.gen_moves())
            if move_ordering == "random":
                random.shuffle(legal)
            elif move_ordering == "mvv_lva":
                def _score(m):
                    i, j = m
                    victim = pos.board[j]
                    attacker = pos.board[i]
                    if victim.islower():
                        vv = _PST[victim.upper()][0]  # rough victim value
                        av = _PST[attacker][0]
                        return vv * 10 - av
                    return -1
                legal.sort(key=_score, reverse=True)
            else:  # "default" = Sunfish move value
                legal.sort(key=pos.value, reverse=True)
            for m in legal:
                if depth > 0 or pos.value(m) >= qs_limit:
                    yield m, -self.bound(pos.move(m), 1 - gamma, depth - 1, root=False)

        best = -_MATE_UPPER
        for m, score in moves():
            best = max(best, score)
            if best >= gamma:
                if len(self.tp_move) > self.cfg["table_size"]:
                    self.tp_move.clear()
                self.tp_move[pos] = m
                break

        # Stalemate check: no legal moves at depth > 0.
        if best < gamma and best < 0 and depth > 0:
            def is_dead(p_):
                return any(p_.value(mm) >= _MATE_LOWER for mm in p_.gen_moves())
            if all(is_dead(pos.move(mm)) for mm in pos.gen_moves()):
                in_check = is_dead(pos.nullmove())
                best = -_MATE_UPPER if in_check else 0

        if len(self.tp_score) > self.cfg["table_size"]:
            self.tp_score.clear()
        if best >= gamma:
            self.tp_score[pos, depth, root] = Entry(best, entry.upper)
        else:
            self.tp_score[pos, depth, root] = Entry(entry.lower, best)

        return best

    def search(self, pos: Position, history=()):
        """Iterative deepening MTD-bi. Yields (depth, move, score) per iter."""
        self.nodes = 0
        self.history = set(history)
        self.tp_score.clear()

        eval_roughness = self.cfg["eval_roughness"]
        for depth in range(1, 1000):
            lower, upper = -_MATE_UPPER, _MATE_UPPER
            while lower < upper - eval_roughness:
                gamma = (lower + upper + 1) // 2
                score = self.bound(pos, gamma, depth)
                if score >= gamma:
                    lower = score
                if score < gamma:
                    upper = score
            # Ensure the best move is cached in tp_move.
            self.bound(pos, lower, depth)
            entry = self.tp_score.get((pos, depth, True))
            yield depth, self.tp_move.get(pos), entry.lower if entry else lower


# ---------------------------------------------------------------------------
# Public API: engine construction and thinking.
# ---------------------------------------------------------------------------
class SunfishEngine:
    """A stateful engine handle. Wraps a Searcher + the active config.

    Use .think(position, history, time_budget) to pick a move.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.searcher = Searcher(cfg)

    def reset(self):
        self.searcher = Searcher(self.cfg)

    def think(self, pos: Position, history=(), time_budget: Optional[float] = None) -> Tuple[Optional[Tuple[int, int]], dict]:
        """Iterative-deepening search bounded by wall-clock time.

        Returns (best_move_or_None, stats_dict).
        """
        if time_budget is None:
            time_budget = self.cfg["time_per_move"]
        margin = self.cfg["early_exit_margin"]

        start = time.time()
        best = None
        best_score = 0
        best_depth = 0
        for depth, move, score in self.searcher.search(pos, history):
            if move is not None:
                best = move
                best_score = score
                best_depth = depth
            elapsed = time.time() - start
            # Stop if already over budget, or if we've used enough of it that
            # the next (typically ~4x costlier) iteration is unlikely to help.
            if elapsed >= time_budget:
                break
            if elapsed > time_budget * margin:
                break
        elapsed = time.time() - start
        stats = {
            "elapsed": elapsed,
            "depth": best_depth,
            "score": best_score,
            "nodes": self.searcher.nodes,
        }
        return best, stats


def build_engine(config_overrides: Optional[dict] = None) -> SunfishEngine:
    """Build a fresh engine honoring config.py (with optional overrides).

    Also refreshes the module-level PST tables used by Position.value and the
    search. Because PSTs are module-level, building two engines with *different*
    configs simultaneously is not supported — call build_engine() once per
    evaluator run for each side.
    """
    global _PST, _MATE_LOWER, _MATE_UPPER
    cfg = _cfg_mod.get_config()
    if config_overrides:
        cfg.update(config_overrides)
    _PST = _build_pst(cfg)
    _MATE_LOWER, _MATE_UPPER = _mate_bounds(cfg)
    return SunfishEngine(cfg)


def starting_position() -> Position:
    return Position(INITIAL_BOARD, 0, (True, True), (True, True), 0, 0)


# ---------------------------------------------------------------------------
# Legality + game-end helpers (needed by evaluator.py).
# ---------------------------------------------------------------------------
def king_is_captured(pos: Position) -> bool:
    """True if the side-to-move no longer has a king on the board."""
    return "K" not in pos.board


def in_check(pos: Position) -> bool:
    """True if the side-to-move is in check."""
    null = pos.nullmove()
    for m in null.gen_moves():
        _, j = m
        if null.board[j] == "k":
            return True
    return False


def legal_moves(pos: Position):
    """Yield moves that don't leave our king capturable next ply."""
    for m in pos.gen_moves():
        new_pos = pos.move(m)
        # After pos.move, it's the opponent's turn; opponent sees our king as 'k'.
        safe = True
        for om in new_pos.gen_moves():
            _, oj = om
            if new_pos.board[oj] == "k":
                safe = False
                break
        if safe:
            yield m


def has_any_legal_move(pos: Position) -> bool:
    for _ in legal_moves(pos):
        return True
    return False


# ---------------------------------------------------------------------------
# Move <-> algebraic converters (useful for PGN-ish logging).
# ---------------------------------------------------------------------------
def sq_to_alg(idx: int, flip: bool) -> str:
    """Translate a 120-board index to 'e4'-style. flip=True means the position
    was rotated from white's perspective (i.e. black to move)."""
    if flip:
        idx = 119 - idx
    file = (idx % 10) - 1           # 0..7
    rank = 10 - (idx // 10)          # 1..8
    return chr(ord("a") + file) + str(rank)


def move_to_alg(m: Tuple[int, int], flip: bool) -> str:
    i, j = m
    return sq_to_alg(i, flip) + sq_to_alg(j, flip)


# ---------------------------------------------------------------------------
# Simple baseline opponents.
# ---------------------------------------------------------------------------
class RandomEngine:
    """Picks a uniformly random legal move. Useful as a sanity floor."""

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()
        self.cfg = {"name": "random"}

    def reset(self):
        pass

    def think(self, pos: Position, history=(), time_budget: Optional[float] = None):
        start = time.time()
        moves = list(legal_moves(pos))
        if not moves:
            return None, {"elapsed": time.time() - start, "depth": 0,
                          "score": 0, "nodes": 0}
        return self.rng.choice(moves), {
            "elapsed": time.time() - start,
            "depth": 0, "score": 0, "nodes": 0,
        }


# Eagerly build the PST so module import works even before build_engine().
_ = build_engine()
