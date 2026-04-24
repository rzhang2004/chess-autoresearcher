"""
run_5_iterations.py - Autoresearch iterations, round 2.

Round 1 learnings:
  - PST_SCALE=1.15 hurt (48%) - baseline PST weighting is already good
  - QS_LIMIT=100 was closest but too slow (54%, 0.354s/move) - try 150
  - N/B +20cp hurt badly (38%) - piece values are sensitive, use tiny deltas
  - EVAL_ROUGHNESS=7 no help (49%) - current window fine
  - MOVE_ORDERING=mvv_lva promising (52%) - try combining with other tweaks

Round 2 experiments:
  1. QS_LIMIT=150  - halfway between 219 and 100; some tactical depth, less slowdown
  2. PST_SCALE=0.9 - less positional (opposite of round 1; 1.15 hurt so try other way)
  3. mvv_lva + QS_LIMIT=170 - combine two near-misses at moderate settings
  4. R=495 (+16cp)  - small rook boost; rooks undervalued in closed positions
  5. DRAW_TEST=False - skip repetition detection in search; faster, may find more wins
"""

from __future__ import annotations

import io
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
EVAL_SEED_BASE = 2033  # continues from round 1 (which ended at 2032)


def _run_evaluation(candidate_content, baseline_content, seed, verbose=True):
    candidate_eng = _build_isolated(_exec_config(candidate_content))
    baseline_eng = _build_isolated(_exec_config(baseline_content))
    label = f"candidate_{time.strftime('%Y%m%d-%H%M%S')}"
    summary = _eval_mod.run_match(
        lambda: candidate_eng,
        lambda: baseline_eng,
        label_a=label,
        label_b="sunfish_baseline",
        n_games=BATCH_SIZE,
        seed=seed,
        log_path=LOGS_DIR,
        verbose=verbose,
    )
    return summary, label


def make_candidate(base, replacements):
    c = base
    for old, new in replacements:
        c = c.replace(old, new)
    return c


def main():
    best_config_content = CONFIG_PY.read_text(encoding="utf-8")

    experiments = [
        {
            "name": "qs_limit_150",
            "description": (
                "QS_LIMIT 219 -> 150: moderate quiescence depth increase.\n"
                "  Round 1: QS_LIMIT=100 got 54% but avg 0.354s/move (too slow).\n"
                "  Hypothesis: 150 captures enough tactical depth without the speed hit."
            ),
            "replacements": [("QS_LIMIT = 219", "QS_LIMIT = 150")],
        },
        {
            "name": "pst_scale_0.9",
            "description": (
                "PST_SCALE 1.0 -> 0.9: reduce positional bonus weight 10%.\n"
                "  Round 1: PST_SCALE=1.15 hurt (48%). Trying the opposite direction.\n"
                "  Hypothesis: slightly less PST emphasis may improve material-first play."
            ),
            "replacements": [("PST_SCALE = 1.0", "PST_SCALE = 0.9")],
        },
        {
            "name": "mvv_lva_qs170",
            "description": (
                "MOVE_ORDERING='mvv_lva' + QS_LIMIT=170: combine two near-misses.\n"
                "  Round 1: mvv_lva alone: 52%. qs_limit=100: 54% (but slow).\n"
                "  Hypothesis: better capture ordering + modest quiescence depth stack."
            ),
            "replacements": [
                ('MOVE_ORDERING = "default"', 'MOVE_ORDERING = "mvv_lva"'),
                ("QS_LIMIT = 219", "QS_LIMIT = 170"),
            ],
        },
        {
            "name": "rook_value_495",
            "description": (
                "R 479 -> 495 (+16cp): small rook value increase.\n"
                "  Round 1 showed major piece value changes hurt badly (-20cp on N/B).\n"
                "  Hypothesis: rooks gain power as game opens; small boost aids endgame."
            ),
            "replacements": [('"R": 479,', '"R": 495,')],
        },
        {
            "name": "draw_test_false",
            "description": (
                "DRAW_TEST False: skip repetition detection during search.\n"
                "  Removes one check per node, speeding up search.\n"
                "  Hypothesis: faster search reaches greater depth; engine finds more wins\n"
                "  instead of voluntarily repeating positions."
            ),
            "replacements": [("DRAW_TEST = True", "DRAW_TEST = False")],
        },
    ]

    print("=" * 60)
    print("AutoResearch round 2: 5 refined iterations")
    print(f"Batch: {BATCH_SIZE} games | Win threshold: {WIN_THRESHOLD_PCT}%")
    print("=" * 60)

    for i, exp in enumerate(experiments, start=6):  # continue numbering from round 1
        print(f"\n{'='*60}")
        print(f"ITERATION {i}/10  [{exp['name']}]")
        print(f"{'='*60}")
        print(f"{exp['description']}\n")

        candidate_content = make_candidate(best_config_content, exp["replacements"])

        if candidate_content == best_config_content:
            print("  WARNING: no change produced - skipping.")
            continue

        try:
            _exec_config(candidate_content)
        except Exception as exc:
            print(f"  Config error: {exc} - skipping.")
            continue

        seed = EVAL_SEED_BASE + (i - 6)
        print(f"  Running {BATCH_SIZE}-game match (seed={seed})...")
        t0 = time.time()
        try:
            summary, label = _run_evaluation(
                candidate_content, best_config_content, seed, verbose=True
            )
        except Exception as exc:
            print(f"  Evaluation crashed: {exc}")
            continue

        win_pct = summary.a_win_rate_pct
        avg_sec = summary.a_avg_sec_per_move
        wall_min = (time.time() - t0) / 60
        speed_ok = avg_sec <= MAX_AVG_SEC_PER_MOVE
        wins_enough = win_pct >= WIN_THRESHOLD_PCT
        status = "KEEP" if (wins_enough and speed_ok) else "DISCARD"

        print(f"\n  Result:")
        print(f"    Win rate : {win_pct:.1f}%  (need >={WIN_THRESHOLD_PCT}%)")
        print(f"    Avg time : {avg_sec:.3f}s/move  (limit {MAX_AVG_SEC_PER_MOVE}s)")
        print(f"    W={summary.a_wins} L={summary.b_wins} D={summary.draws}  "
              f"wall={wall_min:.1f}min")
        print(f"    Decision : {status}")

        if wins_enough and speed_ok:
            best_config_content = candidate_content
            CONFIG_PY.write_text(candidate_content, encoding="utf-8")
            _update_best_config(win_pct, avg_sec, label)
            print(f"    -> Saved to config.py and best_config.yaml.")

        _eval_mod.append_result_row(
            RESULTS_CSV,
            summary,
            notes=f"iteration={i} exp={exp['name']} status={status}",
        )

    print(f"\n{'='*60}")
    print("Round 2 complete. See results.csv for full log.")


if __name__ == "__main__":
    main()
