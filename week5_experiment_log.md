# Week 5 Experiment Log Bundle

**Project:** Chess AutoResearcher (STAT 390 Capstone)
**Author:** Ray Zhang
**Date:** 2026-05-13
**Block:** 10 iterations (#17--#26), autonomous agent-curated
**Runner:** [`run_week5_block.py`](run_week5_block.py)
**Results file:** [`week5_results.csv`](week5_results.csv)
**Plot:** [`week5_metric_trajectory.png`](week5_metric_trajectory.png)

---

## Protocol (held fixed across all 10 runs)

| Variable | Value |
|---|---|
| Protocol version | `v1-2026-04` |
| Batch size | 50 games |
| Time per move | 0.1 s |
| Opening plies | 4 random legal |
| Move limit | 200 plies |
| Color alternation | A=White on even, Black on odd |
| Worker count | 8 (parallel via `run_match_parallel`) |
| Seeds | 5001--5010 (one per iteration, no reuse) |
| Baseline | Locked `config.py` (Sunfish defaults, unchanged since Week 2) |
| Accept criteria | Win rate >= 55% AND avg <= 0.5 s/move |

---

## Complete Run Log

### Iteration 17 -- `table_size_20M`

- **Changed:** `TABLE_SIZE` 10,000,000 -> 20,000,000
- **Hypothesis:** Larger transposition table caches more positions, improving move quality at the same time budget.
- **Result:** 42.0% (W=14 L=22 D=14) | 0.193 s/move | 166.7s wall
- **Decision:** DISCARD (42.0% < 55.0%)
- **Rollback:** Config reverted to baseline. Larger TT actually hurt -- possibly because the hash function distributes poorly at 2x capacity, or memory overhead slows lookups.

### Iteration 18 -- `table_size_5M`

- **Changed:** `TABLE_SIZE` 10,000,000 -> 5,000,000
- **Hypothesis:** If halving TT hurts, it proves TT capacity matters for strength.
- **Result:** 50.0% (W=19 L=19 D=12) | 0.197 s/move | 177.4s wall
- **Decision:** DISCARD (50.0% < 55.0%)
- **Rollback:** Config reverted. 5M TT performed identically to baseline (50% is dead center), suggesting 5M is sufficient for this time control. Combined with iter 17, TT changes in either direction are neutral-to-harmful.

### Iteration 19 -- `eval_roughness_20`

- **Changed:** `EVAL_ROUGHNESS` 13 -> 20
- **Hypothesis:** Wider MTD-bi aspiration window reduces re-searches; engine reaches same depth with fewer iterations.
- **Result:** 50.0% (W=19 L=19 D=12) | 0.193 s/move | 149.7s wall
- **Decision:** DISCARD (50.0% < 55.0%)
- **Rollback:** Config reverted. No measurable effect -- the aspiration window width at this scale does not change which moves are selected.

### Iteration 20 -- `eval_roughness_5`

- **Changed:** `EVAL_ROUGHNESS` 13 -> 5
- **Hypothesis:** Narrower MTD-bi window gives more precise eval at cost of more re-searches per depth.
- **Result:** 54.0% (W=22 L=18 D=10) | 0.200 s/move | 156.3s wall
- **Decision:** DISCARD (54.0% < 55.0%, missed threshold by 1%)
- **Rollback:** Config reverted. **Best result in this block.** However, 54% is indistinguishable from the null condition (Week 4 pooled baseline-vs-baseline mean = 55%, std = 4%). This is the same "near-miss" pattern observed throughout Weeks 3-4.

### Iteration 21 -- `pawn_pst_center`

- **Changed:** `PST_OVERRIDES["P"]` from None to a center-boosted table (+15cp on d4/e4/d5/e5 ranks 3-5)
- **Hypothesis:** Boosting central pawn squares encourages central pawn play.
- **Result:** 44.0% (W=15 L=21 D=14) | 0.211 s/move | 159.2s wall
- **Decision:** DISCARD (44.0% < 55.0%)
- **Rollback:** Config reverted. Center-boosted pawn PST actively hurt -- the engine over-valued central pawn advances at the expense of piece development and king safety.

### Iteration 22 -- `knight_pst_central`

- **Changed:** `PST_OVERRIDES["N"]` from None to a center-boosted table (+10cp on d4/e4/d5/e5 ranks 3-5)
- **Hypothesis:** Boosting knight centralization rewards placing knights on strong central squares.
- **Result:** 47.0% (W=15 L=18 D=17) | 0.186 s/move | 158.4s wall
- **Decision:** DISCARD (47.0% < 55.0%)
- **Rollback:** Config reverted. Knight PST override also hurt. Both PST_OVERRIDES experiments (iters 21-22) show that Sunfish's baseline PSTs are well-calibrated; manual overrides on specific pieces degrade play.

### Iteration 23 -- `bishop_value_330`

- **Changed:** `PIECE_VALUES["B"]` 320 -> 330 (+10cp)
- **Hypothesis:** Small bishop boost reflects the bishop-pair advantage in open positions.
- **Result:** 51.0% (W=19 L=18 D=13) | 0.190 s/move | 167.2s wall
- **Decision:** DISCARD (51.0% < 55.0%)
- **Rollback:** Config reverted. Neutral result -- within noise band. Consistent with Week 3 finding that small piece-value nudges produce effects indistinguishable from chance.

### Iteration 24 -- `queen_value_940`

- **Changed:** `PIECE_VALUES["Q"]` 929 -> 940 (+11cp)
- **Hypothesis:** Small queen boost discourages premature queen trades.
- **Result:** 44.0% (W=16 L=22 D=12) | 0.192 s/move | 155.4s wall
- **Decision:** DISCARD (44.0% < 55.0%)
- **Rollback:** Config reverted. Queen value increase actively hurt. Possibly makes the engine overprotect the queen instead of using it actively.

### Iteration 25 -- `early_exit_0.95`

- **Changed:** `EARLY_EXIT_MARGIN` 0.8 -> 0.95
- **Hypothesis:** Higher margin means engine attempts the next ID depth more often, leading to deeper search and better moves.
- **Result:** 51.0% (W=17 L=16 D=17) | 0.219 s/move | 202.1s wall
- **Decision:** DISCARD (51.0% < 55.0%)
- **Rollback:** Config reverted. Neutral result despite ~13% more time spent per move (0.219 vs ~0.19 baseline). The extra search depth doesn't translate to better moves at this time control. Note: iter 16 (Week 4 ad-hoc) tested EARLY_EXIT_MARGIN=0.6 and got 41% -- so the parameter has *some* effect, but only downward when reduced too aggressively.

### Iteration 26 -- `combo_table20M_roughness20`

- **Changed:** `TABLE_SIZE` 10M -> 20M AND `EVAL_ROUGHNESS` 13 -> 20
- **Hypothesis:** Stacking two orthogonal changes (memory axis + search axis) might produce additive improvement.
- **Result:** 46.0% (W=17 L=21 D=12) | 0.194 s/move | 176.1s wall
- **Decision:** DISCARD (46.0% < 55.0%)
- **Rollback:** Config reverted. Combination performed worse than either individual change (TABLE_SIZE 20M=42%, EVAL_ROUGHNESS 20=50%). This mirrors the Week 3 finding that combining changes interferes rather than stacks.

---

## Resource Usage Notes

- **Total wall time:** 27.8 minutes for 500 games (10 x 50)
- **Parallelization:** 8 workers via `multiprocessing.Pool`, ~2.8 min per 50-game match
- **Memory:** Peak ~1.6 GB for the main process (TABLE_SIZE=20M runs); workers ~150-280 MB each
- **CPU:** ~100% utilization across 8 cores during matches
- **Speed:** All candidates averaged 0.186-0.219 s/move, well within the 0.5 s/move limit
- **No timeouts or OOM events**
