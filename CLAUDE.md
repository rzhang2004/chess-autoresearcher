# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Smoke test (must print "all smoke tests passed")
python test_engine.py

# Run the autoresearch loop (requires ANTHROPIC_API_KEY)
ANTHROPIC_API_KEY=sk-ant-... python search.py
ANTHROPIC_API_KEY=sk-ant-... python search.py --max-iterations 20 --quiet

# Run a match manually (sequential)
python evaluator.py --mode sunfish_vs_sunfish --n-games 50 --time-per-move 0.1 --seed 2026 --log-dir logs --csv results.csv --notes "label"
python evaluator.py --mode sunfish_vs_random  --n-games 50 --time-per-move 0.1 --seed 2026 --log-dir logs --csv results.csv

# Parallel evaluation (~6.7× faster on a multi-core box) — call from Python:
#   evaluator.run_match_parallel(candidate_cfg, baseline_cfg, n_games=50, n_workers=8, seed=...)

# Hand-curated round runner (used when ANTHROPIC_API_KEY isn't available to subprocesses)
python run_5_iterations.py

# Week 4 controlled experiment set (3 experiments, ~50 min on 8 cores)
python run_week4_experiments.py

# CI regression (fast, 4 games)
python evaluator.py --mode sunfish_vs_random --n-games 4 --time-per-move 0.02 --opening-plies 2 --move-limit 60 --seed 9999 --log-dir /tmp/logs --csv /tmp/results.csv --notes "ci"
```

Install the one non-stdlib dependency before running `search.py`:
```bash
pip install anthropic
```

On Windows, set `PYTHONIOENCODING=utf-8` before any script that prints non-ASCII; the default cp1252 console will crash on em-dashes/arrows.

## Architecture

### Frozen vs. editable files (Week 4+)

| File | Status | Purpose |
|------|--------|---------|
| `engine.py` | **editable, single-axis only** | Sunfish reconstruction (120-board, MTD-bi, PSTs, quiescence, null-move). Modifications must be gated behind a `cfg["enable_xxx"]` flag and preserve the protocol — see `program.md` §"Engine modifications". |
| `evaluator.py` | **protocol locked, implementation editable** | Match runner. Game rules, draw detection, color alternation, seed schedule are immutable. Implementation changes (e.g., the `run_match_parallel` multiprocessing path) are allowed if they preserve game outcomes. |
| `test_engine.py` | **frozen** | Smoke tests |
| `program.md` | **frozen** | Agent contract / rules |
| `config.py` | **editable** | All tunable knobs |
| `best_config.yaml` | **editable** | Updated by `search.py` on each KEEP (still empty as of 36 runs; 0 KEEPs) |
| `results.csv` | **append-only** | Experiment log; never rewrite existing rows |
| `search.py` | frozen post-implementation | The optimization loop itself |

### The optimization loop (`search.py`)

`search.py` is the autoresearch harness. Each iteration:

1. **Propose** — calls Claude API (`claude-sonnet-4-6` by default; override with `AUTORESEARCH_MODEL` env var) with current `config.py`, recent `results.csv`, and `program.md`. Claude returns a modified `config.py` in a `\`\`\`python` block.
2. **Validate** — compiles the proposal and calls `get_config()` via `exec` to confirm the contract.
3. **Evaluate** — runs a 50-game head-to-head match (candidate A vs baseline B) via `evaluator.run_match()`. The parallel-runner scripts (`run_5_iterations.py`, `run_week4_experiments.py`) use `evaluator.run_match_parallel()` for ~6.7× speedup.
4. **Accept/reject** — keeps the candidate if win rate ≥ 55% **and** avg ≤ 0.5 s/move; otherwise reverts. Appends a row to `results.csv` either way.

`search.py` is built to be called by an LLM, but the API key isn't always available to child processes (Claude Code masks it from subprocesses). The two hand-curated round runners (`run_5_iterations.py`, `run_week4_experiments.py`) exist so an in-conversation Claude can act as the proposer directly.

### PST isolation trick (in `search.py` and `evaluator.py`)

`engine.py` stores piece-square tables in module-level globals (`_PST`, `_MATE_LOWER`, `_MATE_UPPER`) that are overwritten by every `build_engine()` call, so two simultaneously-configured engines can't coexist in one process. Both `search._PSTIsolatedEngine` and `evaluator._PSTIsolatedEngineMP` solve this the same way: snapshot each engine's PST at construction and swap the module globals in/out around every `think()` call. The MP version exists so the parallel evaluator's worker processes use the same pattern.

### Config space (`config.py::get_config()` returns 12 keys)

| Key | Notes |
|---|---|
| `piece_values` | P/N/B/R/Q/K material values (cp); avoid changing K (sentinel) |
| `pst_base`, `pst_scale`, `pst_overrides` | Piece-square tables; uniform scale or per-piece replacement (64-entry tuples) |
| `qs_limit` | Min capture gain to extend quiescence (baseline 219) |
| `eval_roughness` | MTD-bi aspiration window width |
| `draw_test` | Detect repetitions during search |
| `table_size` | Transposition-table cap |
| `move_ordering` | `"default"` \| `"mvv_lva"` \| `"random"` |
| `time_per_move`, `early_exit_margin` | Time management; `time_per_move` is **overridden by the evaluator** so config edits to it don't affect matches |
| `enable_null_move` | Algorithm toggle for `engine.Searcher.bound` null-move pruning (added Week 4) |

The `get_config()` function at the bottom of `config.py` is the contract boundary — it must remain callable and return all 12 keys.

### Evaluation protocol (`v1-2026-04`, locked)

50 games per batch, 0.1 s/move, 4-ply random opening (seeded), alternating colors, 200-ply move limit, integer per-game seed `seed * 100_000 + game_idx` (Python-3.12 safe; tuple seeds were removed in 3.12).

**The protocol is NOT actually deterministic across runs.** Iterative-deepening is wall-clock bounded inside `engine.SunfishEngine.think`, so different system load → different search depths → different chosen moves. Even two parallel runs with the same seed produce different results. Treat seed as a randomization tag, not a reproducibility key. This is the central finding behind Week 4's "Signal Failure" diagnosis.

### Success criteria

A candidate config is accepted when:
1. Win rate ≥ 55% vs baseline over 50 games
2. Avg sec/move ≤ 0.5
3. Smoke test still passes (`python test_engine.py`)

**Empirical caveat**: 6 pooled baseline-vs-baseline runs from Week 4 averaged 55.0% (σ ≈ 4). The 55% threshold sits *at the noise floor*, so any single-batch "KEEP" decision is statistically indistinguishable from accepting the baseline against itself. See `autoresearch_log.md` and `week4_controlled_experiment_set.md`.

### Key data artifacts

| File | What it tracks |
|---|---|
| `results.csv` | One row per match. Notes column encodes iteration/experiment/status. |
| `week4_results_matrix.csv` | Structured (experiment, axis, level, seed) → outcome table for the controlled experiment set. |
| `autoresearch_log.md` | Narrative log of all 36 runs (15 search-loop iterations + 20 Week 4 controlled + 1 ad-hoc). |
| `week4_controlled_experiment_set.md` | Pre-registration + results for the 3 controlled experiments. |
| `logs/*.json` | Per-match summary + full game traces. |
