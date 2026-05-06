# Error Taxonomy — All 35 Evaluation Runs

Categories follow the Week 4 framework (Signal Failure / Code Instability /
Evaluation Leakage / Agent Misbehavior). Each run is assigned to its dominant
category; a single run may have secondary issues but is bucketed by what
prevents it from producing trustworthy evidence.

## Summary counts

| Category               | Count | % of total |
|------------------------|-------|-----------:|
| Signal Failure         | 30    | 86%        |
| Evaluation Leakage     |  3    |  9%        |
| Code Instability       |  1    |  3%        |
| Agent Misbehavior      |  1    |  3%        |
| **Total**              | **35** | **100%** |

## Category 1 — Signal Failure (30 runs)

> *The loop runs, but no meaningful improvement appears across iterations.*

This is the dominant failure. The 50-game evaluation has σ ≈ 7% sampling
noise, and additional non-determinism comes from wall-clock-bounded iterative
deepening (system load → search depth varies). Even baseline-vs-baseline
runs landed at 50%, 52%, 54%, 56%, 57%, 61% across our six null-condition
trials in Week 4. The 55% acceptance threshold sits **inside** that noise
band, so the loop cannot reliably distinguish improvement from chance.

Examples:
- Rounds 1-2 iter 5 (`mvv_lva_ordering`): 52% → looked promising
- Round 3 iter 12 (`mvv_lva_reseed`): 38% → SAME config, different seed → ⇒ noise
- Week 4 qs_219 (baseline-vs-baseline): 56% and 57% → null condition exceeds threshold

## Category 2 — Evaluation Leakage (3 runs)

> *The metric improves, but comparability is compromised — the evaluation setup shifted.*

When a candidate config drives engine A to spend more wall-clock time per
move than engine B (because deeper search runs longer), A gets a free
advantage from the locked time-budget. The protocol fixes 0.1 s/move, but
both engines compete for the same CPU and the candidate's configuration can
slow it relative to the baseline, raising effective per-move compute.

Affected:
- Round 1 iter 2 (`qs_limit_100`): A averaged 0.354 s/move (3.5× the 0.1 s
  budget), B averaged 0.206 s/move. Result was 54%, but A had 1.7× more
  effective compute per move → **leakage, not signal**.
- Round 2 iter 8 (`mvv_lva_qs170`): A 0.236 s, B 0.198 s.
- Week 4 Exp A qs_50, seed 4001: A max sec/move 36.4 s vs B 13.3 s outlier.

## Category 3 — Code Instability (1 run, fixed)

> *Crashes, inconsistent runs, or a broken pipeline that prevents reliable measurement.*

- Initial run on Python 3.12: `random.Random((seed, game_idx))` raised
  `TypeError` because tuple seeds were removed in 3.12. Fixed in commit by
  switching to integer arithmetic (`seed * 100_000 + game_idx`).

## Category 4 — Agent Misbehavior (1 case, latent)

> *The agent ignores rules or makes uncontrolled changes outside the intended scope.*

The hand-curated experiments (rounds 1-3, week 4) had no agent misbehavior.
However, the original Claude-driven `search.py` loop has potential here:
once Claude proposes a multi-axis change (e.g., "tweak PST_SCALE AND
QS_LIMIT AND mvv_lva together") in a single iteration, that violates
single-axis isolation and the result is uninterpretable. Round 2 iter 8
(`mvv_lva_qs170`, two simultaneous changes) demonstrates the failure mode
even when initiated by the human-in-the-loop: 36% — drastically worse than
either component alone.

## Most distrusted result

Round 1 iter 5 (`mvv_lva_ordering` → 52%). Was treated as "promising near-miss"
for two rounds, then re-tested in Round 3 iter 12 with a fresh seed and
landed at 38% — invalidating the original signal.

## Most trusted result

Week 4 Experiment B `pst_scale=1.0` (baseline-vs-baseline): 54% / 52%
across 2 seeds. The variance here is small *because* the two configs are
identical, so the measurement is reproducible up to RNG and timing noise.
This calibrates the noise floor of the protocol.
