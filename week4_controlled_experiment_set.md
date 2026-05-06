# Week 4 Controlled Experiment Set

**Project:** Chess AutoResearcher (STAT 390 Capstone)
**Author:** Ray Zhang
**Date:** Week 4
**Runner:** [`run_week4_experiments.py`](run_week4_experiments.py)
**Results matrix:** [`week4_results_matrix.csv`](week4_results_matrix.csv)

Three experiments, each varying exactly one axis with all other config
explicitly held fixed and replicated across two seeds for stability
assessment. Total: 1000 games (20 fifty-game matches), ~50 min wall time
on 8 cores via `evaluator.run_match_parallel()`.

---

## Conditions held fixed across ALL experiments

These never change between runs; they define "comparability" per the
Week 4 rubric.

| Variable | Value | Source |
|---|---|---|
| Protocol version | `v1-2026-04` | `evaluator.PROTOCOL_VERSION` |
| Batch size | 50 games | `evaluator.DEFAULT_BATCH_SIZE` |
| Time per move | 0.1 s | passed to `run_match_parallel()` |
| Opening plies | 4 random legal | `evaluator.DEFAULT_OPENING_PLIES` |
| Move limit | 200 plies → draw | `evaluator.DEFAULT_MOVE_LIMIT` |
| Color alternation | A=White on even games, Black on odd | locked |
| Per-game RNG seed | `seed * 100_000 + game_idx` | `evaluator._play_one_game` |
| Baseline opponent | `sunfish_baseline` (current `config.py`) | unchanged across all 20 runs |
| Worker count | 8 (parallel) | `n_workers=8` |
| Replicate seeds | `{4001, 4002}` | new for Week 4 (no overlap with prior rounds) |
| Engine source | `engine.py` (single-axis edit only in Exp C) | committed at SHA `dcebd41` |

**Pre-declared metrics** (chosen before running):
1. **Win rate (%)** of candidate (engine A) vs. baseline (engine B), with
   draws counted as 0.5 — primary metric.
2. **Average seconds per move** for engine A — secondary, for the speed
   constraint (≤0.5 s/move).
3. **Average plies per game** — tertiary, for game-character description
   (e.g., positional play tends to lengthen games).

---

## Experiment A — `QS_LIMIT` sweep (search axis)

### What changed
The candidate's `QS_LIMIT` parameter (minimum capture-gain in centipawns
to extend quiescence search). Lower = deeper quiescence (more captures
considered at search leaves) but slower. Higher = shallower / faster.

### What stayed fixed
Every other config knob is identical to baseline:
`PIECE_VALUES`, `PST_BASE`, `PST_SCALE=1.0`, `PST_OVERRIDES` (all None),
`EVAL_ROUGHNESS=13`, `DRAW_TEST=True`, `TABLE_SIZE=10_000_000`,
`MOVE_ORDERING="default"`, `TIME_PER_MOVE=0.1`, `EARLY_EXIT_MARGIN=0.8`,
`ENABLE_NULL_MOVE=True`. `engine.py` is unmodified.

### Levels (5)
| Level | `QS_LIMIT` | Notes |
|---|---:|---|
| qs_50 | 50 | Aggressive: extend most captures |
| qs_100 | 100 | Moderate-deep |
| qs_150 | 150 | Mild-deep |
| **qs_219** | **219** | **Baseline (control / null condition)** |
| qs_300 | 300 | Shallower than baseline |

### Replication
Each level run twice with seeds `4001` and `4002`. Total: 10 runs × 50 games = 500 games.

### Pre-registered hypothesis
A U-shape on win-rate-vs-`QS_LIMIT`: too low slows the engine without
proportional tactical gain; too high misses captures. Sweet spot
expected near 100–150 if the metric has signal.

### Result (mean across 2 seeds)
| Level | seed 4001 | seed 4002 | Mean | Std (n=2) |
|---|---:|---:|---:|---:|
| qs_50 | 61% | 48% | 54.5% | 9.2 |
| qs_100 | 40% | 60% | 50.0% | 14.1 |
| qs_150 | 49% | 47% | 48.0% | 1.4 |
| **qs_219 (baseline)** | **56%** | **57%** | **56.5%** | **0.7** |
| qs_300 | 40% | 52% | 46.0% | 8.5 |

