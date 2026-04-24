# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Smoke test (must print "all smoke tests passed")
python test_engine.py

# Run the autoresearch loop (requires ANTHROPIC_API_KEY)
ANTHROPIC_API_KEY=sk-ant-... python search.py
ANTHROPIC_API_KEY=sk-ant-... python search.py --max-iterations 20 --quiet

# Run a match manually
python evaluator.py --mode sunfish_vs_sunfish --n-games 50 --time-per-move 0.1 --seed 2026 --log-dir logs --csv results.csv --notes "label"
python evaluator.py --mode sunfish_vs_random  --n-games 50 --time-per-move 0.1 --seed 2026 --log-dir logs --csv results.csv

# CI regression (fast, 4 games)
python evaluator.py --mode sunfish_vs_random --n-games 4 --time-per-move 0.02 --opening-plies 2 --move-limit 60 --seed 9999 --log-dir /tmp/logs --csv /tmp/results.csv --notes "ci"
```

Install the one non-stdlib dependency before running `search.py`:
```bash
pip install anthropic
```

## Architecture

### Frozen vs. editable files

The autoresearch contract enforces a hard boundary:

| File | Status | Purpose |
|------|--------|---------|
| `engine.py` | **frozen** | Self-contained Sunfish reconstruction (120-board mailbox, MTD-bi search, PSTs, quiescence, null-move) |
| `evaluator.py` | **frozen** | Locked match runner; defines the reproducible evaluation protocol |
| `test_engine.py` | **frozen** | Smoke tests |
| `program.md` | **frozen** | Agent contract / rules |
| `config.py` | **editable** | The only file the AI researcher may tune |
| `best_config.yaml` | **editable** | Updated by `search.py` on each KEEP |
| `results.csv` | **append-only** | Experiment log; never rewrite existing rows |
| `search.py` | frozen post-implementation | The optimization loop itself |

### The optimization loop (`search.py`)

`search.py` is the autoresearch harness. Each iteration:

1. **Propose** — calls Claude API (`claude-sonnet-4-6` by default; override with `AUTORESEARCH_MODEL` env var) with the current `config.py`, recent `results.csv` history, and `program.md` rules. Claude returns a modified `config.py` in a `\`\`\`python` block.
2. **Validate** — compiles the proposal and calls `get_config()` via `exec` to confirm the contract is met.
3. **Evaluate** — runs a 50-game head-to-head match (candidate A vs baseline B) using `evaluator.run_match()`.
4. **Accept/reject** — keeps the candidate if win rate ≥ 55% **and** avg ≤ 0.5 s/move; otherwise reverts. Appends a row to `results.csv` either way.

### PST isolation trick

`engine.py` stores piece-square tables in module-level globals (`_PST`, `_MATE_LOWER`, `_MATE_UPPER`) that are overwritten by every `build_engine()` call, making two simultaneously-configured engines impossible in one process. `search.py` works around this with `_PSTIsolatedEngine`: a wrapper that snapshots each engine's PST at construction time and swaps the module globals in/out around every `think()` call. This enables a fair head-to-head between a candidate config and baseline without subprocess overhead.

### Config space

`config.py` exposes these tunable knobs (all others are off-limits):

- `PIECE_VALUES` — material values in centipawns (P/N/B/R/Q; avoid changing K)
- `PST_SCALE` — uniform multiplier on all piece-square table entries
- `PST_OVERRIDES` — per-piece table replacements (64-entry tuples)
- `QS_LIMIT` — minimum capture gain to extend quiescence search
- `EVAL_ROUGHNESS` — MTD-bi aspiration window width
- `DRAW_TEST` — whether to detect repetitions during search
- `TABLE_SIZE` — transposition table cap
- `MOVE_ORDERING` — `"default"` | `"mvv_lva"` | `"random"`
- `TIME_PER_MOVE`, `EARLY_EXIT_MARGIN` — time management

The `get_config()` function at the bottom of `config.py` is the contract boundary — it must remain callable and return all 11 expected keys.

### Evaluation protocol (v1-2026-04, locked)

50 games, 0.1 s/move, 4-ply random opening (seeded), alternating colors, 200-ply move limit. Results are deterministic given the same seed and Python version. Note: the evaluator uses integer arithmetic for per-game seeds (`seed * 100_000 + game_idx`) to maintain Python 3.12 compatibility.

### Success criteria

A candidate config is accepted when:
1. Win rate ≥ 55% vs baseline over 50 games
2. Avg sec/move ≤ 0.5
3. Smoke test still passes (`python test_engine.py`)
