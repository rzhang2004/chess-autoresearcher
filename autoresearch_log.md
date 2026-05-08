# AutoResearch Log — Chess Engine (Sunfish) Config Optimization

**Project**: STAT 390, Ray Zhang
**Protocol**: v1-2026-04 | 50 games/batch | 0.1s/move | 4-ply random opening | seed varies
**Success criterion**: ≥55% win rate vs baseline AND avg ≤0.5s/move
**Baseline** (Week 2, seed=2026): 54.0% mirror match, 99.0% vs random

---

## Week 2 — Baseline Establishment (2026-04-17)

Two 50-game runs to establish the reference point.

| Run | Result | Notes |
|-----|--------|-------|
| Sunfish vs Random | **99.0%** (49W 0L 1D) | Sanity floor confirmed |
| Sunfish vs Sunfish (mirror) | **54.0%** (17W 13L 20D) | Within 1σ of 50%; no color bias |

Avg speed: 0.173–0.217s/move. One 128.6s outlier in the mirror match (known Sunfish iterative-deepening behavior in endgames). Mean well within spec.

---

## Week 3 — Optimization Loop (2026-04-23 to 2026-04-24)

15 iterations run in three rounds of 5. All evaluated head-to-head against the locked baseline using `_PSTIsolatedEngine` (swaps module-level PST globals around each `think()` call to enable fair comparison in a single process).

### Round 1 — Broad Exploration

**Hypothesis space**: PST scaling, quiescence depth, piece values, search parameters, move ordering.

| # | Config change | W | L | D | Win% | Avg s/mv | Decision |
|---|--------------|---|---|---|------|---------|---------|
| 1 | PST_SCALE 1.0→1.15 | 14 | 16 | 20 | 48.0% | 0.174 | DISCARD |
| 2 | QS_LIMIT 219→100 | 19 | 15 | 16 | 54.0% | 0.354 | DISCARD |
| 3 | N 280→300, B 320→340 | 10 | 22 | 18 | 38.0% | 0.179 | DISCARD |
| 4 | EVAL_ROUGHNESS 13→7 | 16 | 17 | 17 | 49.0% | 0.191 | DISCARD |
| 5 | MOVE_ORDERING→mvv_lva | 18 | 16 | 16 | 52.0% | 0.271 | DISCARD |

**Round 1 findings**:
- **QS_LIMIT=100** was closest (54.0%) but avg 0.354s/move — 2× slower than baseline. Speed cost outweighed tactical gain at this threshold.
- **MOVE_ORDERING=mvv_lva** second-closest (52.0%). MVV-LVA capture ordering improves alpha-beta cutoffs but not enough alone.
- **PST_SCALE=1.15** hurt (48%): more positional emphasis made play worse.
- **Minor pieces +20cp** worst result (38%): large piece value changes create systematic positional misconceptions. Piece values are highly sensitive.
- **EVAL_ROUGHNESS=7** no improvement (49%).

### Round 2 — Refined Exploration

**Hypothesis space**: Moderate QS tuning, opposite PST direction, combining near-misses, small piece value nudge, search pruning.

| # | Config change | W | L | D | Win% | Avg s/mv | Decision |
|---|--------------|---|---|---|------|---------|---------|
| 6 | QS_LIMIT 219→150 | 19 | 15 | 16 | 54.0% | 0.213 | DISCARD |
| 7 | PST_SCALE 1.0→0.9 | 9 | 14 | 27 | 45.0% | 0.180 | DISCARD |
| 8 | mvv_lva + QS_LIMIT→170 | 10 | 24 | 16 | 36.0% | 0.236 | DISCARD |
| 9 | R 479→495 (+16cp) | 16 | 12 | 22 | 54.0% | 0.195 | DISCARD |
| 10 | DRAW_TEST→False | 15 | 14 | 21 | 51.0% | 0.204 | DISCARD |

**Round 2 findings**:
- **QS_LIMIT=150** matched the 54.0% of QS_LIMIT=100 but at 0.213s/move (vs 0.354) — much better speed profile.
- **Rook +16cp** also hit 54.0%: small value nudges are safer than large ones.
- **PST_SCALE=0.9 hurt** (45%): both directions of PST scaling hurt. Baseline 1.0 appears optimal.
- **mvv_lva + QS_LIMIT=170 combined** was worst of round 2 (36%). The two changes interfere rather than stack.
- **DRAW_TEST=False** (51%): removing repetition detection from search neither helped nor hurt significantly.