### Stability assessment
**Unstable.** Three of five levels have within-level std > 8 percentage
points across just 2 seeds. The null condition (qs_219, candidate ≡
baseline) returned 56–57% rather than the 50% it should have averaged
to — meaning the metric has a measurable A-side bias of ~6pp on top of
the sampling noise.

---

## Experiment B — `PST_SCALE` sweep (eval axis)

### What changed
The candidate's `PST_SCALE` (uniform multiplier on all piece-square-table
entries). 1.0 is baseline. Higher = more positional weight; lower = more
material-first play.

### What stayed fixed
Every other config knob = baseline. Same fixed conditions as Exp A.
`engine.py` unmodified.

### Levels (3)
| Level | `PST_SCALE` | Notes |
|---|---:|---|
| pst_0.7 | 0.7 | -30% positional weight |
| **pst_1.0** | **1.0** | **Baseline (control)** |
| pst_1.3 | 1.3 | +30% positional weight |

### Replication
Each level run twice with seeds `4001` and `4002`. Total: 6 runs × 50 games = 300 games.

### Pre-registered hypothesis
Symmetric drop on either side of 1.0 (rounds 1–2 already saw both 0.9 →
45% and 1.15 → 48%). Baseline PST scale is approximately optimal.

### Result (mean across 2 seeds)
| Level | seed 4001 | seed 4002 | Mean | Std (n=2) |
|---|---:|---:|---:|---:|
| pst_0.7 | 57% | 43% | 50.0% | 9.9 |
| **pst_1.0 (baseline)** | **54%** | **52%** | **53.0%** | **1.4** |
| pst_1.3 | 43% | 52% | 47.5% | 6.4 |

### Stability assessment
**Mostly noise.** All three levels' confidence intervals overlap with
each other and with the 50% null. The baseline level (pst_1.0,
candidate ≡ baseline) is again above 50% — confirming the same A-side
bias seen in Experiment A.

---

## Experiment C — Null-move pruning ablation (algorithm axis)

### What changed
The candidate's `ENABLE_NULL_MOVE` config flag, which gates the
null-move pruning branch in `engine.Searcher.bound`.

### What stayed fixed
Every other config knob = baseline. Same fixed conditions.

### Engine modification (controlled, single-axis)
This is the **one experiment** that requires editing `engine.py`. Per
`program.md`'s engine-modification rules, the change is:

1. **Single-axis:** only the null-move branch is gated.
2. **Documented:** see commit `dcebd41`; new flag added to
   `config.py::get_config()` and read in `engine.py` line 268.
3. **Protocol-preserving:** position legality, game-end detection, the
   `build_engine()` / `think()` API are all unchanged. Determinism-given-
   seed property is preserved.
4. **Config-flag-gated:** `cfg.get("enable_null_move", True)` — defaults
   to `True` so all prior experiments and the baseline are unaffected.

The relevant diff:
```python
# engine.py line 266-271 (after change):
def moves():
    # Null-move pruning ... Gated by cfg["enable_null_move"] for ablations.
    if (self.cfg.get("enable_null_move", True)
            and depth > 0 and not root
            and any(c in pos.board for c in "RBNQ")):
        yield None, -self.bound(pos.nullmove(), 1 - gamma, depth - 3, root=False)
```

### Levels (2)
| Level | `enable_null_move` | Notes |
|---|---|---|
| **null_move_on** | **True** | **Baseline (control)** |
| null_move_off | False | Disable null-move pruning entirely |

### Replication
Each level run twice with seeds `4001` and `4002`. Total: 4 runs × 50 games = 200 games.

### Pre-registered hypothesis
**Strong-effect prediction:** disabling null-move should hurt
*dramatically* (well outside the noise band), proving that the metric
IS sensitive to algorithmic changes. Null-move pruning typically saves
a constant factor in nodes searched at moderate depths; without it the
engine reaches less depth in the same time budget.

