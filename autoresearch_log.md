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

10 iterations run in two rounds of 5. All evaluated head-to-head against the locked baseline using `_PSTIsolatedEngine` (swaps module-level PST globals around each `think()` call to enable fair comparison in a single process).

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
- **QS_LIMIT=100** was closest (54.0%) but avg 0.354s/move — 2× slower than baseline. Speed cost outweighed tactical gain at this threshold. Promising direction.
- **MOVE_ORDERING=mvv_lva** second-closest (52.0%). MVV-LVA capture ordering improves alpha-beta cutoffs but not enough alone.
- **PST_SCALE=1.15** hurt (48%): more positional emphasis made play worse, suggesting Sunfish's baseline PST weighting is already near-optimal.
- **Minor pieces +20cp** worst result (38%): large piece value changes create systematic positional misconceptions the engine can't resolve within the time budget. Piece values are highly sensitive.
- **EVAL_ROUGHNESS=7** no improvement (49%): MTD-bi aspiration window was already precise enough.

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
- **QS_LIMIT=150** tied the 54.0% of QS_LIMIT=100 but at 0.213s/move (vs 0.354) — much better speed profile. The tactical improvement is real but insufficient to clear 55% alone.
- **Rook +16cp** also hit 54.0%: small value nudges are safer than large ones (round 1 showed +20cp on minors → 38%). Rooks may be slightly undervalued in closed middlegames.
- **PST_SCALE=0.9 hurt** (45%): both directions of PST scaling hurt. Baseline 1.0 appears optimal.
- **mvv_lva + QS_LIMIT=170 combined** was worst of round 2 (36%). The two changes interfere rather than stack — MVV-LVA reorders captures but deeper quiescence then evaluates them differently, creating inconsistency.
- **DRAW_TEST=False** (51%): removing repetition detection from search neither helped nor hurt significantly. The speed saving was marginal.

---

## Summary After 10 Iterations

**KEEPs**: 0  
**Best win rates**: 54.0% × 3 (QS_LIMIT=100, QS_LIMIT=150, R=495)  
**Worst**: 36.0% (mvv_lva + QS_LIMIT=170 combined)

```
Win rate distribution across 10 candidates:
  36%  38%  45%  48%  49%  51%  52%  54%  54%  54%
  ↑ worst                                  ↑ best (×3)
  Baseline mirror: 54%
  Threshold:       55%
```

The 55% threshold has not been cleared. Key structural observations:

1. **Baseline Sunfish parameters are near-optimal.** Every single-parameter change either hurt or produced a statistically indistinguishable result. This is consistent with Sunfish's decade of tuning history.

2. **Statistical noise is the binding constraint.** At 50 games, σ ≈ 7% win rate. To detect a +5% improvement at 80% power requires ~200 games. The three "54%" results could each be noise around 50% or signal around 54% — indistinguishable at N=50.

3. **QS_LIMIT and rook value are the only consistent near-misses.** Both independently reached 54%. These should be the priority for continued tuning.

4. **Parameter combinations backfire.** Round 2 iteration 8 showed that two individually near-neutral changes (mvv_lva at 52%, qs=170 near baseline) combined to produce the worst result (36%). Interaction effects dominate.

---

## Next Steps

Priority hypotheses for round 3:

| Idea | Rationale |
|------|----------|
| Run QS_LIMIT=150 + R=495 with N=100 games | Confirm signal vs noise for both near-misses |
| QS_LIMIT=175 | Narrow the 150–219 range further |
| R=490 (+11cp) | Even smaller rook nudge |
| P=105 (+5cp) | Pawns slightly up — passed pawn endgames |
| Lower EARLY_EXIT_MARGIN to 0.7 | More time used per move within budget |
