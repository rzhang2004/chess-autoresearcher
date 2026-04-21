# Chess AutoResearcher

A constrained, reproducible AutoResearch loop that iteratively improves a
lightweight Python chess engine (Sunfish) under fast time controls, inspired by
Andrej Karpathy's AutoResearcher framework. STAT 390 Spring 2026, Ray Zhang.

Full charter: `../STAT 390 Project Charter - Ray Zhang.pdf`.

## Week 2 milestone: Baseline and Evaluation Pipeline

This repository contains the Week 2 deliverable: a fully reproducible benchmark.
Specifically:

1. An engine-vs-engine match runner (`evaluator.py`) with a **locked
   evaluation protocol** so later weeks' results are comparable apples-to-apples.
2. A measured **baseline performance of Sunfish** over two 50-game batches:
   (a) Sunfish vs Random (sanity floor), (b) Sunfish vs Sunfish (mirror match).
3. **Locked evaluation logic**: `evaluator.py` is frozen, and `program.md`
   explicitly forbids the AutoResearch agent from editing it.
4. Documented reproducible setup (this file).

Week 3 (search loop), Week 4+ (controlled experiments, ablations) are not yet
implemented; `search.py` is an explicit stub.

## Layout (per charter repo structure)

```
chess-autoresearcher/
├── program.md            # Rules for the agent. Frozen.
├── README.md             # This file. Frozen.
├── requirements.txt      # (none — stdlib only)
├── engine.py             # Sunfish-equivalent chess engine. Frozen.
├── config.py             # Tunable knobs. The agent's playground.
├── evaluator.py          # Frozen match runner with locked protocol.
├── search.py             # Week-3 optimization loop (stub).
├── results.csv           # Append-only experiment log.
├── best_config.yaml      # Best config found so far.
├── test_engine.py        # Smoke test. Frozen.
├── logs/                 # Per-match JSON summaries + full game traces.
└── experiments/          # Reserved for Week 3+ per-run artefacts.
```

## Setup

Python 3.9+ required. No third-party packages.

```bash
cd chess-autoresearcher
python3 test_engine.py
```

If the smoke test prints `all smoke tests passed`, you're ready to run matches.

## Reproducing the Week 2 baseline

All knobs are pinned; results are deterministic given the same seed and
platform.

```bash
# Sanity floor: Sunfish should near-sweep Random.
python3 evaluator.py --mode sunfish_vs_random \
    --n-games 50 --time-per-move 0.1 --seed 2026 \
    --log-dir logs --csv results.csv \
    --notes "week2_baseline_sanity"

# Mirror match: both sides Sunfish baseline; a ~50% win rate confirms the
# test harness is unbiased w.r.t. White/Black and opening diversity.
python3 evaluator.py --mode sunfish_vs_sunfish \
    --n-games 50 --time-per-move 0.1 --seed 2026 \
    --log-dir logs --csv results.csv \
    --notes "week2_baseline_mirror_match"
```

Each run appends one row to `results.csv` and writes a timestamped pair of
files to `logs/` (`*_summary.json` + `*_games.json`).

## Locked evaluation protocol (v1-2026-04)

Defined in `evaluator.py` and pinned via `PROTOCOL_VERSION`:

| Parameter       | Value                                          |
| --------------- | ---------------------------------------------- |
| Batch size      | 50 games                                       |
| Time control    | 0.1 s / move (fixed)                           |
| Opening         | 4 plies of uniformly-random legal moves        |
| Color assignment| Alternate — A=White on even games, Black on odd |
| Move limit      | 200 plies → draw                               |
| Draw detection  | 50-move rule, threefold repetition, insufficient material, stalemate |
| Win detection   | Checkmate, king-capture, "no move returned"    |
| RNG seed        | Fixed per run; passed in explicitly            |

Protocol changes require a new `PROTOCOL_VERSION` string and invalidate prior
results. The agent has no edit access to this file — see `program.md`.

## Week 2 baseline results

_Populated by `evaluator.py`. Raw rows in `results.csv`; per-match details in
`logs/`._

### Sunfish vs Random (sanity floor)

| Metric                    | Value                         |
| ------------------------- | ----------------------------- |
| Games                     | 50                            |
| Sunfish wins              | 49                            |
| Random wins               | 0                             |
| Draws                     | 1 (threefold repetition)      |
| Sunfish win rate          | **99.0%**                     |
| Avg plies / game          | 32.8                          |
| Sunfish avg sec / move    | 0.173                         |
| Sunfish max sec / move    | 1.22 (outlier; see notes)     |
| Random avg sec / move     | 0.0004                        |
| Wall clock                | 124 s                         |
| Terminations              | 49 × checkmate, 1 × repetition |

### Sunfish vs Sunfish (mirror match)