### Round 3 — Validation

**Goal**: Re-test the apparent near-misses at *fresh seeds* to distinguish real signal from sampling noise.

| # | Config change | W | L | D | Win% | Avg s/mv | Decision |
|---|--------------|---|---|---|------|---------|---------|
| 11 | QS_LIMIT 219→180 | 15 | 18 | 17 | 47.0% | 0.222 | DISCARD |
| 12 | MOVE_ORDERING→mvv_lva (re-seed) | 11 | 23 | 16 | 38.0% | 0.213 | DISCARD |
| 13 | R 479→490 (+11cp) | 17 | 15 | 18 | 52.0% | 0.198 | DISCARD |
| 14 | P 100→105 (+5cp) | 20 | 17 | 13 | 53.0% | 0.190 | DISCARD |
| 15 | QS_LIMIT=150 + R=495 (combo) | 19 | 17 | 14 | 52.0% | 0.179 | DISCARD |

**Round 3 findings — the validation cohort killed the apparent signals**:
- **`mvv_lva` re-seeded fell from 52% → 38%** — its earlier near-miss was *noise*.
- **`qs_limit_180` came in at 47%** — the QS_LIMIT 100 / 150 trend (both 54%) was *noise*.
- **`rook_value_490` (+11cp) → 52%** — smaller version of the +16cp 54% result, still in the noise band.
- **`pawn_value_105` (+5cp) → 53%** — the only previously-untouched parameter; modest result, also indistinguishable from noise.
- **`combo_qs150_rook495` → 52%** — stacking two 54% candidates from different mechanisms produced no additivity.

After round 3, **none of the 15 hand-curated single-parameter changes produces an effect distinguishable from sampling noise.**

---

## Summary After 15 Iterations

**KEEPs**: 0 / 15
**Win rate distribution**:

```
36  38  38  45  47  48  49  51  52  52  52  53  54  54  54
↑ worst (×2)                                       ↑ best (×3)
                Baseline mirror = 54
                Threshold       = 55  (never cleared)
```

Median = 51%; mean = 49.0%. The empirical distribution is centered just below 50% and dispersed roughly ±8pp — nearly indistinguishable from a fair-coin null at 50 trials.

Three structural observations:

1. **Baseline Sunfish parameters are near-optimal.** Single-axis perturbations either hurt or land within noise. Consistent with Sunfish's decade of tuning history.
2. **Statistical noise is the binding constraint.** At 50 games, σ ≈ 7%. Detecting a +5pp effect at 80% power requires ~200 games — 4× more compute per evaluation.
3. **Apparent near-misses fail validation runs.** Three "54%" results (QS_LIMIT 100, QS_LIMIT 150, R+16) all reverted to ≤52% when re-tested at fresh seeds.

---

## Week 4 — Controlled Experiments (2026-05-06)

A formal pivot from "try things in the loop" to **structured causal evidence**. Three experiments, each varying ONE axis with all other config explicitly fixed and replicated across two seeds. Run via the new parallelised `evaluator.run_match_parallel()` (8 workers → 6.7× wall-clock speedup; full plan in 50 min vs 5h).

The autoresearch contract was relaxed (per `program.md`) to allow controlled `engine.py` modifications behind config-flag gates. Experiment C exercises that path.

See [`week4_controlled_experiment_set.md`](week4_controlled_experiment_set.md) for the full pre-registration; [`week4_results_matrix.csv`](week4_results_matrix.csv) for raw rows.

### Experiment A — `QS_LIMIT` sweep (search axis, 5 levels × 2 seeds = 500 games)

| Level | seed 4001 | seed 4002 | Mean | Std |
|---|---:|---:|---:|---:|
| qs_50 | 61% | 48% | 54.5% | 9.2 |
| qs_100 | 40% | 60% | 50.0% | 14.1 |
| qs_150 | 49% | 47% | 48.0% | 1.4 |
| **qs_219 (baseline)** | **56%** | **57%** | **56.5%** | **0.7** |
| qs_300 | 40% | 52% | 46.0% | 8.5 |

No coherent dose-response curve. The null condition (candidate ≡ baseline) returned ~56.5%, well above the 50% it should average to over many runs.

### Experiment B — `PST_SCALE` sweep (eval axis, 3 levels × 2 seeds = 300 games)

