# program.md — Rules for the AutoResearch agent

This file defines the contract between the human researcher and the AutoResearch
agent. It is **not editable by the agent**.

## Goal

Improve the lightweight Python chess engine's playing strength under fast time
controls (0.1–0.5 sec/move). Success = modified engine achieves ≥55% win rate
vs baseline Sunfish over ≥200 games (per charter success criteria).

## What the agent is allowed to edit

| File              | Editable? | Purpose                                           |
| ----------------- | --------- | ------------------------------------------------- |
| `program.md`      | NO        | This file. The rules of the game.                 |
| `README.md`       | NO        | Human-facing docs.                                |
| `requirements.txt`| NO        | Python dependencies.                              |
| `engine.py`       | **YES (Week 4+)** | Chess engine; tunable for controlled experiments. |
| `config.py`       | **YES**   | Tunable parameters. The agent's playground.       |
| `evaluator.py`    | NO        | Match runner. Frozen to prevent gaming the metric.|
| `search.py`       | NO        | The AutoResearch optimization loop.               |
| `results.csv`     | append    | Experiment log. Append-only; never rewrite.       |
| `best_config.yaml`| YES       | Best config found so far.                         |
| `test_engine.py`  | NO        | Regression test.                                  |

## What the agent may tune (in `config.py`)

- **Piece values** (`piece_values`): P/N/B/R/Q/K base material values.
- **PST weights** (`pst_scale`): uniform or per-piece scale on piece-square tables.
- **Search params**:
  - `qs_limit`: quiescence search capture threshold
  - `eval_roughness`: aspiration-window width for MTD-bi
  - `draw_test`: whether to detect repetitions during search
- **Move ordering**: see `config.py` comments.
- **Time management** (`time_per_move`, `early_exit_margin`).

## What is off-limits

- No neural networks, no external datasets.
- No edits to `evaluator.py`'s **protocol logic** (game rules, draw detection,
  color alternation, seed schedule). Implementation-only edits (parallelism,
  IO) that preserve protocol semantics are allowed.
- No access to the evaluator's random seeds or opening book during proposal.
- No changes that bypass the speed constraint (avg ≤0.5 sec/move).

## Engine modifications (Week 4+)

`engine.py` is editable for controlled experiments under these constraints:

1. **Single-axis changes only.** Each experimental run modifies exactly one
   algorithmic axis (e.g., toggle null-move pruning, change a heuristic).
   Bundled changes are forbidden.
2. **Document every change.** Each experiment must explicitly record what was
   modified, what was held fixed, and the expected effect direction.
3. **Preserve protocol invariants.** Modifications must NOT change:
   - Position legality / move-generation correctness
   - Game-end detection (mate, stalemate, draws)
   - The `build_engine()` and `SunfishEngine.think()` public API
   - The deterministic-given-seed property
4. **Add a config flag for each algorithmic toggle.** Don't hardcode
   `if False:` blocks; expose as a `cfg["enable_xxx"]` boolean so the change
   is reversible and auditable. Add the flag to `config.py`'s `get_config()`.

## Success = measurable, reproducible, fast

An accepted config must:
1. Win ≥55% of games vs baseline over ≥200 games (or pass a gating batch of 50).
2. Respect the speed constraint: avg sec/move ≤ 0.5.
3. Not regress on the smoke test (`test_engine.py`).

## Change protocol (used by `search.py` in Week 3)

1. Read this file.
2. Propose a diff to `config.py`.
3. Run `evaluator.py` with candidate config vs baseline.
4. If win rate increased beyond noise floor → keep; append row to `results.csv`;
   update `best_config.yaml`.
5. Else → revert `config.py` and append a "rejected" row to `results.csv`.
