# "What Actually Worked" Memo

**Project:** Chess AutoResearcher (STAT 390 Capstone)
**Author:** Ray Zhang
**Date:** 2026-05-13
**Scope:** Week 5 autonomous block (iterations 17--26) in context of all 46 runs

---

## The Honest Answer: Nothing Produced a Real, Interpretable Gain

Across 10 Week 5 iterations exploring 5 previously-untouched parameter axes (TABLE_SIZE, EVAL_ROUGHNESS, PST_OVERRIDES, bishop/queen values, and one combination), no modification cleared the 55% acceptance threshold. The best result was 54.0% (EVAL_ROUGHNESS=5), which is indistinguishable from the null condition.

This is consistent with all prior work: 26 iterations + 20 controlled experiment runs = 46 total evaluations, and **0 KEEPs**. The baseline Sunfish configuration has never been beaten.

---

## What We Learned (The Research Finding)

The absence of improvement IS the finding. Specifically:

### 1. Sunfish's default parameters are near-optimal for this time control

Every parameter axis has now been probed:

| Axis | Iterations | Best | Verdict |
|---|---|---|---|
| QS_LIMIT | 1,2,6,8,11,15 + Exp A (10 runs) | 54% | Noise |
| PST_SCALE | 1,7 + Exp B (6 runs) | 57%* | Noise (*null condition) |
| PIECE_VALUES | 3,9,13,14,23,24 | 54% | Noise |
| MOVE_ORDERING | 5,12 | 52% | Noise |
| EVAL_ROUGHNESS | 4,19,20 | 54% | Noise |
| TABLE_SIZE | 17,18 | 50% | Noise |
| EARLY_EXIT_MARGIN | 16,25 | 51% | Noise |
| DRAW_TEST | 10 | 51% | Noise |
| PST_OVERRIDES | 21,22 | 47% | Hurt |
| enable_null_move | Exp C (4 runs) | 55.5%* | Noise (*null condition) |
| Combinations | 8,15,26 | 52% | Hurt or noise |

Sunfish has been tuned by its maintainers over a decade. At 0.1s/move with 50-game batches, the parameter space is flat near the optimum -- no single-axis perturbation produces a measurable improvement.

### 2. The evaluation metric's noise floor dominates

At N=50 games, the standard deviation of win rate is ~7 percentage points (binomial: sqrt(0.5 * 0.5 / 50) = 7.1%). The 55% acceptance threshold is only 0.7 standard deviations above the 50% null, meaning:
- A true 50% candidate has a **24% chance** of crossing 55% by luck
- A true 55% candidate only has a **50% chance** of being detected

The Week 4 null-condition analysis (6 baseline-vs-baseline runs averaging 55.0%) proved that even the threshold itself is at the noise floor.

### 3. Which modifications consistently failed

Two categories reliably produced below-50% results:

- **PST modifications** (PST_SCALE, PST_OVERRIDES): 7 runs, mean 46.3%. Sunfish's piece-square tables are tightly calibrated; any deviation degrades positional judgment.
- **Large piece-value changes** (>= +20cp): iter 3 (N+20/B+20) hit 38%. The evaluation function's piece-value ratios are critical to material trade decisions.

### 4. What came closest (but was still noise)

EVAL_ROUGHNESS=5 (54%) was the Week 5 "best." If this were a real signal, the causal story would be: a narrower aspiration window makes MTD-bi converge to more precise evaluations at the cost of more re-searches, and the precision improvement outweighs the depth loss. But without replication at additional seeds, this cannot be distinguished from sampling noise.

---

## What Would Need to Change to Make Progress

The bottleneck is not the parameter space -- it's the evaluation resolution:

1. **Increase N to 200+** -- reduces sigma from 7% to 3.5%, making the 55% threshold ~1.4 sigma above null (detectable at 80% power for a true +5pp effect).
2. **Replicate every candidate at 3+ seeds** -- Week 3's validation runs proved single-seed results are uninterpretable.
3. **Target algorithmic changes, not config tuning** -- the Week 4 null-move ablation showed the largest effect (-8pp). Engine-level changes (e.g., late-move reductions, killer heuristic, aspiration windows in the search itself) are more likely to produce detectable effects than config knob adjustments.

---

## Summary

| Question | Answer |
|---|---|
| What did the agent discover? | Sunfish's defaults are near-optimal; no config change beats baseline |
| Was any improvement real? | No -- all results within the null-condition noise band |
| What consistently failed? | PST overrides and piece-value perturbations |
| What is the research finding? | The metric at N=50 cannot resolve config-level effects; the optimization target should be the evaluation protocol or the search algorithm, not the parameters |