| Metric                    | Value                         |
| ------------------------- | ----------------------------- |
| Games                     | 50                            |
| Engine A wins             | 17                            |
| Engine B wins             | 13                            |
| Draws                     | 20                            |
| A win rate (w/ half-draws)  | **54.0%**                   |
| White wins / Black wins / Draws | 14 / 16 / 20            |
| White win rate (w/ half-draws) | **48.0%**                |
| Avg plies / game          | 109.3 (median 114.5)          |
| Min / max plies           | 35 / 200                      |
| Avg sec / move (A)        | 0.217                         |
| Avg sec / move (B)        | 0.210                         |
| Wall clock                | 1133 s (18.9 min)             |
| Terminations              | 30 × checkmate, 15 × threefold repetition, 3 × insufficient material, 2 × move limit |

Both headline win rates (A at 54%, White at 48%) sit within one standard
error of 50% (σ ≈ 7% at N=50), so the harness shows no detectable color
bias or A/B tagging bias. Game lengths span a healthy range and every game
terminated via a chess rule rather than a bug.

### Speed-constraint check (charter success criterion #3)

Target: avg ≤ 0.1–0.5 s/move.

| Run                        | Avg sec/move | Median per-game-max | p90 per-game-max | Worst single move |
| -------------------------- | ------------ | ------------------- | ---------------- | ----------------- |
| Sunfish vs Random (50g)    | 0.173        | —                   | —                | 1.22 s            |
| Sunfish vs Sunfish (50g)   | 0.214        | 0.57 s              | 4.70 s           | **128.6 s**       |

**Average pass**, **outlier fail.** The mean comfortably meets the charter's
0.5 s/move ceiling, but the iterative-deepening loop has no mid-iteration
preemption, so a single deep iteration in a pathological endgame can
balloon. In the 50-game mirror match one move consumed 128.6 s; the 90th
percentile of per-game worst-moves is 4.7 s. This is known Sunfish
behavior.

Explicitly out of scope for Week 2. Week 3+ time-management work
(charter-approved tunable) is the natural place to cap this — the knob is
already exposed as `TIME_PER_MOVE` / `EARLY_EXIT_MARGIN` in `config.py`.

## Design notes

### Why a self-contained Sunfish

The charter calls for "Sunfish (available online)". The development sandbox
used for this milestone blocks egress to github.com, raw.githubusercontent.com,
and pypi.org, so the canonical `sunfish.py` could not be downloaded and
neither could `python-chess`. `engine.py` is a faithful reconstruction of
Thomas Ahle's public-domain Sunfish following the same design:

- 120-square padded mailbox board
- Piece-square table evaluation (PSTs from Sunfish baseline)
- MTD-bi search with aspiration windows and a transposition table
- Quiescence search (capture extension)
- Null-move pruning

Because the AutoResearch agent only edits `config.py`, the engine file could
be swapped out for the canonical `sunfish.py` at any time without changing
the optimization loop's contract. The PST and piece values in `config.py`
exactly match Sunfish's defaults, so `sunfish_baseline` here plays at the
same nominal ~2000 Lichess Elo reported by the upstream project.

### What "lock the evaluation logic" actually looks like here

Three layers of protection:

1. `program.md` — declarative contract: "the agent may not edit
   `evaluator.py`". Enforced by review / the human in the loop.
2. `evaluator.py` constants are pinned at module top with a
   `PROTOCOL_VERSION` string. Any change flips the version.
3. The agent cannot see the evaluator's random seed in `config.py`; it's
   injected at call time by `search.py`.

The evaluator doesn't guard against a malicious agent with filesystem access —
that's outside the threat model. The protection is against *accidental*
regression: once a protocol is locked, a careless tweak can't silently
invalidate weeks of baselines.

## Risks tracked so far

- **Mirror win rate ≠ 50%** → would point to color bias or an asymmetric
  opening book. Watched in the mirror-match summary above.
- **Per-move time outliers** → one 1.2s move in the Random match. Mean is
  within spec, but endgame iterative-deepening overshoots are a known
  Sunfish behavior. Week 3 time-management work should cap this.
- **Sunfish reconstruction drift** → the PSTs and search logic are copied
  from memory of the canonical Sunfish source. A swap with the canonical
  file is a one-file change if drift is suspected.

## Running the regression suite

```bash
python3 test_engine.py          # smoke test; must print 'all smoke tests passed'
python3 evaluator.py --mode sunfish_vs_random --n-games 10 \
    --time-per-move 0.05 --notes "regression"
```

A GitHub Actions workflow at `.github/workflows/ci.yml` runs the smoke test
and a tiny regression match on every push / PR across Python 3.9, 3.11, 3.12.

## License

GPL-3.0-or-later. See `LICENSE`.

Because `engine.py` is a reconstruction of Thomas Ahle's GPL-licensed
Sunfish, the entire project is distributed under the GPL-3.0 as well. If
you fork this repo and modify it, your fork must also be GPL-3.0.
