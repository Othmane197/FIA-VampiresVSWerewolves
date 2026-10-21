# 07 · Testing and benchmarking

Every claim in this documentation was checked by one of the tools below. They are also how the
bot was improved: **measure → read the lost games → fix → re-measure on the same seeds**.

## 7.1 Unit and end-to-end tests: [tests/](../../tests)

Run with `python -m unittest discover tests` (standard library only, about 35 s). **38 tests**:

| File | Tests | What they guarantee |
|---|---|---|
| [test_rules.py](../../tests/test_rules.py) | `test_server_formula`, `test_defender_1_5x_is_random_not_sure`, `test_sure_results`, `test_legal_split`, `test_cheats`, `test_byte_overflow_refused`, `test_probe1_split_and_merged_attack`, `test_sure_kill_and_merge`, `test_mean_mode_deterministic` | Our rules = the real server's: formulas, the defender-random rule, each cheating case, and a replay of the live probe game |
| [test_planner.py](../../tests/test_planner.py) | `test_fuzz_all_plans_legal` (500 random positions × 3 configs, more than 1,000 plans, plus `quick_plan` and `fallback_plan`), `test_safe_step_never_walks_into_bigger_humans`, `test_split_generated_for_two_small_houses`, `test_no_split_when_disabled`, `test_detachment_safety`, `test_unsafe_house_not_split_to` | Every generated plan is legal; splits appear when they should and never toward an unsafe house |
| [test_agent.py](../../tests/test_agent.py) | **Puzzles:** `test_takes_the_sure_kill`, `test_does_not_suicide_or_wait_next_to_a_killer`, `test_splits_to_take_two_adjacent_houses`, `test_converges_two_groups_on_a_big_house`. **Safety:** `test_time_budget_big_map`, `test_fuzz_never_illegal`, `test_backup_model_never_illegal`, `test_watchdog_sends_the_fallback_when_late`, `test_tournament_client_selects_the_model`, `test_gamestate_interface` | Correct tactical decisions; the budget is respected; a legal move every time, for both models; a late agent is replaced by the fallback move; `SPLITTER_MODEL` really selects the model |
| [test_protocol.py](../../tests/test_protocol.py) | `test_full_game_no_cheat_no_timeout`, `test_small_map_to_the_end` | Two real `main.py` processes play complete games against the fake server: no cheating, no timeout, clean BYE |
| [test_arena.py](../../tests/test_arena.py) | `test_python_file_bots_are_loaded_and_play`, `test_arena_task_against_a_file_bot_stores_its_files`, `test_flagship_and_backup`, `test_styled_opponents_are_reproducible`, `test_unknown_option_is_refused`, `test_history_and_comparisons_are_appended`, `test_rounds_keep_the_pairs_together`, `test_paired_delta_and_drop_rule`, `test_informative_slots_skip_games_nobody_disagrees_on`, `test_real_conditions_script_plays_and_records`, `test_two_programs_play_over_the_protocol` | The testing infrastructure itself: external bots of both interfaces load and play and their logs get valid file names; the two kept models are built as documented; styled opponents are reproducible; results are stored; the faster-benchmark machinery (rounds, early stopping, slot selection) is correct; the real-conditions script plays, alternates the connection order and records its games; two client programs play a server match (7.5) |

## 7.2 Fake server: [tools/fake_server.py](../../tools/fake_server.py)

