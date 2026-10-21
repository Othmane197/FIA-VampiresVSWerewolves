# The Splitter: strategy documentation

This folder explains the whole AI: the strategy, the algorithms behind it, and the script and
function that implement each part. It is the source material for the project report.

Every algorithm description links to the exact function that implements it. Links point at a file and line (`file.py#L42`);
in VS Code, Ctrl+click opens the file at that line.

## Reading order

| # | Chapter | What it covers |
|---|---|---|
| 01 | [Overview](01_overview.md) | The problem, the idea (smart splitting), the architecture, the two kept models (flagship and backup), and what happens in one turn |
| 02 | [Game rules and the real server](02_game_rules_and_server.md) | The rules as the server really applies them (probed and disassembled), and our exact copy of them: `splitter/rules.py`, `splitter/state.py` |
| 03 | [Plan generator](03_plan_generator.md) | How a turn is reduced to about 15 sensible joint plans: goals, safe steps, exact-size splits, safety checks, pincers, flee, commitment (`splitter/planner.py`) |
| 04 | [Evaluation](04_evaluation.md) | How a position is turned into a win probability: immediate tactics, merge- and contest-aware race projection, exposure, end-of-game scaling; the backup's calibrated constants (`splitter/evaluate.py`) |
| 05 | [Search (MCTS)](05_search_mcts.md) | Open-loop Monte Carlo Tree Search over joint plans (`splitter/mcts.py`) |
| 06 | [Agent and safety net](06_agent_and_safety.md) | The time budget, the watchdog, the fallback chain, the never-illegal guarantee, the two models and how to choose one on tournament day (`splitter/agent.py`, `ai_agent.py`, `main.py`) |
| 07 | [Testing and benchmarking](07_testing_and_benchmarking.md) | Unit tests, the fake server, the arena, testing against bots inside and outside the repo (any language), randomized-style opponents, stored results, how to run an experiment, and 2–3× faster benchmarks (informative slots, early stopping, resume) |
| 08 | [Results and iteration history](08_results_and_iterations.md) | Benchmark numbers, the no-split ablation, tournament-speed results, each improvement and the lost game that motivated it, rejected ideas |
| 09 | [Function index](09_function_index.md) | Generated table of every class and function, with line links |
| 10 | [Parameters](10_parameters.md) | Every tunable, its current value, the evidence behind it, and the removed ones |
| 11 | [Opponent modelling (HMMs), retired](11_opponent_modeling.md) | Move reconstruction, style HMM (Baum-Welch), goal recognizer, policy HMM: how they worked, what they predicted, why they did not win games; the search bug found along the way |
| 12 | [Improvement campaign 1](12_experiments.md) | Screening, anti-overfitting validation on hold-out opponents and maps, replication on fresh dice, a pre-registered test; what reliably beat the baseline and what did not |
| 13 | [Future improvements](13_future_ideas.md) | The idea list after campaign 1, the outcome of each idea, and the next steps |
| 14 | [Improvement campaign 2](14_campaign2.md) | 17 ideas (search, caching, path planning, swarm, prediction, evaluation fitting, clock), their implementation, four validation stages up to a pre-registered 1.5 s test, the choice and verification of the two kept models |
| 15 | [Failed strategies](15_failed_strategies.md) | The do-not-retry register: every rejected idea of both campaigns, its result, the likely reason, and what would justify a retry |

## The optimization process at a glance

1. **Build from lost games (v1–v5, chapter 08).** Every change came from reading a game the bot lost: merge-aware race, commitment, pincers, the 30% strike threshold, protected plans, flee into open space, contest-aware race. 81% → 79% against a much stronger panel.
2. **Find bugs with instrumentation (v6, chapter 11.8).** Integrating the opponent model exposed an open-loop search bug that silently lost 4.1% of turns: fixing it gave +2.2 points, the largest single gain of the project.
3. **Campaign 1 (chapter 12): learn to distrust screens.** Fourteen variants screened, the best (+11.3) vanished on unseen maps and opponents. Method adopted: tuning vs hold-out data, paired comparisons on the same dice, replication, pre-registration.
4. **Validate at tournament speed (chapter 08.2).** The runner-up was neutral at 0.2 s and −14.8 at 1.5 s: the final word always belongs to 1.5 s games.
5. **Campaign 2 (chapter 14): explore widely, keep almost nothing.** Seventeen ideas, all within noise; screen winners changed sign on unseen data again. The evaluation fit (from game outcomes) became the backup model. Testing became 2–3× cheaper (informative slots, early stopping).
6. **Verify the choice.** A pre-registered 1.5 s run fixed the ranking; the kept flagship makes the same decisions as the validated v7 on 300 of 300 test positions.
7. **Record the failures (chapter 15)** so that nobody spends another week rediscovering them.

