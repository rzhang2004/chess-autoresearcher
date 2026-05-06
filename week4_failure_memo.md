# Failure Analysis Memo — Dominant Mode: Signal Failure

**Project:** Chess AutoResearcher (STAT 390 Capstone)
**Author:** Ray Zhang
**Date:** Week 4
**Status:** Yellow → Red (the metric cannot reliably distinguish improvement from noise)

## What changed this week

Three controlled experiments, each varying ONE axis with all other config
held fixed and 2 seed replicates per level:

- **A.** `QS_LIMIT` sweep at {50, 100, 150, 219, 300} — 10 runs
- **B.** `PST_SCALE` sweep at {0.7, 1.0, 1.3} — 6 runs
- **C.** `enable_null_move` ablation at {True, False} — 4 runs (engine.py edit)

Plus an `evaluator.run_match_parallel()` patch to multiprocess game-playing
across 8 cores (6.7× speedup; 18 min → 2.7 min per 50-game match).

## What happened as a result

Across 20 controlled runs at the locked protocol (50 games, 0.1 s/move, seed
schedule), no level reliably crossed the 55% acceptance threshold. More
importantly, **the baseline-vs-baseline null condition (`qs_219`, `pst_1.0`,
`null_move_on`) returned win rates of 50, 52, 54, 56, 57, 61** across its
six trials — the threshold sits inside the null-condition's variance band.

The strongest "signal" candidate from rounds 1-2 (`mvv_lva_ordering` at 52%)
was re-tested in round 3 at a different seed and landed at 38%, confirming
that the original 52% reading was noise.

## Why it likely happened

Two compounding noise sources:

1. **Sample variance.** With N=50 games and equal-strength engines,
   σ(p̂) = √(0.25/50) = 7.07%. The threshold "≥ 55%" is only 0.71 σ above
   the null. The probability of a truly-equal candidate exceeding 55% by
   chance alone is ≈ 24%.

2. **Wall-clock-bounded search non-determinism.** Iterative deepening is
   capped by `time_budget`, so search depth depends on system load. Running
   the same (config, seed) pair twice on the same machine produced different
   game outcomes (verified during multiprocessing validation: 4-4-2 vs
   2-4-4 for n=10, seed=9999). This is a property of the locked protocol,
   not a bug — but it adds non-deterministic variance on top of sample
   variance.

These together mean the autoresearch loop has been operating below its
**measurement floor** for three rounds. Every rejected/accepted decision
in iterations 1-15 was statistically indistinguishable from a coin flip.

## What to do about it

**Required fix this week:** raise effective batch size before re-running
any acceptance test. Two options, ranked by interpretability:

1. **Single big batch (recommended): N=200 games per evaluation.**
   σ → 3.5%; the 55% threshold becomes 1.4 σ above null (false-positive
   rate ≈ 8%). With 8-way parallelism this is ~10 min per evaluation —
   still tractable for a search loop.

2. **Replicated medium batches: 4 × N=50 at different seeds.**
   Aggregate by mean; same effective σ but exposes seed-to-seed instability
   directly in the data. Useful for diagnosing leakage events (a single
   seed driving an outlier is visible).

**Adopt going forward:** every accepted KEEP must be re-validated at a
fresh seed before being written to `best_config.yaml`. This catches the
mvv_lva-style false positive automatically.

**Out-of-scope but flagged:** the protocol's wall-clock-bounded ID is the
deeper problem. Switching to a fixed-depth search (e.g., depth=4 for all
moves) would remove timing noise entirely at the cost of comparability with
the locked v1-2026-04 protocol. This is a Week 5+ decision for the human
researcher.

## Status designation

🟡 **Yellow.** The Week 4 deliverables ARE controlled and interpretable —
the data conclusively diagnoses the metric's noise floor — but the loop's
existing acceptance criterion is unreliable until N is increased. One
required fix before next iteration: raise N to 200 or implement seed
replication, then re-run the rounds 1-3 "near-misses" (`qs_limit_100`,
`mvv_lva_ordering`, `rook_value_495`, `pawn_value_105`) to see whether
any cross the lower-noise threshold.
