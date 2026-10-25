# 06 · Agent and safety net

**A failure on tournament day caps the grade at 10/20**, and the server treats any illegal move,
empty move or dropped connection as **cheating** (chapter 02). So the bot is built in layers that
each guarantee a legal answer in time.

## 6.1 Tournament client: [main.py](../../main.py)

| Function | Role |
|---|---|
| [`parse_args`](../../main.py#L11) | Server ip and port are the **last two arguments** (the PDF's launch convention), plus optional `--name` and `--delay` |
| [`main`](../../main.py#L95) | Protocol loop: sends NME; builds the board from SET, HUM, HME and MAP; answers every UPD with a MOV; resets the agent on END; exits on BYE |
| [`fallback_moves`](../../main.py#L39) | One legal move (the biggest group to a free neighbour), used if the agent crashes, returns nothing or is too slow. **An empty MOV is never sent** |
| [`Watchdog`](../../main.py#L51) | Runs `compute_moves` in a worker thread and waits at most `SPLITTER_WATCHDOG` (1.8 s) after the UPD. If this turn's search is late, it sends **the search's best plan so far** (`agent.anytime_moves()`: the most visited root plan, refreshed every 32 iterations, or the planner's top plan before the search starts; legality-checked), and only without one the fallback move (campaign 4). While a late worker is still running, the agent is not called again (its state is not thread-safe): the next turn uses the fallback move |

**Changes to the starter version:**
- the default `--delay` is now 0 (0.5 s used a quarter of the time budget);
- `compute_moves` runs under the watchdog (campaign 2): a crash, an empty answer or a late answer all become a legal fallback move. A late answer used to make the server skip our turn, which can desynchronize the protocol;
- the agent is reset on END.

The binary protocol itself is the starter's [network.py](../../network.py) and
[game_state.py](../../game_state.py), unchanged.

## 6.2 [ai_agent.py](../../ai_agent.py)

- **[`AIAgent`](../../ai_agent.py#L22)** is what `main.py` instantiates.
  - It builds a [`SplitterAgent`](../../splitter/agent.py#L49) with `SPLITTER_TIME` seconds per move (default 1.5).
  - **`SPLITTER_MODEL`** chooses the model: `flagship` (default) or `backup` (6.5).
  - `SPLITTER_OPTIONS="key=value,..."` (testing only) adds options to the model, to play a candidate under real conditions (`tools/teammate_matches.py --options`). A malformed entry is skipped; an unknown option is reported and the model is built without the extra options, so a bad value never costs the engine.
  - `SPLITTER_VERBOSE=1` prints the search statistics.
  - [`AIAgent.anytime_moves`](../../ai_agent.py#L74) gives the watchdog the engine's best plan so far.
  - If the `splitter` package cannot even be imported (for example a missing file on the CTI machine), it falls back to the starter strategy.
- **[`AIAgent.compute_moves`](../../ai_agent.py#L63)** calls the Splitter and falls back to [`StarterAgent`](../../ai_agent.py#L105), the original starter-kit logic, on any error.

## 6.3 [splitter/agent.py](../../splitter/agent.py): `SplitterAgent`

**Three interfaces,** so every teammate's tool can run the bot:

| Method | Used by |
|---|---|
| [`compute_moves(game_state)`](../../splitter/agent.py#L101) | `main.py` / `AIAgent`, Dana's self-play |
| [`compute_moves_board(board, species)`](../../splitter/agent.py#L116) | Othmane's and Ronita's arenas |
| [`choose(state, side, ply)`](../../splitter/agent.py#L123) | Our arena (fast path, true ply known) |

**The decision: [`_choose`](../../splitter/agent.py#L194).**

1. **Plies left** = [`_remaining_plies`](../../splitter/agent.py#L147).
   - The server never tells us the ply, so `compute_moves` estimates it as 2 × our turn counter.
   - After 10 plies it also projects the plies left from the game clock (`game_seconds` = 300, i.e. 5 minutes), because the clock can end the game before the 200-ply cap when both bots use most of their 2 s. (In the arena the clock rarely bound, chapter 14.3, stage E.)
2. **Behind?** We are behind if `evaluate(...)` < 0.35, or if in the last 20 plies our material is below theirs ([`material_balance`](../../splitter/evaluate.py#L220)). Only then are gamble plans generated (`gamble="adaptive"`).
3. **Root plans** = [`generate_plans`](../../splitter/planner.py#L381) with **last turn's intents.** Only intents of groups still standing where we left them are kept (commitment, chapter 03).
4. **Search.**
   - `search="greedy"`, or only one plan: play the top plan.
   - Otherwise [`MCTS.search`](../../splitter/mcts.py#L116) with the **remaining budget**: `time_limit` − time already used − 20 ms.
5. **Remember intents.** The chosen plan's intents are stored for next turn.

**The safety net: [`_safe_choose`](../../splitter/agent.py#L157).**

1. Run `_choose` inside try/except.
2. Validate the result with [`check_moves`](../../splitter/rules.py#L91), the server's cheating rules plus bounds and the 255 cap.
3. If invalid or empty: [`fallback_plan`](../../splitter/planner.py#L618), then [`_emergency_move`](../../splitter/agent.py#L246).
4. Convert every value to a plain `int` 5-tuple, ready for `struct.pack`.
5. The reason for any rejection is kept in `last_error` (the tests assert it stays `None`).

**Variants.** Every behaviour is a keyword argument (chapter 10): `splits`, `search`, `gamble`, `c`,
`rollout_depth`, `prior_bias`, `widen_k`, `safety_margin`, `max_detachments`, `reserve_ratio`,
`reserve_radius`, plus any `PlanConfig` field and any evaluation constant as `eval_<name>`
through `**extra`. An unknown option raises `TypeError`, so a misspelt option cannot silently
produce a run identical to the baseline. The arena builds variants from strings like
`"Splitter:splits=0,c=0.8"` (chapter 07).

## 6.4 Time budget

- **Server limit:** 2 s per move, per the PDF (the local server config uses 5 s).
- **Our budget:** 1.5 s, measured from the moment `compute_moves` is called.
- **Measured:**
  - slowest move on the real server: 1.48 s;
  - in the arena with 6 games in parallel: 1.54 s;
  - 0 timeouts in every benchmark.
- **Recommendation:** keep 1.5 s; use `SPLITTER_TIME=1.4` only if the tournament machine is clearly slower. Thinking time is worth a lot at this speed (half the budget costs 25 points, chapter 14.3), and the watchdog now covers an occasional slow move.

## 6.5 The two models: flagship and backup

Both are defined once, in [`MODELS`](../../splitter/agent.py#L37) (splitter/agent.py), and used by
the tournament client (`SPLITTER_MODEL`) and the arena (names `Splitter`, `Splitter-Classic`):

| Model | Options | Tournament command | Why |
|---|---|---|---|
| **flagship** ("Splitter-R3") | `rollout_policy="race", rollout_strike=0.45, rollout_depth_contact=6, leaf_mix=0.5, race_root=True, bait_check=True, strike_p=0.6, desperate_p=0.1` | `python main.py <ip> <port>` | Won campaign 3's pre-registered final on fresh maps (+8.0 ± 3.9); real conditions 9-1-2 with 0 timeouts; decision-for-decision identical to the validated candidate (chapter 16.9) |
| **backup** ("Splitter-Classic") | none (all defaults) | `SPLITTER_MODEL=backup python main.py <ip> <port>` | The campaign-2 flagship, identical to the frozen v7 (300/300 decisions): the most tested model, and it loses differently (more draws, far fewer wipeouts) |

The flagship's slowest move: 1.56 s in its screen, 1.51 s in the final (408 arena games, 0
timeouts) and 1.65 s over the real protocol (12 games). Its race rollouts stop at the search
deadline. In 1,018 campaign-3 games of the whole R family there was one 2.05 s move (by
Splitter-R, while other jobs shared the CPU, chapter 16.5); the watchdog below covers that case.

On Windows PowerShell: `$env:SPLITTER_MODEL = "backup"; python main.py <ip> <port>`.

**Removed after measurement** ([15 · Failed strategies](15_failed_strategies.md)): the retired
runner-up Splitter-HMM (style HMM observing the opponent and adapting the risk settings: −11.9 ±
4.1 at 1.5 s), pre-game analysis (`--pregame`, −4.7), map-aware deathball (−3.9), tree reuse,
endgame moves and the game-clock `tempo` option (−8.3).
