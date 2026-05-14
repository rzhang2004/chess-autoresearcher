# Week 5 Keep / Discard / Crash Summary

**Block:** Iterations 17--26 (10 runs, 500 games total)
**Date:** 2026-05-13

---

## Outcome Counts

| Category | Count | Percentage |
|----------|------:|----------:|
| **KEEP** | 0 | 0% |
| **DISCARD** | 10 | 100% |
| **CRASH** | 0 | 0% |

---

## Every Run, With Decision and Reason

| Iter | Experiment | Win% | W-L-D | Decision | Reason for Rollback |
|-----:|-----------|-----:|------:|----------|-------------------|
| 17 | table_size_20M | 42.0 | 14-22-14 | DISCARD | 42.0% < 55% threshold |
| 18 | table_size_5M | 50.0 | 19-19-12 | DISCARD | 50.0% < 55% threshold |
| 19 | eval_roughness_20 | 50.0 | 19-19-12 | DISCARD | 50.0% < 55% threshold |
| 20 | eval_roughness_5 | **54.0** | 22-18-10 | DISCARD | 54.0% < 55% threshold (missed by 1pp) |
| 21 | pawn_pst_center | 44.0 | 15-21-14 | DISCARD | 44.0% < 55% threshold |
| 22 | knight_pst_central | 47.0 | 15-18-17 | DISCARD | 47.0% < 55% threshold |
| 23 | bishop_value_330 | 51.0 | 19-18-13 | DISCARD | 51.0% < 55% threshold |
| 24 | queen_value_940 | 44.0 | 16-22-12 | DISCARD | 44.0% < 55% threshold |
| 25 | early_exit_0.95 | 51.0 | 17-16-17 | DISCARD | 51.0% < 55% threshold |
| 26 | combo_table20M_roughness20 | 46.0 | 17-21-12 | DISCARD | 46.0% < 55% threshold |

---

## Distribution

```
42  44  44  46  47  50  50  51  51  54
         median = 48.5%
         mean   = 47.9%
         std    = 3.7pp
         best   = 54% (eval_roughness_5)
         worst  = 42% (table_size_20M)
```

All 10 results fall within the noise band established in Week 4 (baseline-vs-baseline pooled: mean=55%, std=4%). None cleared the 55% threshold.

---

## Rollback Logic

Every DISCARD immediately reverted to the locked baseline `config.py`. The baseline was **never modified** during this block -- all 10 iterations evaluated against the same unchanged Sunfish defaults. No cascading changes; no state leaked between iterations.

The only way config.py would have changed is if a KEEP occurred (win_pct >= 55% AND avg_sec <= 0.5), which would have updated the baseline for subsequent iterations. Since 0 KEEPs occurred, every iteration used identical baseline and candidate-vs-baseline comparison conditions.
