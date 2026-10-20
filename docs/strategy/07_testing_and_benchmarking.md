# 07 · Testing and benchmarking

Every claim in this documentation was checked by one of the tools below. They are also how the
bot was improved: **measure → read the lost games → fix → re-measure on the same seeds**.

## 7.1 Unit and end-to-end tests: [tests/](../../tests)

Run with `python -m unittest discover tests` (standard library only, about 25 s). **34 tests**:

| File | Tests | What they guarantee |
|---|---|---|
| [test_rules.py](../../tests/test_rules.py) | `test_server_formula`, `test_defender_1_5x_is_random_not_sure`, `test_sure_results`, `test_legal_split`, `test_cheats`, `test_byte_overflow_refused`, `test_probe1_split_and_merged_attack`, `test_sure_kill_and_merge`, `test_mean_mode_deterministic` | Our rules = the real server's: formulas, the defender-random rule, each cheating case, and a replay of the live probe game |
| [test_planner.py](../../tests/test_planner.py) | `test_fuzz_all_plans_legal` (500 random positions × 3 configs, more than 1,000 plans, plus `quick_plan` and `fallback_plan`), `test_safe_step_never_walks_into_bigger_humans`, `test_split_generated_for_two_small_houses`, `test_no_split_when_disabled`, `test_detachment_safety`, `test_unsafe_house_not_split_to` | Every generated plan is legal; splits appear when they should and never toward an unsafe house |
| [test_agent.py](../../tests/test_agent.py) | **Puzzles:** `test_takes_the_sure_kill`, `test_does_not_suicide_or_wait_next_to_a_killer`, `test_splits_to_take_two_adjacent_houses`, `test_converges_two_groups_on_a_big_house`. **Safety:** `test_time_budget_big_map`, `test_fuzz_never_illegal`, `test_gamestate_interface` | Correct tactical decisions; the budget is respected; a legal move every time |
| [test_opponent_model.py](../../tests/test_opponent_model.py) | `test_plain_split_conversion`, `test_crossing_sources_are_not_a_split`, `test_long_shot_attack`, `test_tracker_end_to_end`, `test_forward_matches_brute_force`, `test_baum_welch_improves_likelihood`, `test_style_belief_recovers_a_splitter`, `test_goal_recognition_straight_walk`, `test_policy_hmm_identifies_greedy_opponent`, `test_agent_with_model_never_illegal` | Move reconstruction; the HMM maths (forward = brute force, EM improves the likelihood); online inference recovers a known opponent; the agent with the model never plays an illegal move (chapter 11) |
| [test_protocol.py](../../tests/test_protocol.py) | `test_full_game_no_cheat_no_timeout`, `test_small_map_to_the_end` | Two real `main.py` processes play complete games against the fake server: no cheating, no timeout, clean BYE |

## 7.2 Fake server: [tools/fake_server.py](../../tools/fake_server.py)

