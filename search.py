"""
search.py — AutoResearch optimization loop.

Implements the propose → evaluate → accept/reject cycle described in
program.md.  This file is frozen once implemented; only config.py is a valid
target for the AI researcher.

Usage:
    python search.py                        # run until Ctrl-C
    python search.py --max-iterations 20   # stop after 20 rounds
    python search.py --quiet               # suppress per-game output

Requires:
    ANTHROPIC_API_KEY environment variable
"""

from __future__ import annotations

import copy
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import anthropic

import engine as _engine_mod
import evaluator as _eval_mod


# ---------------------------------------------------------------------------
# Constants.
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent
RESULTS_CSV = str(REPO_ROOT / "results.csv")
BEST_CONFIG_YAML = REPO_ROOT / "best_config.yaml"
CONFIG_PY = REPO_ROOT / "config.py"
PROGRAM_MD = REPO_ROOT / "program.md"
LOGS_DIR = str(REPO_ROOT / "logs")

WIN_THRESHOLD_PCT = 55.0       # Win rate (%) required to accept a candidate.
MAX_AVG_SEC_PER_MOVE = 0.5     # Speed limit from program.md.
BATCH_SIZE = 50                # Games per evaluation batch.
EVAL_SEED_BASE = 2027          # Incremented each iteration for opening variety.