[`FakeServer`](../../tools/fake_server.py#L52) is a headless copy of the official server.

**What it copies:**
- the **binary protocol** (NME → SET, HUM, HME, MAP; UPD ↔ MOV; END, BYE);
- **player 0 moves first;**
- **UPD contents:** the cells that changed since that player's last UPD;
- **timeouts:** a late reply skips the turn, and leftover bytes are flushed;
- **cheating** (`check_moves`) or a dropped connection ends the game;
- optionally the **game clock** (`game_seconds`, the real server's `MaxGameDuration` of 5 minutes);
- it reports how many players have connected, so launchers can enforce the connection order (= who is player 0).

[`FakeServer.run`](../../tools/fake_server.py#L84) plays one full game. It works on any OS, so
`main.py` can be tested without the Windows GUI.

Command line: `python tools/fake_server.py --map testmap.xml --port 5555`.

## 7.3 Real server and analysis tools

| Tool | Use |
|---|---|
| [tools/restart_server.ps1](../../tools/restart_server.ps1) | Restart the official exe with a chosen map, `MaxPlays` and `MaxPlayDuration`. It rewrites the `.exe.config`; restore it with `git checkout VampiresVSWerewolvesGameServer.exe.config` |
| [tools/probe_server.py](../../tools/probe_server.py) | Scripted probe scenarios (`rules`, `late`, `rule5`, `thr15`, `thr6`, `long`) that established chapter 02 |
| [tools/play_bot.py](../../tools/play_bot.py) | Connect any arena bot (e.g. `Apex`) to a server, to watch Splitter vs a teammate in the GUI |
| [tools/teammate_matches.py](../../tools/teammate_matches.py) | **Real-conditions matches**: our tournament client vs each teammate's bot, 4 games each (2 per role), over the protocol, recorded (7.5) |
| [tools/server_match.py](../../tools/server_match.py) | Play **any two client programs** against each other over the protocol (7.5) |
| [tools/tune_eval.py](../../tools/tune_eval.py) | Fits the evaluation's calibration constants on recorded games (log-loss, with a check set and a calibration table); produced the backup model (chapter 14.3) |
| [tools/informative_slots.py](../../tools/informative_slots.py) | Picks the (opponent, map) slots that discriminate between configurations, for 2–3× cheaper benchmarks (7.8) |
| [tools/gen_function_index.py](../../tools/gen_function_index.py) | Generates chapter 09; `--check` verifies the index and every chapter link, `--fix` re-points moved links |

## 7.4 Arena: [arena/](../../arena)

| File | Role |
|---|---|
| [fetch_opponents.py](../../arena/fetch_opponents.py) | [`fetch`](../../arena/fetch_opponents.py#L38) copies the teammates' current bots from their git branches (`origin/Othmane`, `origin/Ronita`, `origin/Dana`) into `arena/vendor/` (gitignored): **every top-level `.py` file** except the shared starter-kit files and their tests, so new or renamed helper modules are picked up and deleted ones removed. `vendor/<branch>/REVISION` records the commit copied. Run `python -m arena.fetch_opponents --fetch` (`--fetch` = `git fetch` their latest pushes first) |
| [opponents.py](../../arena/opponents.py) | [`make_bot(spec, time_limit)`](../../arena/opponents.py#L310) builds any bot behind one interface ([`Bot`](../../arena/opponents.py#L76)). Adapters for the team's two interfaces ([`GameStateBot`](../../arena/opponents.py#L88), [`BoardBot`](../../arena/opponents.py#L110)), plus [`SplitterBot`](../../arena/opponents.py#L127), [`SnapshotBot`](../../arena/opponents.py#L256) and external files ([`load_external`](../../arena/opponents.py#L267)). [`load_vendor`](../../arena/opponents.py#L52) imports a teammate's modules without name clashes. All specs are listed in 7.5 |
| [referee.py](../../arena/referee.py) | [`play_game`](../../arena/referee.py#L59): one game with the **server's rules** (it uses `State.apply` and `check_moves`). Illegal or crash → the offender loses; too slow → turn skipped. Records the move log, split turns and decision times; `record=True` keeps the full trace (ground truth for chapter 11) |
| [maps.py](../../arena/maps.py) | [`build_suite`](../../arena/maps.py#L138): 14 **tuning** maps in 6 families: `given` (thetrap, testmap), `sym`, `villages` (many small houses), `prize` (big central house), `close` (close starts), `sparse`; plus the **`holdout`** family (8 maps, fresh seeds) that is only used to validate, never to tune (`--maps all` excludes it). All generated maps are point-symmetric ([`symmetric_map`](../../arena/maps.py#L63)), so neither side has a map advantage. [`write_xml`](../../arena/maps.py#L43) exports a map for the real GUI; `.xml` paths are accepted too |
| [run.py](../../arena/run.py) | The benchmark command line ([`main`](../../arena/run.py#L260)). Every (opponent, map) pair is played on **both species**, alternating the first player. **Seeds are fixed per game**, so two configurations meet the same dice. `--bot A B C` runs several configurations in **one shared pool**, longest games first, and prints a **paired comparison** of each with the first ([`compare`](../../arena/run.py#L169)). `--panel fast` = Apex, RaceMCTS, Expecti, TacticalSplitter; `--seed` changes all dice; `--save-all-logs` records full games. Reports win rate ± standard error by opponent, map, side and first player ([`report`](../../arena/run.py#L94)) and stores everything (7.6) |
| [history.py](../../arena/history.py) | Browse the stored results of every run and server match (7.6) |
| [replay.py](../../arena/replay.py) | Replay one game verbosely |
| [snapshot.py](../../arena/snapshot.py) | `python -m arena.snapshot v7` freezes `splitter/` as `Snap:v7`, for A/B tests against the next version. Kept locally (gitignored): `v5fix` (the v5 baseline of chapters 11–12) and `v7` (the current flagship) |

## 7.5 Testing against other bots, inside and outside the repo

| Opponent | How to name it | Example |
|---|---|---|
| **Our two models** | `Splitter` (flagship), `Splitter-Calibrated` (backup) | `--bot Splitter Splitter-Calibrated` |
| Randomized opponent styles (no teammate plays like this) | `Styled:<n>` (`--panel styled` = `Styled:1`–`Styled:6`) | `--opp Styled:2 Styled:5` |
| Style proxies | `Splitter:splits=0` (deathball), `Splitter:gamble=always,c=0.9` (aggressive) | `--opp "Splitter:splits=0"` |
| Any variant of ours | `"Splitter:key=value,..."` (any `SplitterAgent` / `PlanConfig` option; unknown keys are refused) | `"Splitter:c=0.8,rollout_depth=0"` |
| A frozen version of ours | `Snap:<version>[:key=value,..]` | `Snap:v7`, `Snap:v5fix` |
| Teammates' bots (from their branches) | `Apex`, `RaceMCTS`, `Expecti`, `TacticalSplitter`, `Grabber`, `Rusher`, `Greedy`, `Starter`, `Turtle`, … (after `python -m arena.fetch_opponents`) | `--opp Apex RaceMCTS` |
| **Any Python bot file outside the repo** | `py:<path/to/file.py>[:ClassName]` | `--opp "py:../OtherTeam/ai_agent.py:AIAgent"` |
| **Any program in any language** (Java, C++, an exe, another team's `main.py`) | [tools/server_match.py](../../tools/server_match.py) with two client commands | see below |

**External Python files** ([`load_external`](../../arena/opponents.py#L267)). The file is imported
with its own folder on the path (so its sibling modules load). Without `ClassName`, the first class
defining `compute_moves` is used. The interface is detected from the signature:
`compute_moves(state)` → the repo's `GameState` interface; `compute_moves(board, species)` →
Othmane's `BoardState` interface. The class is built with no argument, or with its name if the
constructor requires one.

**Server matches between any two programs** ([`play_one`](../../tools/server_match.py#L60)):

```bash
python tools/server_match.py \
    --a "python main.py --name Splitter {host} {port}" \
    --b "java -jar ../OtherTeam/bot.jar {host} {port}" \
    --maps given,villages --games 2 --timeout 2.0
```

- Each game starts a `FakeServer` on a free port and launches both commands (`{host}` and `{port}` are filled in).
- The two clients **alternate who connects first**, so each plays both species and both move orders.
- Output: one line per game (score, reason, plies, totals, cheating), then the score of A with its standard error, timeouts and cheats.

### Real-conditions matches against the teammates: [tools/teammate_matches.py](../../tools/teammate_matches.py)

The arena is built for fast, paired comparisons. To see how the **tournament bot** does against
each teammate **under the real server's conditions**, use this script instead:

```bash
python tools/teammate_matches.py                       # flagship vs Apex, TacticalSplitter, RaceMCTS, Expecti: 4 games each
python tools/teammate_matches.py --model backup        # the backup model
python tools/teammate_matches.py --opp Apex --games 8  # one opponent, more games (keep a multiple of 4)
python tools/teammate_matches.py --all                 # every bot on the teammates' branches
python tools/teammate_matches.py --no-update           # replay the versions already downloaded
```

**Always the teammates' latest code.** Before the first game, the script downloads what the
teammates have pushed (`git fetch` of their branches) and copies their current code into
`arena/vendor/`. Then it loads each bot once in a fresh process as a check: a bot whose latest
version does not load is reported as **unavailable** (with the error) and skipped, and the
others still play. Every result records the exact version played (branch @ commit, date,
commit message). Without network, the last downloaded version is used, and the summary says so.

| Condition | Arena (`arena.run`) | `teammate_matches.py` |
|---|---|---|
| Rules | Our exact copy of the rules, in-process | **Real binary protocol** through [`FakeServer`](../../tools/fake_server.py#L52): 2 s per move, a late move skips the turn, illegal / empty move or dropped connection = cheating |
| Game end | 200 plies (no clock) | 200 plies **and the 5-minute game clock** (`MaxGameDuration`, `--game-seconds 300`) |
| Our bot | `SplitterAgent` called directly | **`main.py`, the tournament client**, with its watchdog, launched as on tournament day |
| Opponents | Called in-process; the copy in `arena/vendor/` from the last `fetch_opponents` | Each teammate bot is its own client process (`tools/play_bot.py`), **updated to their latest push at the start of every run** |
| Who plays first | Alternated | By **connection order**, as on the real server (first to connect = Vampires = moves first) |
| Speed-ups | Slots, early stopping, parallel workers | **None**: every game is played to its end, one game at a time, 1.5 s per move for every bot |
| Maps and sides | 14 tuning + 8 hold-out, both sides | The official sample maps `testmap.xml` and `thetrap.xml`; the default 4 games per opponent cover every (map, side) combination, **2 games in each role**: testmap as Vampires, thetrap as Vampires, testmap as Werewolves, thetrap as Werewolves (`--maps` to change) |

**Output** (`arena/results/teammates/<date-time>_<model>/`): `games.csv` (one row per game,
written as soon as it ends: opponent and its version, result, reason, plies, final totals,
timeouts of both sides, our slowest move read from `main.py`'s log, watchdog fallbacks,
cheating), `summary.md` (the versions played, any unavailable opponent, and the summary table),
`logs/` (both clients' output for every game), and one line per opponent, with its version, in
`arena/results/history.csv`.

## 7.6 Stored results

Every run is kept, so experiments can be compared later without re-running them.

| File | Written by | Content |
|---|---|---|
| `arena/results/<time>_<bot>.csv` | `arena/run.py` | One row per game: bot, opponent, map, side, seed, score, margin, timeouts, illegal moves, crashes, decision times |
| `arena/results/history.csv` | `arena/run.py` ([`store_history`](../../arena/run.py#L150)), `tools/server_match.py` | One summary line per bot per run: opponents, maps, games, time, seed, score ± se, problems |
| `arena/results/comparisons.csv` | `arena/run.py` | Every paired comparison (`--bot A B ...`): delta vs the reference, overall and per opponent, ± se |
| `arena/results/logs/<run>/` | `arena/run.py` | The log of every game not won, for reading lost games |
| `arena/results/traces/<run>/` | `arena/run.py --save-all-logs` | Full move records (ground truth) for the opponent-model tools |
| `arena/results/server_matches/*.csv` | `tools/server_match.py` | One row per server game |

`arena/results/` is gitignored. Browse it with:

```bash
python -m arena.history                    # last 20 runs
python -m arena.history --bot Splitter-Calibrated   # one bot's runs
python -m arena.history --comparisons      # paired comparisons
```

## 7.7 How to run an experiment

```bash
python -m arena.fetch_opponents --fetch                           # the teammates' latest pushed bots
python -m arena.snapshot v7                                       # freeze the current version
# ... change the code ...
# screening: several candidates, ONE pool, paired vs the first (the baseline)
python -m arena.run --bot Snap:v7 Splitter "Splitter:c=0.4" --opp RaceMCTS Expecti Snap:v5fix --maps all --games 2 --time 0.1
# validation on data never used for tuning (anti-overfitting)
python -m arena.run --bot Snap:v7 Splitter --opp Apex RaceMCTS Expecti Styled:1 Styled:2 Styled:3 --slots arena/slots/holdout.json --drop-worse --time 0.25
# replication on fresh dice, all 22 maps
python -m arena.run --bot Snap:v7 Splitter --maps given,sym,villages,prize,close,sparse,holdout --games 1 --time 0.2 --seed 7000
# tournament speed
python -m arena.run --bot Splitter Splitter-Calibrated --slots arena/slots/holdout.json --drop-worse --time 1.5 --hard 2.0 --workers 4 --out run.csv
```

**Reading the numbers:**
- Differences smaller than about 2 standard errors are noise. 24 games per opponent means about ±10%; 448 games means about ±2%.
- Always confirm a promising change on the full set: several "improvements" seen on 96 games disappeared there (chapter 08).
- **Validate on the hold-out opponents and maps before adopting anything.** The best tuning result of the campaign (+11.3) vanished there (chapter 12).
- With many candidates, one will look good by luck: replicate on fresh dice (`--seed`).
- Benchmarks run at 0.1–0.2 s per move for speed. At 1.5 s, use at most 4 workers on 8 cores (two thinking bots per game), so that the CPU is not shared and the timings stay honest.

## 7.8 Faster benchmarks without losing accuracy

**Why benchmarks were slow.** Every bot thinks for a fixed time per move, so a game lasts about
time × plies × thinking bots, whatever the code speed. At 1.5 s, the 288-game stage-3 run of
chapter 14 needed more than 3 hours. The levers are fewer games and fewer plies, not faster code.

| Idea | Measured on our stored games | Verdict |
|---|---|---|
| **Informative slots** ([tools/informative_slots.py](../../tools/informative_slots.py), `arena.run --slots`) | A paired comparison learns nothing from a game that every configuration wins (or loses) alike. In the 18-configuration screen, the 26% of the plies spent on slots where no configuration ever disagreed (TacticalSplitter, Apex and Expecti on village maps, ...) carried **no information**; 90% of the disagreement came from 43% of the plies. **Cross-validated** (slots chosen on half of the candidates, evaluated on the other half): same verdicts, same z-scores, **2.1× to 3.0× more precision per ply** | **Adopted.** Default for screening and validation |
| **Early stopping** (`arena.run --drop-worse`) | Plays in 4 rounds (pairs kept together); after each, a candidate with paired Δ + 2 SE < 0 (after ≥ 20 games) is stopped | **Adopted.** Saves the remaining rounds of clearly bad candidates; never stops the reference |
| **Resume** (`arena.run --out run.csv`, then `--resume run.csv`) | Every game is written as soon as it ends; an interrupted run (sleep, crash, closed session) continues where it stopped | **Adopted** (an interrupted 1.5 s run used to lose everything) |
| Adjudication: stop a game when one side leads by a ratio | On 576 recorded games: ratio 3× is never wrong but saves only 6% of the plies; ratio 2× saves 13% but misjudges 0.6–1.2% of games; 1.5× misjudges 2–4% | **Rejected** |
| Adjudication: stalemate (no humans, totals unchanged for N plies) | Saves 20–34% of the plies but misjudges **2–7%** of games: late gambles really do flip games | **Rejected.** The endgame matters |
| More workers at 1.5 s | Oversubscribing the CPU shrinks every bot's thinking time: it would test at another speed | Rejected |

**Recommended workflow (chapter 14):**

```bash
# 1. screen on the informative tuning slots, stop bad candidates early
python -m arena.run --bot Splitter "Splitter:x=1" "Splitter:y=2" --slots arena/slots/tuning.json --drop-worse --time 0.25
# 2. validate on the informative hold-out slots (+ styled opponents), then at 1.5 s
python -m arena.run --bot Splitter "Splitter:x=1" --slots arena/slots/holdout.json --drop-worse --time 1.5 --hard 2.0 --workers 4 --out run.csv
# 3. regenerate the slot files after a big change of the bot (from any multi-bot run)
python tools/informative_slots.py arena/results/<run>.csv --coverage 0.9 --out arena/slots/tuning.json
```

**Caveat:** results on slots describe *contested* games. Absolute win rates for reports come from
the full panel; slots are for deciding whether a change is better.

## 7.9 Lint and type checking

- **Ruff**, with the config in [pyproject.toml](../../pyproject.toml):
  - `target-version = "py38"`, because the CTI machines' Python version is unknown, so we must not use 3.9+/3.10+ syntax;
  - catch-all `except` blocks are allowed only in the never-crash files.
- **Pylance** (VS Code, `standard` type checking, workspace-wide analysis; vendor bots, snapshots and results excluded in `.vscode/settings.json`).
- **Status (2026-10-21): Ruff "All checks passed!"; Pylance 0 errors and 0 warnings in every project file, starter files included.** The only remaining items are greyed "not accessed" hints on interface method stubs and `_`-prefixed loop variables.