[`FakeServer`](../../tools/fake_server.py#L51) is a headless copy of the official server.

**What it copies:**
- the **binary protocol** (NME → SET, HUM, HME, MAP; UPD ↔ MOV; END, BYE);
- **player 0 moves first;**
- **UPD contents:** the cells that changed since that player's last UPD;
- **timeouts:** a late reply skips the turn, and leftover bytes are flushed;
- **cheating** (`check_moves`) or a dropped connection ends the game.

[`FakeServer.run`](../../tools/fake_server.py#L81) plays one full game. It works on any OS, so
`main.py` can be tested without the Windows GUI.

Command line: `python tools/fake_server.py --map testmap.xml --port 5555`.

## 7.3 Real server tools

| Tool | Use |
|---|---|
| [tools/restart_server.ps1](../../tools/restart_server.ps1) | Restart the official exe with a chosen map, `MaxPlays` and `MaxPlayDuration`. It rewrites the `.exe.config`; restore it with `git checkout VampiresVSWerewolvesGameServer.exe.config` |
| [tools/probe_server.py](../../tools/probe_server.py) | Scripted probe scenarios (`rules`, `late`, `rule5`, `thr15`, `thr6`, `long`) that established chapter 02 |
| [tools/play_bot.py](../../tools/play_bot.py) | Connect any arena bot (e.g. `Apex`) to a server, to watch Splitter vs a teammate in the GUI |
| [tools/opponent_report.py](../../tools/opponent_report.py) | Opponent-model accuracy per bot on recorded games (chapter 11) |
| [tools/train_opponent_model.py](../../tools/train_opponent_model.py) | Baum-Welch training of the style HMM, with hold-out validation (chapter 11) |

## 7.4 Arena: [arena/](../../arena)

| File | Role |
|---|---|
| [fetch_opponents.py](../../arena/fetch_opponents.py) | [`fetch`](../../arena/fetch_opponents.py#L27) copies the teammates' bots from their git branches (`origin/Othmane`, `origin/Ronita`, `origin/Dana`) into `arena/vendor/` (gitignored). Run `python -m arena.fetch_opponents` (add `--fetch` to `git fetch` first) |
| [opponents.py](../../arena/opponents.py) | [`make_bot(spec, time_limit)`](../../arena/opponents.py#L226) builds any bot behind one interface ([`Bot`](../../arena/opponents.py#L63)). Adapters handle the team's two interfaces ([`GameStateBot`](../../arena/opponents.py#L75), [`BoardBot`](../../arena/opponents.py#L97)), plus [`SplitterBot`](../../arena/opponents.py#L114) and [`SnapshotBot`](../../arena/opponents.py#L215). [`load_vendor`](../../arena/opponents.py#L39) imports a teammate's modules without name clashes. Specs: `Apex`, `RaceMCTS`, `Expecti`, `TacticalSplitter`, `Grabber`, `Rusher`, `Greedy`, `Starter`, `Turtle`, …; `Splitter-nosplit`; `Splitter:key=value,...`; `Snap:v5` |
| [referee.py](../../arena/referee.py) | [`play_game`](../../arena/referee.py#L59): one game with the **server's rules** (it uses `State.apply` and `check_moves`). Illegal or crash → the offender loses; too slow → turn skipped. Records the move log, split turns and decision times |
| [maps.py](../../arena/maps.py) | [`build_suite`](../../arena/maps.py#L138): 14 **tuning** maps in 6 families: `given` (thetrap, testmap), `sym`, `villages` (many small houses), `prize` (big central house), `close` (close starts), `sparse`; plus the **`holdout`** family (8 maps, fresh seeds) that is only used to validate, never to tune (`--maps all` excludes it). All generated maps are point-symmetric ([`symmetric_map`](../../arena/maps.py#L63)), so neither side has a map advantage. [`write_xml`](../../arena/maps.py#L43) exports a map for the real GUI |
| [run.py](../../arena/run.py) | The benchmark command line ([`main`](../../arena/run.py#L155)). Every (opponent, map) pair is played on **both species**, alternating the first player. **Seeds are fixed per game**, so two configurations meet the same dice. `--bot A B C` runs several configurations in **one shared pool**, longest games first, and prints a **paired comparison** of each with the first (`compare`). `--panel fast` = Apex, RaceMCTS, Expecti, TacticalSplitter; `--seed` changes all dice; `--save-all-logs` records full games (ground truth). It reports win rate ± standard error by opponent, map, side and first player ([`report`](../../arena/run.py#L89)), writes a CSV to `arena/results/`, and saves the log of every game not won to `arena/results/logs/<run>/` |
| [replay.py](../../arena/replay.py) | Replay one game verbosely |
| [snapshot.py](../../arena/snapshot.py) | `python -m arena.snapshot v6` freezes `splitter/` as `Snap:v6`, for A/B tests against the next version |

## 7.5 How to run an experiment

```bash
python -m arena.fetch_opponents                                   # once (or after teammates push)
python -m arena.snapshot v6                                       # freeze the current version
# ... change the code ...
# screening: several candidates, ONE pool, paired vs the first (the baseline)
python -m arena.run --bot Snap:v6 "Snap:v6:c=0.4" "Snap:v6:kite=1" --opp RaceMCTS Expecti Snap:v5fix --maps all --games 2 --time 0.1
# validation on data never used for tuning (anti-overfitting)
python -m arena.run --bot Snap:v6 "Snap:v6:kite=1" --opp Apex TacticalSplitter Grabber Greedy Starter Rusher "Snap:v6:splits=0" "Snap:v6:gamble=always,c=0.9" --maps holdout --games 2 --time 0.2
# replication on fresh dice, all 22 maps
python -m arena.run --bot Snap:v6 "Snap:v6:kite=1" --maps given,sym,villages,prize,close,sparse,holdout --games 1 --time 0.2 --seed 7000
```

**Reading the numbers:**
- Differences smaller than about 2 standard errors are noise. 24 games per opponent means about ±10%; 448 games means about ±2%.
- Always confirm a promising change on the full 448-game set: several "improvements" seen on 96 games disappeared there (chapter 08).
- **Validate on the hold-out opponents and maps before adopting anything.** The best tuning result of the campaign (+11.3) vanished there (chapter 12).
- With many candidates, one will look good by luck: replicate on fresh dice (`--seed`).
- Benchmarks run at 0.2 s per move for speed. Validate important changes at the real 1.5 s with `--time 1.5 --hard 2.0`.

## 7.6 Lint and type checking

- **Ruff**, with the config in [pyproject.toml](../../pyproject.toml):
  - `target-version = "py38"`, because the CTI machines' Python version is unknown, so we must not use 3.9+/3.10+ syntax;
  - catch-all `except` blocks are allowed only in the never-crash files.
- **Pylance** (VS Code, `standard` type checking, workspace-wide analysis).
- **Status (2026-10-19): 0 findings in our code.** The remaining findings are only in the untouched starter files `game_engine.py`, `game_state.py`, `network.py` and `connect.py`.
