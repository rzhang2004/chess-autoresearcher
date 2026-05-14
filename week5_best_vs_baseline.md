# Week 5 Best Result vs. Baseline

**Block:** Iterations 17--26

---

## Best Candidate

| Field | Value |
|---|---|
| **Iteration** | 20 |
| **Experiment** | `eval_roughness_5` |
| **Change** | `EVAL_ROUGHNESS` 13 -> 5 (narrower MTD-bi aspiration window) |
| **Win rate** | 54.0% (22W 18L 10D) |
| **Avg s/move** | 0.200 s |
| **Seed** | 5004 |

## Baseline

| Field | Value |
|---|---|
| **Config** | Sunfish defaults (unchanged since Week 2) |
| **Mirror match** | 54.0% (Week 2, seed 2026) |
| **Null-condition mean** | 55.0% +/- 4.0% (6 baseline-vs-baseline runs, Week 4) |

---

## Direct Comparison

```
Best candidate (eval_roughness_5):   54.0%
Baseline mirror match (Week 2):      54.0%
Null-condition mean (Week 4):        55.0%  +/- 4.0%

Difference from null-condition mean:  -1.0 pp
Standard deviations from null:        -0.25 sigma
```

**The best Week 5 result does not beat the baseline.** 54.0% is 1 percentage point *below* the null-condition mean (55.0%) established by 6 baseline-vs-baseline runs in Week 4. It is statistically indistinguishable from the baseline playing against itself.

---

## Is This Improvement Real or Accidental?

**Accidental.** Three lines of evidence:

1. **Within the null band.** The 54% result sits inside the 95% CI of the null condition [47%, 63%]. A baseline-vs-baseline run at this seed could easily produce the same number.

2. **No replication.** The result was observed at a single seed (5004). Week 3 validation runs showed that apparent 54% results from prior iterations (QS_LIMIT=100, QS_LIMIT=150, R+16cp) all reverted to 47--52% when re-tested at fresh seeds.

3. **The block's mean is below 50%.** Across all 10 iterations, the mean win rate was 47.9% -- below the 50% expected if changes had zero effect. This suggests that *most perturbations to Sunfish's parameters slightly degrade play*, and the few that score near 54% are simply the upper tail of the noise distribution.

---

## Cumulative Status (All 26 Iterations + 20 Controlled)

After 46 total evaluation runs across Weeks 2--5:

- **KEEPs: 0**
- **Best single-run score: 61%** (Week 4, null-move-on baseline-vs-baseline, seed 4001 -- this is itself a null-condition data point)
- **Best candidate score: 54%** (tied across 5 different experiments at different seeds)
- **Config.py: unchanged from Sunfish defaults**

The current best config IS the baseline. No modification has produced a statistically significant improvement.
