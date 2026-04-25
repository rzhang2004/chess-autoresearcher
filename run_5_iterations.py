"""
run_5_iterations.py - Autoresearch round 3.

Lessons from rounds 1-2 (10 iterations, 0 KEEPs):
  * 54% appears repeatedly (qs_limit_100/150, rook_value_495) - same as baseline
    mirror match's A-side rate (17W-13L-20D = 54%); this is the noise floor.
  * 50 games gives sigma ~ 7%, so 55% threshold is ~0.7sigma above 50% null;
    distinguishing real signal from noise needs re-runs at different seeds.
  * Combinations of two search-side changes (mvv_lva + qs170) backfired hard
    (36%); pair changes that touch DIFFERENT mechanisms instead.
  * PST_SCALE is symmetric bad (1.15 -> 48%, 0.9 -> 45%); skip.
  * Large piece-value deltas hurt severely; use tiny deltas only.

Round 3 plan: mix validation and refined exploration.
  11. qs_limit_180         - round out QS curve (100, 150, 180)
  12. mvv_lva_reseed       - re-test iter 5 (52%) at fresh seed (validate)
  13. rook_value_490       - smaller rook bump (+11cp, not +16cp)
  14. pawn_value_105       - untouched parameter; +5cp on pawns
  15. combo_qs150_rook495  - stack two 54% candidates (different mechanisms)
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
EVAL_SEED_BASE = 2038  # round 2 ended at 2037


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
            "name": "qs_limit_180",
            "description": (
                "QS_LIMIT 219 -> 180: extend the QS sweet-spot search.\n"
                "  Prior: qs=100 -> 54% (slow 0.354s/move); qs=150 -> 54% (0.213s/move).\n"
                "  Hypothesis: 180 keeps most tactical benefit at lowest speed cost."
            ),
            "replacements": [("QS_LIMIT = 219", "QS_LIMIT = 180")],
        },
        {
            "name": "mvv_lva_reseed",
            "description": (
                "MOVE_ORDERING='mvv_lva' re-test at fresh seed (validation run).\n"
                "  Prior: iter 5 hit 52% at seed 2032. With sigma ~ 7%, that could be\n"
                "  noise above true 50%, or real ~52% signal. Re-run distinguishes.\n"
                "  Hypothesis: if signal, second run lands 50-55%; if noise, anywhere."
            ),
            "replacements": [('MOVE_ORDERING = "default"', 'MOVE_ORDERING = "mvv_lva"')],
        },
        {
            "name": "rook_value_490",
            "description": (
                "R 479 -> 490 (+11cp): smaller rook bump than iter 9 (+16cp -> 54%).\n"
                "  Hypothesis: minor pieces are very sensitive to value changes; even\n"
                "  rooks may benefit from smaller perturbations to find a real edge."
            ),
            "replacements": [('"R": 479,', '"R": 490,')],
        },
        {
            "name": "pawn_value_105",
            "description": (
                "P 100 -> 105 (+5cp): tiny pawn boost; pawn value is untouched so far.\n"
                "  Pawn value underpins all material trade decisions. Sunfish's P:N\n"
                "  ratio (1:2.8) is slightly low vs Stockfish (1:3.05); raising P\n"
                "  brings the ratio closer.\n"
                "  Hypothesis: small boost subtly improves trade evaluation."
            ),
            "replacements": [('"P": 100,', '"P": 105,')],
        },
        {
            "name": "combo_qs150_rook495",
            "description": (
                "Combine QS_LIMIT=150 (iter 6: 54%) with R=495 (iter 9: 54%).\n"
                "  These touch DIFFERENT mechanisms (search depth vs material value),\n"
                "  unlike round 2 iter 8 (mvv_lva + qs170) which both affected search.\n"
                "  Hypothesis: orthogonal improvements stack additively rather than\n"
                "  fighting each other; expect 55-58% if both signals are real."
            ),
            "replacements": [
                ("QS_LIMIT = 219", "QS_LIMIT = 150"),
                ('"R": 479,', '"R": 495,'),
            ],
        },
    ]

    print("=" * 60)
    print("AutoResearch round 3: 5 refined iterations (#11-15)")
    print(f"Batch: {BATCH_SIZE} games | Win threshold: {WIN_THRESHOLD_PCT}%")
    print("=" * 60)

    for i, exp in enumerate(experiments, start=11):
        print(f"\n{'='*60}")
        print(f"ITERATION {i}/15  [{exp['name']}]")
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

        seed = EVAL_SEED_BASE + (i - 11)
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
    print("Round 3 complete. See results.csv for full log.")


if __name__ == "__main__":
    main()