MODEL = os.environ.get("AUTORESEARCH_MODEL", "claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# PST-isolated engine wrapper.
#
# engine.py keeps piece-square tables in module-level globals (_PST,
# _MATE_LOWER, _MATE_UPPER) that are overwritten on every build_engine()
# call.  To run a fair head-to-head between candidate and baseline engines
# in the same process we snapshot each engine's PST at build time and swap
# the module globals around every think() call.
# ---------------------------------------------------------------------------

class _PSTIsolatedEngine:
    """Wraps SunfishEngine; restores captured PST globals before each think()."""

    def __init__(self, engine, pst: dict, mate_lower: int, mate_upper: int):
        self._engine = engine
        self._pst = pst
        self._mate_lower = mate_lower
        self._mate_upper = mate_upper

    # Delegate cfg attribute so evaluator can attach a 'name' key.
    @property
    def cfg(self):
        return self._engine.cfg

    @cfg.setter
    def cfg(self, value):
        self._engine.cfg = value

    def reset(self):
        self._engine.reset()

    def think(self, pos, history=(), time_budget=None):
        prev_pst = _engine_mod._PST
        prev_lower = _engine_mod._MATE_LOWER
        prev_upper = _engine_mod._MATE_UPPER
        _engine_mod._PST = self._pst
        _engine_mod._MATE_LOWER = self._mate_lower
        _engine_mod._MATE_UPPER = self._mate_upper
        try:
            return self._engine.think(pos, history, time_budget)
        finally:
            _engine_mod._PST = prev_pst
            _engine_mod._MATE_LOWER = prev_lower
            _engine_mod._MATE_UPPER = prev_upper


def _build_isolated(full_cfg: dict) -> _PSTIsolatedEngine:
    """Build a SunfishEngine from a complete cfg dict and capture its PST."""
    engine = _engine_mod.build_engine(config_overrides=full_cfg)
    pst = copy.deepcopy(_engine_mod._PST)
    return _PSTIsolatedEngine(
        engine, pst, _engine_mod._MATE_LOWER, _engine_mod._MATE_UPPER
    )


# ---------------------------------------------------------------------------
# Config helpers.
# ---------------------------------------------------------------------------

def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _exec_config(content: str) -> dict:
    """Execute a config.py string and return its full cfg dict."""
    ns: dict = {}
    exec(compile(content, "<config>", "exec"), ns)
    return ns["get_config"]()


def _write_config(content: str) -> None:
    CONFIG_PY.write_text(content, encoding="utf-8")


def _results_tail(n: int = 20) -> str:
    """Return the last n data rows of results.csv as a plain string."""
    try:
        lines = Path(RESULTS_CSV).read_text(encoding="utf-8").splitlines()
        if len(lines) <= 1:
            return "(no experiments yet)"
        return "\n".join(lines[max(1, len(lines) - n):])
    except FileNotFoundError:
        return "(results.csv not found)"


def _update_best_config(win_rate_pct: float, avg_sec: float, label: str) -> None:
    """Patch three scalar fields in best_config.yaml without touching the rest."""
    text = BEST_CONFIG_YAML.read_text(encoding="utf-8")
    updates = {
        "label": label,
        "win_rate_vs_baseline_pct": win_rate_pct,
        "avg_sec_per_move": avg_sec,
    }
    new_lines = []
    written: set = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or ":" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.partition(":")[0].strip()
        if key in updates:
            new_lines.append(f"{key}: {updates[key]}")
            written.add(key)
        else:
            new_lines.append(line)
    for k in updates:
        if k not in written:
            new_lines.append(f"{k}: {updates[k]}")
    BEST_CONFIG_YAML.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Claude API: propose a config change.
# ---------------------------------------------------------------------------

def _propose_config(
    client: anthropic.Anthropic,
    current_config: str,
    history: str,
    iteration: int,
) -> str:
    """Ask Claude to propose a modified config.py and return the file content."""
    program_rules = _read_file(PROGRAM_MD)
    best_yaml = BEST_CONFIG_YAML.read_text(encoding="utf-8")

    system = (
        "You are an AI researcher performing automated optimization of a Python "
        "chess engine (Sunfish). Each iteration you propose ONE targeted parameter "
        "change to config.py that might improve playing strength.\n\n"
        "## Rules from program.md\n"
        f"{program_rules}\n\n"
        "## Output format\n"
        "Return ONLY the complete, valid Python content for config.py inside a "
        "```python ... ``` code block. Preserve the full file structure exactly; "
        "change exactly one conceptual thing per iteration.\n\n"
        "## Suggested exploration directions\n"
        "- PST_SCALE: amplify (>1.0) or dampen (<1.0) positional bonuses.\n"
        "- PIECE_VALUES: nudge individual pieces by ±10–30 cp (avoid K).\n"
        "- QS_LIMIT: lower → deeper quiescence, higher → faster but shallower.\n"
        "- EVAL_ROUGHNESS: MTD-bi aspiration window width.\n"
        "- MOVE_ORDERING: try 'mvv_lva' for more tactical sharpness.\n"
        "- PST_OVERRIDES: replace a specific piece's table with a tuned version.\n"
        "Study the experiment history to avoid re-running failed ideas."
    )

    user = (
        f"Iteration {iteration}.\n\n"
        f"CURRENT config.py:\n```python\n{current_config}\n```\n\n"
        f"BEST CONFIG SO FAR:\n{best_yaml}\n\n"
        f"RECENT EXPERIMENT HISTORY (results.csv):\n{history}\n\n"
        "Propose the next config.py to maximize win rate against the baseline."
    )

    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = resp.content[0].text
    m = re.search(r"```python\s*(.*?)\s*```", raw, re.DOTALL)
    return m.group(1).strip() if m else raw.strip()


# ---------------------------------------------------------------------------
# Head-to-head evaluation with PST isolation.
# ---------------------------------------------------------------------------

def _run_evaluation(
    candidate_content: str,
    baseline_content: str,
    seed: int,
    verbose: bool,
) -> tuple:
    """Run BATCH_SIZE games: candidate (A) vs baseline (B).

    Returns (MatchSummary, label_a).

    Both engines capture independent PST snapshots so a config that changes
    piece-square values is evaluated fairly even though engine.py stores PSTs
    as module-level globals.
    """
    candidate_cfg = _exec_config(candidate_content)
    baseline_cfg = _exec_config(baseline_content)

    # Build order matters: the last build sets the module-level PST, which
    # becomes the 'resting' state between think() calls — harmless since each
    # wrapper restores its snapshot on entry and exit.
    candidate_eng = _build_isolated(candidate_cfg)
    baseline_eng = _build_isolated(baseline_cfg)

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


# ---------------------------------------------------------------------------
# Main loop.
# ---------------------------------------------------------------------------

def main(max_iterations: Optional[int] = None, verbose: bool = True) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY environment variable not set.")

    client = anthropic.Anthropic(api_key=api_key)

    # The "current best" config content — updated in memory when a candidate
    # is kept, and written to disk at the same time.
    best_config_content = _read_file(CONFIG_PY)

    print(f"AutoResearch chess loop | model={MODEL} | batch={BATCH_SIZE} games")
    print(f"Win threshold: {WIN_THRESHOLD_PCT}% | Speed limit: {MAX_AVG_SEC_PER_MOVE}s/move")
    print("Press Ctrl+C to stop.\n")

    iteration = 1
    while max_iterations is None or iteration <= max_iterations:
        sep = "=" * 60
        print(f"\n{sep}\nITERATION {iteration}\n{sep}")

        # --- Propose ---
        print(f"[{iteration}] Asking {MODEL} for a config change...")
        try:
            candidate_content = _propose_config(
                client, best_config_content, _results_tail(20), iteration
            )
        except Exception as exc:
            print(f"  Proposal failed: {exc}")
            iteration += 1
            continue

        # --- Validate: syntax ---
        try:
            compile(candidate_content, "config.py", "exec")
        except SyntaxError as exc:
            print(f"  Syntax error — skipping: {exc}")
            iteration += 1
            continue

        # --- Validate: cfg contract (get_config must succeed) ---
        try:
            candidate_cfg = _exec_config(candidate_content)
        except Exception as exc:
            print(f"  Config exec failed — skipping: {exc}")
            iteration += 1
            continue

        if candidate_cfg == _exec_config(best_config_content):
            print("  Proposal identical to current best — skipping.")
            iteration += 1
            continue

        # --- Evaluate ---
        seed = EVAL_SEED_BASE + iteration
        print(f"[{iteration}] Running {BATCH_SIZE}-game match (seed={seed})...")
        try:
            summary, label = _run_evaluation(
                candidate_content, best_config_content, seed, verbose
            )
        except Exception as exc:
            print(f"  Evaluation crashed: {exc}")
            iteration += 1
            continue

        win_pct = summary.a_win_rate_pct
        avg_sec = summary.a_avg_sec_per_move
        speed_ok = avg_sec <= MAX_AVG_SEC_PER_MOVE
        wins_enough = win_pct >= WIN_THRESHOLD_PCT
        status = "KEEP" if (wins_enough and speed_ok) else "DISCARD"

        print(
            f"\n  Result: {win_pct:.1f}% win rate  |  {avg_sec:.3f}s/move avg  →  {status}"
        )

        if wins_enough and speed_ok:
            best_config_content = candidate_content
            _write_config(candidate_content)
            _update_best_config(win_pct, avg_sec, label)
            print(f"  Saved to config.py and best_config.yaml.")
        else:
            if not wins_enough:
                print(f"  {win_pct:.1f}% < {WIN_THRESHOLD_PCT}% threshold.")
            if not speed_ok:
                print(f"  avg {avg_sec:.3f}s > {MAX_AVG_SEC_PER_MOVE}s speed limit.")

        _eval_mod.append_result_row(
            RESULTS_CSV,
            summary,
            notes=f"iteration={iteration} status={status}",
        )

        iteration += 1

    print("\nAutoResearch loop complete.")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="AutoResearch chess optimization loop.")
    ap.add_argument(
        "--max-iterations", type=int, default=None,
        help="Stop after N iterations (default: run until Ctrl-C).",
    )
    ap.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-game output during evaluation.",
    )
    args = ap.parse_args()
    main(max_iterations=args.max_iterations, verbose=not args.quiet)