### Result (mean across 2 seeds)
| Level | seed 4001 | seed 4002 | Mean | Std (n=2) |
|---|---:|---:|---:|---:|
| **null_move_on (baseline)** | **61%** | **50%** | **55.5%** | **7.8** |
| null_move_off | 53% | 42% | 47.5% | 7.8 |

### Stability assessment
**Effect observed but small.** Mean drops 8pp from on→off (55.5% →
47.5%), in the predicted direction, but the 95% CIs of the two levels
overlap. With only 2 seeds we cannot exclude the possibility that this
is also noise. The hypothesis predicted a *much larger* effect — that
prediction is partially falsified, suggesting either (a) Sunfish's
null-move pruning contributes less than expected, or (b) the metric is
too noisy at N=50 to resolve it.

---

## Summary table — all 20 controlled runs

(Excerpt — full data in [`week4_results_matrix.csv`](week4_results_matrix.csv))

| # | Exp | Axis | Level | Seed | Win % | A s/move | W-L-D |
|--:|-----|------|-------|-----:|------:|---------:|------:|
|  1 | A | qs_limit | qs_50 | 4001 | 61.0 | 0.188 | 22-11-17 |
|  2 | A | qs_limit | qs_50 | 4002 | 48.0 | 0.210 | 17-19-14 |
|  3 | A | qs_limit | qs_100 | 4001 | 40.0 | 0.176 | 10-20-20 |
|  4 | A | qs_limit | qs_100 | 4002 | 60.0 | 0.205 | 22-12-16 |
|  5 | A | qs_limit | qs_150 | 4001 | 49.0 | 0.182 | 18-19-13 |
|  6 | A | qs_limit | qs_150 | 4002 | 47.0 | 0.208 | 16-19-15 |
|  7 | A | qs_limit | qs_219 | 4001 | 56.0 | 0.210 | 19-13-18 |
|  8 | A | qs_limit | qs_219 | 4002 | 57.0 | 0.191 | 22-15-13 |
|  9 | A | qs_limit | qs_300 | 4001 | 40.0 | 0.186 | 13-23-14 |
| 10 | A | qs_limit | qs_300 | 4002 | 52.0 | 0.190 | 19-17-14 |
| 11 | B | pst_scale | pst_0.7 | 4001 | 57.0 | 0.191 | 17-10-23 |
| 12 | B | pst_scale | pst_0.7 | 4002 | 43.0 | 0.199 | 14-21-15 |
| 13 | B | pst_scale | pst_1.0 | 4001 | 54.0 | 0.184 | 21-17-12 |
| 14 | B | pst_scale | pst_1.0 | 4002 | 52.0 | 0.182 | 17-15-18 |
| 15 | B | pst_scale | pst_1.3 | 4001 | 43.0 | 0.187 | 13-20-17 |
| 16 | B | pst_scale | pst_1.3 | 4002 | 52.0 | 0.193 | 17-15-18 |
| 17 | C | enable_null_move | null_move_on | 4001 | 61.0 | 0.192 | 23-12-15 |
| 18 | C | enable_null_move | null_move_on | 4002 | 50.0 | 0.191 | 17-17-16 |
| 19 | C | enable_null_move | null_move_off | 4001 | 53.0 | 0.218 | 19-16-15 |
| 20 | C | enable_null_move | null_move_off | 4002 | 42.0 | 0.218 | 14-22-14 |

---

## Cross-experiment finding: the null-condition baseline

All three experiments include a **baseline-vs-baseline** level (qs_219,
pst_1.0, null_move_on). Pooled across the six baseline-vs-baseline runs:

```
[56, 57, 54, 52, 61, 50]   →  mean = 55.0%,  std = 4.0%
```

The 55% acceptance threshold sits *exactly at the mean of the null
condition*. This is the central piece of evidence supporting the
"Signal Failure" diagnosis in
[`week4_failure_memo.md`](week4_failure_memo.md).
