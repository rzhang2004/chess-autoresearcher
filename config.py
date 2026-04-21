"""
config.py — The knobs the AutoResearch agent is allowed to tune.

This is the ONLY file the agent may edit freely. Changes here are picked up
by engine.py at engine-construction time.

The baseline values below are Thomas Ahle's Sunfish defaults. They define the
reference engine all modifications are compared against.
"""

# ---------------------------------------------------------------------------
# Piece material values (centipawns-ish units used by Sunfish).
# Sunfish baseline defaults.
# ---------------------------------------------------------------------------
PIECE_VALUES = {
    "P": 100,
    "N": 280,
    "B": 320,
    "R": 479,
    "Q": 929,
    "K": 60000,
}

# ---------------------------------------------------------------------------
# Piece-square tables (positional bonuses per square, from White's perspective,
# indexed by rank 8 → rank 1, file a → file h).
# These are Sunfish's baseline tables. Agent may scale them via PST_SCALE or
# override per-piece via PST_OVERRIDES.
# ---------------------------------------------------------------------------
PST_BASE = {
    "P": (
          0,   0,   0,   0,   0,   0,   0,   0,
         78,  83,  86,  73, 102,  82,  85,  90,
          7,  29,  21,  44,  40,  31,  44,   7,
        -17,  16,  -2,  15,  14,   0,  15, -13,
        -26,   3,  10,   9,   6,   1,   0, -23,
        -22,   9,   5, -11, -10,  -2,   3, -19,
        -31,   8,  -7, -37, -36, -14,   3, -31,
          0,   0,   0,   0,   0,   0,   0,   0,
    ),
    "N": (
        -66, -53, -75, -75, -10, -55, -58, -70,
         -3,  -6, 100, -36,   4,  62,  -4, -14,
         10,  67,   1,  74,  73,  27,  62,  -2,
         24,  24,  45,  37,  33,  41,  25,  17,
         -1,   5,  31,  21,  22,  35,   2,   0,
        -18,  10,  13,  22,  18,  15,  11, -14,
        -23, -15,   2,   0,   2,   0, -23, -20,
        -74, -23, -26, -24, -19, -35, -22, -69,
    ),
    "B": (
        -59, -78, -82, -76, -23,-107, -37, -50,
        -11,  20,  35, -42, -39,  31,   2, -22,
         -9,  39, -32,  41,  52, -10,  28, -14,
         25,  17,  20,  34,  26,  25,  15,  10,
         13,  10,  17,  23,  17,  16,   0,   7,
         14,  25,  24,  15,   8,  25,  20,  15,
         19,  20,  11,   6,   7,   6,  20,  16,
         -7,   2, -15, -12, -14, -15, -10, -10,
    ),
    "R": (
         35,  29,  33,   4,  37,  33,  56,  50,
         55,  29,  56,  67,  55,  62,  34,  60,
         19,  35,  28,  33,  45,  27,  25,  15,
          0,   5,  16,  13,  18,  -4,  -9,  -6,
        -28, -35, -16, -21, -13, -29, -46, -30,
        -42, -28, -42, -25, -25, -35, -26, -46,
        -53, -38, -31, -26, -29, -43, -44, -53,
        -30, -24, -18,   5,  -2, -18, -31, -32,
    ),
    "Q": (
          6,   1,  -8,-104,  69,  24,  88,  26,
         14,  32,  60, -10,  20,  76,  57,  24,
         -2,  43,  32,  60,  72,  63,  43,   2,
          1, -16,  22,  17,  25,  20, -13,  -6,
        -14, -15,  -2,  -5,  -1, -10, -20, -22,
        -30,  -6, -13, -11, -16, -11, -16, -27,
        -36, -18,   0, -19, -15, -15, -21, -38,
        -39, -30, -31, -13, -31, -36, -34, -42,
    ),
    "K": (
          4,  54,  47, -99, -99,  60,  83, -62,
        -32,  10,  55,  56,  56,  55,  10,   3,
        -62,  12, -57,  44, -67,  28,  37, -31,
        -55,  50,  11,  -4, -19,  13,   0, -49,
        -55, -43, -52, -28, -51, -47,  -8, -50,
        -47, -42, -43, -79, -64, -32, -29, -32,
         -4,   3, -14, -50, -57, -18,  13,   4,
         17,  30,  -3, -14,   6,  -1,  40,  18,
    ),
}

# Uniform scale multiplier applied to every PST entry. 1.0 = baseline.
PST_SCALE = 1.0

# Per-piece override (None = use PST_BASE[piece]). Must be a length-64 tuple.
PST_OVERRIDES = {
    "P": None,
    "N": None,
    "B": None,
    "R": None,
    "Q": None,
    "K": None,
}

# ---------------------------------------------------------------------------
# Search parameters.
# ---------------------------------------------------------------------------
QS_LIMIT = 219           # Quiescence: captures must gain at least this much.
EVAL_ROUGHNESS = 13      # MTD-bi aspiration window width.
DRAW_TEST = True         # Detect repetitions during search.
TABLE_SIZE = 10_000_000  # Transposition table cap.

# ---------------------------------------------------------------------------
# Move ordering.
#   "default" = Sunfish's move-value heuristic (captures first, then pst delta)
#   "mvv_lva" = most valuable victim / least valuable attacker (captures only)
#   "random"  = debug/ablation: no ordering
# ---------------------------------------------------------------------------
MOVE_ORDERING = "default"

# ---------------------------------------------------------------------------
# Time management.
# ---------------------------------------------------------------------------
TIME_PER_MOVE = 0.1       # Seconds per move for iterative deepening.
EARLY_EXIT_MARGIN = 0.8   # Stop ID early if next depth unlikely to complete.

# ---------------------------------------------------------------------------
# Bundled snapshot used by engine.py. Do not reference directly from outside.
# ---------------------------------------------------------------------------
def get_config():
    return {
        "piece_values": dict(PIECE_VALUES),
        "pst_base": {k: tuple(v) for k, v in PST_BASE.items()},
        "pst_scale": PST_SCALE,
        "pst_overrides": {k: (tuple(v) if v is not None else None)
                          for k, v in PST_OVERRIDES.items()},
        "qs_limit": QS_LIMIT,
        "eval_roughness": EVAL_ROUGHNESS,
        "draw_test": DRAW_TEST,
        "table_size": TABLE_SIZE,
        "move_ordering": MOVE_ORDERING,
        "time_per_move": TIME_PER_MOVE,
        "early_exit_margin": EARLY_EXIT_MARGIN,
    }
