"""
make_week4_artifacts.py — generate the Week 4 deliverable artifacts.

Inputs:
  - week4_results_matrix.csv  (controlled experiments, 20 rows)
  - results.csv               (all 35 runs: 15 prior + 20 week 4)

Outputs:
  - week4_metric_over_time.png  (multi-panel plot)
  - week4_error_taxonomy.md     (4-category breakdown)
  - week4_failure_memo.md       (one-page analysis)
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

REPO_ROOT = Path(__file__).parent
MATRIX_CSV = REPO_ROOT / "week4_results_matrix.csv"
RESULTS_CSV = REPO_ROOT / "results.csv"


def _read_matrix():
    rows = []
    with open(MATRIX_CSV) as f:
        for row in csv.DictReader(f):
            row["win_pct"] = float(row["win_pct"])
            row["level_value"] = float(row["level_value"]) if row["level_value"] not in ("True", "False") else (1.0 if row["level_value"] == "True" else 0.0)
            row["seed"] = int(row["seed"])
            rows.append(row)
    return rows


def _aggregate(rows, experiment, axis_key):
    """Group by level_value, return list of (level, [win_pcts], mean, std)."""
    groups = {}
    for r in rows:
        if r["experiment"] != experiment:
            continue
        groups.setdefault((r["level_name"], r["level_value"]), []).append(r["win_pct"])
    out = []
    for (lname, lval), wps in sorted(groups.items(), key=lambda x: x[0][1]):
        mean = statistics.mean(wps)
        std = statistics.stdev(wps) if len(wps) > 1 else 0.0
        out.append((lname, lval, wps, mean, std))
    return out


# ---------------------------------------------------------------------------
# Plot generation
# ---------------------------------------------------------------------------
def make_plot(rows):
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Week 4 Controlled Experiments — Win % vs Baseline",
                 fontsize=14, fontweight="bold")

    # ----- Panel A: QS_LIMIT sweep -----
    ax = axes[0, 0]
    agg_a = _aggregate(rows, "A", "qs_limit")
    xs = [g[1] for g in agg_a]
    means = [g[3] for g in agg_a]
    stds = [g[4] for g in agg_a]
    for g in agg_a:
        for wp in g[2]:
            ax.plot(g[1], wp, 'o', color='gray', alpha=0.5, markersize=8)
    ax.errorbar(xs, means, yerr=stds, fmt='-D', color='steelblue',
                linewidth=2, capsize=5, label="mean ± stdev (2 seeds)")
    ax.axhline(50, color='black', linestyle=':', alpha=0.5, label="null (50%)")
    ax.axhline(55, color='red', linestyle='--', alpha=0.7, label="acceptance threshold (55%)")
    ax.axvline(219, color='green', linestyle=':', alpha=0.5, label="baseline (219)")
    ax.set_xlabel("QS_LIMIT")
    ax.set_ylabel("Win % vs baseline")
    ax.set_title("Experiment A: QS_LIMIT sweep")
    ax.set_ylim(30, 70)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", fontsize=8)

    # ----- Panel B: PST_SCALE sweep -----
    ax = axes[0, 1]
    agg_b = _aggregate(rows, "B", "pst_scale")
    xs = [g[1] for g in agg_b]
    means = [g[3] for g in agg_b]
    stds = [g[4] for g in agg_b]
    for g in agg_b:
        for wp in g[2]:
            ax.plot(g[1], wp, 'o', color='gray', alpha=0.5, markersize=8)
    ax.errorbar(xs, means, yerr=stds, fmt='-D', color='darkorange',
                linewidth=2, capsize=5, label="mean ± stdev (2 seeds)")
    ax.axhline(50, color='black', linestyle=':', alpha=0.5)
    ax.axhline(55, color='red', linestyle='--', alpha=0.7, label="55% threshold")
    ax.axvline(1.0, color='green', linestyle=':', alpha=0.5, label="baseline (1.0)")
    ax.set_xlabel("PST_SCALE")
    ax.set_ylabel("Win % vs baseline")
    ax.set_title("Experiment B: PST_SCALE sweep")
    ax.set_ylim(30, 70)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", fontsize=8)

    # ----- Panel C: null-move ablation -----
    ax = axes[1, 0]
    agg_c = _aggregate(rows, "C", "enable_null_move")
    labels = [g[0] for g in agg_c]
    means = [g[3] for g in agg_c]
    stds = [g[4] for g in agg_c]
    individuals = [g[2] for g in agg_c]
    x_pos = np.arange(len(labels))
    bars = ax.bar(x_pos, means, yerr=stds, capsize=8,
                  color=['lightcoral', 'mediumseagreen'],
                  edgecolor='black', linewidth=1.2)
    for i, wps in enumerate(individuals):
        for wp in wps:
            ax.plot(i, wp, 'o', color='black', alpha=0.7, markersize=10, zorder=3)
    ax.axhline(50, color='black', linestyle=':', alpha=0.5, label="null (50%)")
    ax.axhline(55, color='red', linestyle='--', alpha=0.7, label="55% threshold")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Win % vs baseline")
    ax.set_title("Experiment C: null-move pruning ablation (engine.py edit)")
    ax.set_ylim(30, 70)
    ax.grid(alpha=0.3, axis='y')
    ax.legend(loc="upper right", fontsize=8)

    # ----- Panel D: Metric-over-time (all 35 runs) -----
    ax = axes[1, 1]
    win_pcts = []
    notes = []
    with open(RESULTS_CSV) as f:
        for row in csv.DictReader(f):
            if "iteration=" in row.get("notes", "") or "week4" in row.get("notes", ""):
                win_pcts.append(float(row["a_win_rate_pct"]))
                notes.append(row["notes"])
    iters = list(range(1, len(win_pcts) + 1))
    colors = ['steelblue' if 'iteration=' in n else 'darkorange' for n in notes]
    ax.scatter(iters, win_pcts, c=colors, s=60, alpha=0.8, edgecolor='black', linewidth=0.5)
    ax.axhline(50, color='black', linestyle=':', alpha=0.5)
    ax.axhline(55, color='red', linestyle='--', alpha=0.7, label="55% threshold")
    ax.fill_between(iters, [43]*len(iters), [57]*len(iters), color='gray',
                    alpha=0.15, label="±1σ noise band (≈7%)")
    ax.set_xlabel("Run index (chronological)")
    ax.set_ylabel("Win % vs baseline")
    ax.set_title("All 35 evaluation runs over time")
    ax.set_ylim(30, 70)
    ax.grid(alpha=0.3)
    blue_p = mpatches.Patch(color='steelblue', label='Rounds 1-3 (iter 1-15)')
    orange_p = mpatches.Patch(color='darkorange', label='Week 4 controlled (20)')
    ax.legend(handles=[blue_p, orange_p,
                       mpatches.Patch(color='red', label='55% threshold'),
                       mpatches.Patch(color='gray', alpha=0.3, label='±1σ band')],
              loc="upper right", fontsize=8)

    plt.tight_layout()
    out = REPO_ROOT / "week4_metric_over_time.png"
    plt.savefig(out, dpi=130, bbox_inches='tight')
    print(f"Wrote {out}")


# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------
def make_taxonomy():
    text = """# Error Taxonomy — All 35 Evaluation Runs

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
"""
    out = REPO_ROOT / "week4_error_taxonomy.md"
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out}")


# ---------------------------------------------------------------------------
# Failure-analysis memo
# ---------------------------------------------------------------------------
def make_memo():
    text = """# Failure Analysis Memo — Dominant Mode: Signal Failure

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
"""
    out = REPO_ROOT / "week4_failure_memo.md"
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    rows = _read_matrix()
    print(f"Loaded {len(rows)} matrix rows")
    make_plot(rows)
    make_taxonomy()
    make_memo()
    print("\nWeek 4 artifacts complete.")
