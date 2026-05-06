"""
run_week4_experiments.py — Three controlled experiments for Week 4 deliverables.

Each experiment varies ONE axis with all other config held fixed. Each level is
replicated across 2 seeds for stability assessment.

Experiments:
  A. QS_LIMIT sweep   {50, 100, 150, 219 (baseline), 300}  - search axis
  B. PST_SCALE sweep  {0.7, 1.0 (baseline), 1.3}            - eval axis
  C. null-move toggle {True (baseline), False}              - algorithm axis (engine.py edit)

Results written to:
  - week4_results_matrix.csv  (one row per (experiment, level, seed, game_batch))
  - results.csv               (existing autoresearch log; appended)
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
from search import _exec_config

CONFIG_PY = REPO_ROOT / "config.py"
RESULTS_CSV = str(REPO_ROOT / "results.csv")
MATRIX_CSV = str(REPO_ROOT / "week4_results_matrix.csv")
LOGS_DIR = str(REPO_ROOT / "logs")

N_GAMES = 50
N_WORKERS = 8
SEEDS = [4001, 4002]   # 2 replicates per level

MATRIX_COLS = [
    "timestamp", "experiment", "axis", "level_name", "level_value",
    "seed", "n_games", "win_pct", "avg_plies",
    "a_avg_sec_per_move", "b_avg_sec_per_move",
    "a_max_sec_per_move", "b_max_sec_per_move",
    "wins", "losses", "draws", "wall_seconds",
    "engine_modified", "notes",
]


def _ensure_matrix_header():
    if not Path(MATRIX_CSV).exists():
        with open(MATRIX_CSV, "w", newline="") as f:
            csv.writer(f).writerow(MATRIX_COLS)


def _append_matrix_row(experiment, axis, level_name, level_value, seed,
                        summary, engine_modified, notes):
    with open(MATRIX_CSV, "a", newline="") as f:
        csv.writer(f).writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            experiment, axis, level_name, level_value, seed,
            summary.n_games, summary.a_win_rate_pct, summary.avg_plies,
            summary.a_avg_sec_per_move, summary.b_avg_sec_per_move,
            summary.a_max_sec_per_move, summary.b_max_sec_per_move,
            summary.a_wins, summary.b_wins, summary.draws,
            summary.wall_seconds, engine_modified, notes,
        ])


def _run_one(experiment, axis, level_name, level_value, seed,
              candidate_cfg, baseline_cfg, engine_modified=False, notes=""):
    """Run one 50-game match, log to matrix and results.csv."""
    label = f"{experiment}_{level_name}_seed{seed}"
    print(f"  [{label}] running {N_GAMES} games (n_workers={N_WORKERS})...")
    t0 = time.time()
    summary = _eval_mod.run_match_parallel(
        candidate_cfg, baseline_cfg,
        label_a=label,
        label_b="sunfish_baseline",
        n_games=N_GAMES,
        n_workers=N_WORKERS,
        seed=seed,
        log_path=LOGS_DIR,
        verbose=False,
    )
    wall = time.time() - t0
    print(f"    win_pct={summary.a_win_rate_pct:.1f}%  "
          f"W={summary.a_wins} L={summary.b_wins} D={summary.draws}  "
          f"avgA={summary.a_avg_sec_per_move:.3f}s  wall={wall:.0f}s")
    _append_matrix_row(
        experiment, axis, level_name, level_value, seed,
        summary, engine_modified=engine_modified, notes=notes,
    )
    _eval_mod.append_result_row(
        RESULTS_CSV, summary,
        notes=f"week4 exp={experiment} level={level_name} seed={seed}",
    )
    return summary


def main():
    _ensure_matrix_header()
    baseline_cfg = _exec_config(CONFIG_PY.read_text(encoding="utf-8"))

    overall_t0 = time.time()
    print("=" * 60)
    print(f"Week 4 controlled experiments  (parallel, {N_WORKERS} workers)")
    print(f"Estimated wall time: ~50 min  ({len(SEEDS)} seeds x ~10 levels)")
    print("=" * 60)

    # ---------------------------------------------------------------
    # Experiment A: QS_LIMIT sweep
    # ---------------------------------------------------------------
    print("\n" + "#" * 60)
    print("# EXPERIMENT A: QS_LIMIT sweep")
    print("#" * 60)
    qs_levels = [50, 100, 150, 219, 300]  # 219 is baseline
    for level in qs_levels:
        cand = dict(baseline_cfg)
        cand["qs_limit"] = level
        for seed in SEEDS:
            _run_one(
                experiment="A",
                axis="qs_limit",
                level_name=f"qs_{level}",
                level_value=level,
                seed=seed,
                candidate_cfg=cand,
                baseline_cfg=baseline_cfg,
                engine_modified=False,
                notes=f"qs_limit={level} (baseline=219)",
            )

    # ---------------------------------------------------------------
    # Experiment B: PST_SCALE sweep
    # ---------------------------------------------------------------
    print("\n" + "#" * 60)
    print("# EXPERIMENT B: PST_SCALE sweep")
    print("#" * 60)
    pst_levels = [0.7, 1.0, 1.3]  # 1.0 is baseline
    for level in pst_levels:
        cand = dict(baseline_cfg)
        cand["pst_scale"] = level
        for seed in SEEDS:
            _run_one(
                experiment="B",
                axis="pst_scale",
                level_name=f"pst_{level}",
                level_value=level,
                seed=seed,
                candidate_cfg=cand,
                baseline_cfg=baseline_cfg,
                engine_modified=False,
                notes=f"pst_scale={level} (baseline=1.0)",
            )

    # ---------------------------------------------------------------
    # Experiment C: null-move pruning ablation (engine.py modification)
    # ---------------------------------------------------------------
    print("\n" + "#" * 60)
    print("# EXPERIMENT C: null-move pruning ablation")
    print("#" * 60)
    nm_levels = [True, False]  # True is baseline
    for level in nm_levels:
        cand = dict(baseline_cfg)
        cand["enable_null_move"] = level
        level_name = f"null_move_{'on' if level else 'off'}"
        for seed in SEEDS:
            _run_one(
                experiment="C",
                axis="enable_null_move",
                level_name=level_name,
                level_value=str(level),
                seed=seed,
                candidate_cfg=cand,
                baseline_cfg=baseline_cfg,
                engine_modified=True,  # required engine.py change
                notes=f"enable_null_move={level} (baseline=True)",
            )

    elapsed_min = (time.time() - overall_t0) / 60
    print("\n" + "=" * 60)
    print(f"All experiments complete. Total wall time: {elapsed_min:.1f} min")
    print(f"Matrix written to: {MATRIX_CSV}")
    print(f"Results appended to: {RESULTS_CSV}")
    print("=" * 60)


if __name__ == "__main__":
    main()