| Level | seed 4001 | seed 4002 | Mean | Std |
|---|---:|---:|---:|---:|
| pst_0.7 | 57% | 43% | 50.0% | 9.9 |
| **pst_1.0 (baseline)** | **54%** | **52%** | **53.0%** | **1.4** |
| pst_1.3 | 43% | 52% | 47.5% | 6.4 |

All three levels' confidence intervals overlap with each other and with 50%.

### Experiment C — Null-move pruning ablation (algorithm axis, engine.py edit, 200 games)

This required adding `ENABLE_NULL_MOVE: bool = True` to `config.py` and gating the null-move branch in `engine.Searcher.bound`. The change is single-axis, documented, protocol-preserving, and config-flag-defaulted to baseline.

| Level | seed 4001 | seed 4002 | Mean | Std |
|---|---:|---:|---:|---:|
| **null_move_on (baseline)** | **61%** | **50%** | **55.5%** | **7.8** |
| null_move_off | 53% | 42% | 47.5% | 7.8 |

8pp drop in the predicted direction, but 95% CIs of the two levels overlap. The pre-registered hypothesis was a *much larger* effect; that prediction is partially falsified — either Sunfish's null-move pruning contributes less than expected, or the metric is too noisy to resolve it at N=50.

### Cross-experiment null-condition pooling

The three experiments collectively include **six baseline-vs-baseline runs** (qs_219 ×2, pst_1.0 ×2, null_move_on ×2). Pooled:

```
[56, 57, 54, 52, 61, 50]   →  mean = 55.0%,  std = 4.0%
```

**The 55% acceptance threshold equals the mean of the null condition.** Any candidate's "win" against baseline is statistically indistinguishable from the candidate-equals-baseline case at 50 games per evaluation.

---

## Cumulative Results — 35 Total Runs (15 search-loop + 20 controlled)

```
Win-rate distribution across all 35 candidate runs:

36  38  38  40  40  42  43  43  45  47  47  48  48  49  49  50  50  51  52  52  52  52  52  53  53  54  54  54  56  57  57  60  61  61  61
                        median (51) ↑                          baseline-vs-baseline pooled mean = 55%
```

**Total KEEPs: 0.** The dominant failure mode is **Signal Failure** under the four-category Week 4 taxonomy — the loop runs cleanly but cannot produce interpretable evidence at the current N=50 batch size.

Full taxonomy breakdown for all 35 runs:

| Category | Count | Examples |
|---|---:|---|
| **Signal Failure** | 32 | All 15 Round 1-3 runs + most controlled levels (in 38-57% noise band) |
| **Evaluation Leakage** | 2 | Round-1 #2 (qs_limit_100 spent 0.354s/move — unfair compute share); Round-2 #8 |
| **Code Instability** | 1 | Python-3.12 tuple-seed bug in `evaluator.py` (fixed in Week 3 setup) |
| **Agent Misbehavior** | 0 | All experiments hand-curated; no agent went rogue |

---

## Open Uncertainty

1. **Is the metric's A-side bias (~55% null mean) real or sample-bound?** Six replicates is not enough to characterize. To decide: run 20+ baseline-vs-baseline replicates.
2. **Does null-move pruning contribute more than 8pp at higher N?** The Experiment C effect is in the predicted direction but underwhelming. Re-run at N=200 to resolve.
3. **Are there any single-axis changes outside the noise band?** Across 35 runs, no. But 35 is sparse coverage of the config space.

---

## Next Steps

The lesson from 35 runs is unambiguous: **N=50 is too small to learn anything**. The most impactful change is to the *evaluation protocol*, not the *search loop*:

| Priority | Action | Rationale |
|---|---|---|
| 1 | Bump batch size to N=200 | σ drops 7% → 3.5%; threshold becomes ~1.4σ above null (currently 0.7σ). |
| 2 | Always run ≥3 seed replicates per level | Single-seed reads are uninterpretable per the Week 4 evidence. |
| 3 | Add power analysis to `search.py` | Reject any KEEP whose CI overlaps the null condition's CI. |
| 4 | Re-test `null_move_off` at N=200 | Highest-effect-size candidate from controlled set; deserves resolution. |
| 5 | Plot raw per-game outcomes, not just batch means | Visualize game-length and termination-reason distributions for under-the-mean diagnosis. |
