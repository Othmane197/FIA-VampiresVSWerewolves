# The Splitter: strategy documentation

This folder explains the whole AI: the strategy, the algorithms behind it, and the script and
function that implement each part. It is the source material for the project report.

Every algorithm description links to the exact function that implements it. Links point at a file and line (`file.py#L42`);
in VS Code, Ctrl+click opens the file at that line.

## Reading order

| # | Chapter | What it covers |
|---|---|---|
| 01 | [Overview](01_overview.md) | The problem, the idea (smart splitting), the architecture, and what happens in one turn |
| 02 | [Game rules and the real server](02_game_rules_and_server.md) | The rules as the server really applies them (probed and disassembled), and our exact copy of them: `splitter/rules.py`, `splitter/state.py` |
| 03 | [Plan generator](03_plan_generator.md) | How a turn is reduced to about 15 sensible joint plans: goals, safe steps, exact-size splits, safety checks, pincers, flee, commitment (`splitter/planner.py`) |
| 04 | [Evaluation](04_evaluation.md) | How a position is turned into a win probability: immediate tactics, merge- and contest-aware race projection, exposure, end-of-game scaling (`splitter/evaluate.py`) |
| 05 | [Search (MCTS)](05_search_mcts.md) | Open-loop Monte Carlo Tree Search over joint plans (`splitter/mcts.py`) |
| 06 | [Agent and safety net](06_agent_and_safety.md) | The time budget, the fallback chain, the never-illegal guarantee, and the link to the tournament client (`splitter/agent.py`, `ai_agent.py`, `main.py`) |
| 07 | [Testing and benchmarking](07_testing_and_benchmarking.md) | Unit tests, the fake server, the arena, snapshots, and how to run an experiment |
| 08 | [Results and iteration history](08_results_and_iterations.md) | Benchmark numbers, the no-split ablation, each improvement and the lost game that motivated it, rejected ideas, next steps |
| 09 | [Function index](09_function_index.md) | Generated table of every class and function, with line links |
| 10 | [Parameters](10_parameters.md) | Every tunable, its current value, and the evidence behind it |

The raw evidence for chapter 02 is [../SERVER_FINDINGS.md](../SERVER_FINDINGS.md).

## Keeping this documentation in sync with the code

The documentation is updated in the **same change** as the code:

1. **Regenerate the function index.** Run `python tools/gen_function_index.py`. Use `--check` to verify it is up to date.
2. **Fix line links in chapters 01–08 and 10** for every function whose line moved. The index from step 1 lists the new lines.
3. **Update the chapter that explains the changed behaviour.** If a parameter changed, update [10_parameters.md](10_parameters.md).
4. **New benchmark results go in [08](08_results_and_iterations.md),** with the command used.
5. **Add a line to the change log below.**

## Change log

| Date | Change | Chapters updated |
|---|---|---|
| 2026-10-19 | Documentation created for Splitter v5: contest-aware race, reserve radius 6, planner caches. Lint and type fixes: Ruff 0, Pylance 0 errors in our code. `MCTS.search` returns the best prior plan if no iteration finished in time. | all |
