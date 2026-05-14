"""
run_week5_block.py -- Week 5 autonomous block: 10 iterations.

Each iteration varies ONE axis. All evaluated head-to-head against locked
baseline via run_match_parallel (8 workers). Seeds continue from prior work
(last used: 4100 in iteration 16).

Design rationale for these 10 experiments:
  Weeks 3-4 exhausted: PST_SCALE, QS_LIMIT, MOVE_ORDERING, large piece deltas,
  null-move ablation, EARLY_EXIT_MARGIN, DRAW_TEST. All landed in noise band.

  Week 5 explores the REMAINING untouched axes:
    - TABLE_SIZE (transposition table capacity)
    - EVAL_ROUGHNESS (MTD-bi aspiration window)
    - PST_OVERRIDES (per-piece positional tables)
    - Small piece-value nudges on B, Q
    - Combinations of individually-promising results
"""

from __future__ import annotations

import csv
import io
import os
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

import evaluator as _eval_mod
from search import (
    _exec_config, _build_isolated,
    _update_best_config, WIN_THRESHOLD_PCT, MAX_AVG_SEC_PER_MOVE,
    BATCH_SIZE, LOGS_DIR,
)

RESULTS_CSV = str(REPO_ROOT / "results.csv")
CONFIG_PY = REPO_ROOT / "config.py"
WEEK5_CSV = str(REPO_ROOT / "week5_results.csv")
EVAL_SEED_BASE = 5001  # fresh seed range for Week 5
N_WORKERS = 8

WEEK5_COLS = [
    "iteration", "experiment", "hypothesis", "changed_param", "old_value",
    "new_value", "seed", "n_games", "win_pct", "wins", "losses", "draws",
    "avg_sec_per_move", "avg_plies", "wall_seconds", "decision", "rollback_reason",
]


def _ensure_week5_header():
    if not Path(WEEK5_CSV).exists():
        with open(WEEK5_CSV, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(WEEK5_COLS)


def _append_week5_row(iteration, exp, summary, decision, rollback_reason=""):
    with open(WEEK5_CSV, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            iteration, exp["name"], exp["hypothesis"], exp["changed_param"],
            exp["old_value"], exp["new_value"], summary.seed, summary.n_games,
            summary.a_win_rate_pct, summary.a_wins, summary.b_wins, summary.draws,
            round(summary.a_avg_sec_per_move, 4), round(summary.avg_plies, 1),
            round(summary.wall_seconds, 1), decision, rollback_reason,
        ])


def make_candidate(base, replacements):
    c = base
    for old, new in replacements:
        if old not in c:
            raise ValueError(f"Replacement target not found in config: {old!r}")
        c = c.replace(old, new)
    return c