The raw evidence for chapter 02 is [../SERVER_FINDINGS.md](../SERVER_FINDINGS.md).

## Keeping this documentation in sync with the code

The documentation is updated in the **same change** as the code:

1. **Regenerate the function index.** Run `python tools/gen_function_index.py`. Use `--check` to verify it is up to date.
2. **Fix line links in the chapters** for every function whose line moved: `python tools/gen_function_index.py --fix` moves each link to its function's current definition line (review the diff).
3. **Update the chapter that explains the changed behaviour.** If a parameter changed, update [10_parameters.md](10_parameters.md).
4. **New benchmark results go in [08](08_results_and_iterations.md),** with the command used.
5. **Add a line to the change log below.**

## Change log

| Date | Change | Chapters updated |
|---|---|---|
| 2026-10-21 | `tools/teammate_matches.py`: real-conditions matches vs the teammates' bots (real protocol, 2 s, 200 plies, 5-minute clock, `main.py` as client, one game at a time, no speed-ups), 3 games per opponent, recorded. Fake server: game clock and connection-order tracking (also used by `tools/server_match.py`). 38 tests. | 07, 08 |
| 2026-10-21 | v8, campaign 2: 17 ideas implemented and measured (screen, unseen-data replication, 1.5 s, pre-registered verification). Kept: flagship **Splitter** (unchanged, 300/300 identical decisions with v7) and backup **Splitter-Calibrated** (evaluation fitted on outcomes, `SPLITTER_MODEL=backup`). Retired: Splitter-HMM (−11.9 ± 4.1 at 1.5 s) and its files (`splitter/observe.py`, `opponent_model.py`, `opponent_params.py`, `tools/opponent_report.py`, `tools/train_opponent_model.py`, `tests/test_opponent_model.py`). Added: `main.py` watchdog, `Styled:<n>` opponents, referee game clock, `tools/tune_eval.py`, `tools/informative_slots.py`, `arena.run --slots / --drop-worse / --resume`, keep-awake. Local archive snapshot `splitter_c2` with every campaign-2 option. 37 tests. | 01, 03, 04, 05, 06, 07, 08, 10, 11, 12, 13, 14 (new), 15 (new) |
| 2026-10-20 | v7 clean-up. Two strategies kept: flagship **Splitter** (v6 defaults) and runner-up **Splitter-HMM** (`opponent_model=True`). Deleted after measurement (code preserved in commit `79fd09c`): goal recognizer, policy HMM, search steering, pre-emptive plans, kiting, light tree, `split_enemy_dist`, `prize_lock`, map-aware deathball, `--pregame`. Testing: external Python bots (`py:<file>`), `tools/server_match.py` (any two programs over the protocol), stored history (`history.csv`, `comparisons.csv`, `python -m arena.history`). 39 tests; Ruff and Pylance clean. Tournament-speed validation. | all; 13 (new) |
| 2026-10-20 | v6: open-loop expansion fix (+2.2 pts, default). Opponent model (`splitter/observe.py`, `splitter/opponent_model.py`, `tools/opponent_report.py`, `tools/train_opponent_model.py`) and the pre-emptive, adaptive, pre-game and map-aware switches: all measured, off by default. Arena: multi-bot shared pool, paired comparison, `--panel fast`, hold-out maps, `--save-all-logs`. 34 tests. | 03, 04, 05, 06, 07, 08, 10, 11 (new), 12 (new) |
| 2026-10-19 | Documentation created for Splitter v5: contest-aware race, reserve radius 6, planner caches. Lint and type fixes: Ruff 0, Pylance 0 errors in our code. `MCTS.search` returns the best prior plan if no iteration finished in time. | all |