def main():
    _ensure_week5_header()
    best_config_content = CONFIG_PY.read_text(encoding="utf-8")
    baseline_cfg = _exec_config(best_config_content)

    experiments = [
        # --- 1. TABLE_SIZE 10M -> 20M ---
        {
            "name": "table_size_20M",
            "hypothesis": "Larger transposition table caches more positions, improving move quality at same time budget",
            "changed_param": "TABLE_SIZE",
            "old_value": "10_000_000",
            "new_value": "20_000_000",
            "replacements": [("TABLE_SIZE = 10_000_000", "TABLE_SIZE = 20_000_000")],
        },
        # --- 2. TABLE_SIZE 10M -> 5M ---
        {
            "name": "table_size_5M",
            "hypothesis": "Smaller TT tests whether baseline is already optimal; if 5M hurts, TT size matters for strength",
            "changed_param": "TABLE_SIZE",
            "old_value": "10_000_000",
            "new_value": "5_000_000",
            "replacements": [("TABLE_SIZE = 10_000_000", "TABLE_SIZE = 5_000_000")],
        },
        # --- 3. EVAL_ROUGHNESS 13 -> 20 ---
        {
            "name": "eval_roughness_20",
            "hypothesis": "Wider MTD-bi window reduces re-searches; engine reaches same depth with fewer iterations",
            "changed_param": "EVAL_ROUGHNESS",
            "old_value": "13",
            "new_value": "20",
            "replacements": [("EVAL_ROUGHNESS = 13", "EVAL_ROUGHNESS = 20")],
        },
        # --- 4. EVAL_ROUGHNESS 13 -> 5 ---
        {
            "name": "eval_roughness_5",
            "hypothesis": "Narrower MTD-bi window gives more precise eval; tradeoff is more re-searches per depth",
            "changed_param": "EVAL_ROUGHNESS",
            "old_value": "13",
            "new_value": "5",
            "replacements": [("EVAL_ROUGHNESS = 13", "EVAL_ROUGHNESS = 5")],
        },
        # --- 5. Pawn PST override: boost center pawns ---
        {
            "name": "pawn_pst_center",
            "hypothesis": "Boosting d4/e4/d5/e5 pawn squares by +15cp encourages central pawn play",
            "changed_param": "PST_OVERRIDES[P]",
            "old_value": "None",
            "new_value": "center_boosted",
            "replacements": [
                (
                    '"P": None,',
                    '"P": (\n'
                    '          0,   0,   0,   0,   0,   0,   0,   0,\n'
                    '         78,  83,  86,  73, 102,  82,  85,  90,\n'
                    '          7,  29,  21,  59,  55,  31,  44,   7,\n'
                    '        -17,  16,  -2,  30,  29,   0,  15, -13,\n'
                    '        -26,   3,  10,  24,  21,   1,   0, -23,\n'
                    '        -22,   9,   5, -11, -10,  -2,   3, -19,\n'
                    '        -31,   8,  -7, -37, -36, -14,   3, -31,\n'
                    '          0,   0,   0,   0,   0,   0,   0,   0,\n'
                    '    ),'
                ),
            ],
        },
        # --- 6. Knight PST override: stronger centralization ---
        {
            "name": "knight_pst_central",
            "hypothesis": "Boosting knight center squares (d4/e4/d5/e5) by +10cp rewards knight centralization",
            "changed_param": "PST_OVERRIDES[N]",
            "old_value": "None",
            "new_value": "center_boosted",
            "replacements": [
                (
                    '"N": None,',
                    '"N": (\n'
                    '        -66, -53, -75, -75, -10, -55, -58, -70,\n'
                    '         -3,  -6, 100, -36,   4,  62,  -4, -14,\n'
                    '         10,  67,   1,  84,  83,  27,  62,  -2,\n'
                    '         24,  24,  45,  47,  43,  41,  25,  17,\n'
                    '         -1,   5,  31,  31,  32,  35,   2,   0,\n'
                    '        -18,  10,  13,  22,  18,  15,  11, -14,\n'
                    '        -23, -15,   2,   0,   2,   0, -23, -20,\n'
                    '        -74, -23, -26, -24, -19, -35, -22, -69,\n'
                    '    ),'
                ),
            ],
        },
        # --- 7. Bishop value B 320 -> 330 ---
        {
            "name": "bishop_value_330",
            "hypothesis": "Small bishop boost (+10cp) reflects bishop-pair advantage in open positions",
            "changed_param": "PIECE_VALUES[B]",
            "old_value": "320",
            "new_value": "330",
            "replacements": [('"B": 320,', '"B": 330,')],
        },
        # --- 8. Queen value Q 929 -> 940 ---
        {
            "name": "queen_value_940",
            "hypothesis": "Small queen boost (+11cp) discourages premature queen trades",
            "changed_param": "PIECE_VALUES[Q]",
            "old_value": "929",
            "new_value": "940",
            "replacements": [('"Q": 929,', '"Q": 940,')],
        },
        # --- 9. EARLY_EXIT_MARGIN 0.8 -> 0.95 ---
        {
            "name": "early_exit_0.95",
            "hypothesis": "Higher margin means engine tries next ID depth more often; more search = better moves",
            "changed_param": "EARLY_EXIT_MARGIN",
            "old_value": "0.8",
            "new_value": "0.95",
            "replacements": [("EARLY_EXIT_MARGIN = 0.8", "EARLY_EXIT_MARGIN = 0.95")],
        },
        # --- 10. Combo: best of above (or TABLE_SIZE 20M + EVAL_ROUGHNESS 20) ---
        {
            "name": "combo_table20M_roughness20",
            "hypothesis": "Stack two orthogonal changes: larger TT (memory axis) + wider aspiration (search axis)",
            "changed_param": "TABLE_SIZE + EVAL_ROUGHNESS",
            "old_value": "10M + 13",
            "new_value": "20M + 20",
            "replacements": [
                ("TABLE_SIZE = 10_000_000", "TABLE_SIZE = 20_000_000"),
                ("EVAL_ROUGHNESS = 13", "EVAL_ROUGHNESS = 20"),
            ],
        },
    ]

    overall_t0 = time.time()
    print("=" * 60)
    print("WEEK 5 AUTONOMOUS BLOCK -- 10 iterations")
    print(f"Parallel evaluation: {N_WORKERS} workers, {BATCH_SIZE} games/match")
    print(f"Win threshold: {WIN_THRESHOLD_PCT}% | Speed limit: {MAX_AVG_SEC_PER_MOVE}s/move")
    print(f"Seeds: {EVAL_SEED_BASE} to {EVAL_SEED_BASE + len(experiments) - 1}")
    print("=" * 60)

    keeps = 0
    discards = 0
    crashes = 0

    for i, exp in enumerate(experiments):
        iteration = 17 + i  # continue from iteration 16
        seed = EVAL_SEED_BASE + i
        print(f"\n{'='*60}")
        print(f"ITERATION {iteration}  [{exp['name']}]")
        print(f"  Param: {exp['changed_param']}  {exp['old_value']} -> {exp['new_value']}")
        print(f"  Hypothesis: {exp['hypothesis']}")
        print(f"{'='*60}")

        # Build candidate config
        try:
            candidate_content = make_candidate(best_config_content, exp["replacements"])
        except ValueError as exc:
            print(f"  CRASH: replacement failed: {exc}")
            crashes += 1
            # Still log the crash
            with open(WEEK5_CSV, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    iteration, exp["name"], exp["hypothesis"], exp["changed_param"],
                    exp["old_value"], exp["new_value"], seed, 0,
                    "", "", "", "", "", "", "", "CRASH", str(exc),
                ])
            continue

        # Validate config
        try:
            candidate_cfg = _exec_config(candidate_content)
        except Exception as exc:
            print(f"  CRASH: config validation failed: {exc}")
            crashes += 1
            with open(WEEK5_CSV, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    iteration, exp["name"], exp["hypothesis"], exp["changed_param"],
                    exp["old_value"], exp["new_value"], seed, 0,
                    "", "", "", "", "", "", "", "CRASH", str(exc),
                ])
            continue

        # Run match
        print(f"  Running {BATCH_SIZE}-game parallel match (seed={seed})...")
        t0 = time.time()
        try:
            summary = _eval_mod.run_match_parallel(
                candidate_cfg, baseline_cfg,
                label_a=f"week5_iter{iteration}_{exp['name']}",
                label_b="sunfish_baseline",
                n_games=BATCH_SIZE,
                n_workers=N_WORKERS,
                seed=seed,
                log_path=LOGS_DIR,
                verbose=False,
            )
        except Exception as exc:
            print(f"  CRASH: evaluation failed: {exc}")
            crashes += 1
            with open(WEEK5_CSV, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    iteration, exp["name"], exp["hypothesis"], exp["changed_param"],
                    exp["old_value"], exp["new_value"], seed, 0,
                    "", "", "", "", "", "", "", "CRASH", str(exc),
                ])
            continue

        wall = time.time() - t0
        win_pct = summary.a_win_rate_pct
        avg_sec = summary.a_avg_sec_per_move
        speed_ok = avg_sec <= MAX_AVG_SEC_PER_MOVE
        wins_enough = win_pct >= WIN_THRESHOLD_PCT

        if wins_enough and speed_ok:
            decision = "KEEP"
            rollback_reason = ""
            keeps += 1
            # Accept: update baseline for future iterations
            best_config_content = candidate_content
            CONFIG_PY.write_text(candidate_content, encoding="utf-8")
            baseline_cfg = candidate_cfg
            _update_best_config(win_pct, avg_sec,
                                f"week5_iter{iteration}_{exp['name']}")
        else:
            decision = "DISCARD"
            reasons = []
            if not wins_enough:
                reasons.append(f"win_pct={win_pct:.1f}% < {WIN_THRESHOLD_PCT}%")
            if not speed_ok:
                reasons.append(f"avg_sec={avg_sec:.3f}s > {MAX_AVG_SEC_PER_MOVE}s")
            rollback_reason = "; ".join(reasons)
            discards += 1

        print(f"\n  Result: {win_pct:.1f}% win rate | {avg_sec:.4f}s/move | "
              f"W={summary.a_wins} L={summary.b_wins} D={summary.draws}")
        print(f"  Wall time: {wall:.0f}s")
        print(f"  Decision: {decision}")
        if rollback_reason:
            print(f"  Rollback reason: {rollback_reason}")
        if decision == "KEEP":
            print(f"  >>> KEPT! config.py updated.")

        # Log to week5 CSV
        _append_week5_row(iteration, exp, summary, decision, rollback_reason)

        # Log to main results.csv
        _eval_mod.append_result_row(
            RESULTS_CSV, summary,
            notes=f"iteration={iteration} exp={exp['name']} status={decision}",
        )

    elapsed_min = (time.time() - overall_t0) / 60
    print(f"\n{'='*60}")
    print(f"WEEK 5 BLOCK COMPLETE")
    print(f"  Total wall time: {elapsed_min:.1f} min")
    print(f"  KEEPs: {keeps}  DISCARDs: {discards}  CRASHes: {crashes}")
    print(f"  Results: {WEEK5_CSV}")
    print("=" * 60)


if __name__ == "__main__":
    main()
