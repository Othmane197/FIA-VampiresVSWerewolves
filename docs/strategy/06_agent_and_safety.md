# 06 · Agent and safety net

**A failure on tournament day caps the grade at 10/20**, and the server treats any illegal move,
empty move or dropped connection as **cheating** (chapter 02). So the bot is built in layers that
each guarantee a legal answer in time.

## 6.1 Tournament client: [main.py](../../main.py)

| Function | Role |
|---|---|
| [`parse_args`](../../main.py#L9) | Server ip and port are the **last two arguments** (the PDF's launch convention), plus optional `--name` and `--delay` |
| [`main`](../../main.py#L53) | Protocol loop: sends NME; builds the board from SET, HUM, HME and MAP; answers every UPD with a MOV; resets the agent on END; exits on BYE |
| [`fallback_moves`](../../main.py#L41) | One legal move (the biggest group to a free neighbour), used if the agent crashes or returns nothing. **An empty MOV is never sent** |

**Changes to the starter version:**
- the default `--delay` is now 0 (0.5 s used a quarter of the time budget);
- `compute_moves` is wrapped in try/except;
- the agent is reset on END.

The binary protocol itself is the starter's [network.py](../../network.py) and
[game_state.py](../../game_state.py), unchanged.

## 6.2 [ai_agent.py](../../ai_agent.py)

- **[`AIAgent`](../../ai_agent.py#L22)** is what `main.py` instantiates.
  - It builds a [`SplitterAgent`](../../splitter/agent.py#L35) with `SPLITTER_TIME` seconds per move (default 1.5).
  - `SPLITTER_VERBOSE=1` prints the search statistics.
  - If the `splitter` package cannot even be imported (for example a missing file on the CTI machine), it falls back to the starter strategy.
- **[`AIAgent.compute_moves`](../../ai_agent.py#L58)** calls the Splitter and falls back to [`StarterAgent`](../../ai_agent.py#L70), the original starter-kit logic, on any error.

## 6.3 [splitter/agent.py](../../splitter/agent.py): `SplitterAgent`

**Three interfaces,** so every teammate's tool can run the bot:

| Method | Used by |
|---|---|
| [`compute_moves(game_state)`](../../splitter/agent.py#L87) | `main.py` / `AIAgent`, Dana's self-play |
| [`compute_moves_board(board, species)`](../../splitter/agent.py#L102) | Othmane's and Ronita's arenas |
| [`choose(state, side, ply)`](../../splitter/agent.py#L109) | Our arena (fast path, true ply known) |

**The decision: [`_choose`](../../splitter/agent.py#L169).**

1. **Plies left** = [`_remaining_plies`](../../splitter/agent.py#L116).
   - The server never tells us the ply, so `compute_moves` estimates it as 2 × our turn counter.
   - After 10 plies it also projects the plies left from the game clock (`game_seconds` = 300, i.e. 5 minutes), because the clock usually ends the game before the 200-ply cap.
2. **Behind?** We are behind if `evaluate(...)` < 0.35, or if in the last 20 plies our material is below theirs ([`material_balance`](../../splitter/evaluate.py#L205)). Only then are gamble plans generated (`gamble="adaptive"`).
3. **Root plans** = [`generate_plans`](../../splitter/planner.py#L343) with **last turn's intents.** Only intents of groups still standing where we left them are kept (commitment, chapter 03).
4. **Search.**
   - `search="greedy"`, or only one plan: play the top plan.
   - Otherwise [`MCTS.search`](../../splitter/mcts.py#L122) with the **remaining budget**: `time_limit` − time already used − 20 ms.
5. **Remember intents.** The chosen plan's intents are stored for next turn.

**The safety net: [`_safe_choose`](../../splitter/agent.py#L126).**

1. Run `_choose` inside try/except.
2. Validate the result with [`check_moves`](../../splitter/rules.py#L91), the server's cheating rules plus bounds and the 255 cap.
3. If invalid or empty: [`fallback_plan`](../../splitter/planner.py#L636), then [`_emergency_move`](../../splitter/agent.py#L268).
4. Convert every value to a plain `int` 5-tuple, ready for `struct.pack`.
5. The reason for any rejection is kept in `last_error` (the tests assert it stays `None`).

**Variants.** Every behaviour is a keyword argument (chapter 10): `splits`, `search`, `gamble`, `c`,
`rollout_depth`, `safety_margin`, `max_detachments`, `reserve_ratio`, `reserve_radius`,
`light_tree`, plus any `PlanConfig` field through `**extra`. The arena builds variants from
strings like `"Splitter:splits=0,c=0.8"` (chapter 07).

## 6.4 Time budget

- **Server limit:** 2 s per move, per the PDF (the local server config uses 5 s).
- **Our budget:** 1.5 s, measured from the moment `compute_moves` is called.
- **Measured:**
  - slowest move on the real server: 1.48 s;
  - in the arena with 6 games in parallel: 1.54 s;
  - 0 timeouts in every benchmark.
- **Recommendation:** run with `SPLITTER_TIME=1.4` on tournament day for extra margin on an unknown machine.

## 6.5 Opponent model, adaptive settings and pre-game (chapters 11 and 12)

- **`SplitterAgent(opponent_model=True, ...)`** builds an `OpponentModel`.
  - [`_safe_choose`](../../splitter/agent.py#L126) calls `opp_model.observe(state)` before deciding (it learns from the opponent's last move) and `note_our_move` after.
  - Both are wrapped in try/except, so the model can never break a turn.
- **`adapt=True`** makes [`_adapt_settings`](../../splitter/agent.py#L233) adjust `reserve_radius`, `safety_margin` and `hunt_bonus` each turn from the measured aggression, long-shot rate and split rate (after 8 observed turns).
- **`pregame(game_state)`** ([`SplitterAgent.pregame`](../../splitter/agent.py#L215)) is called by `main.py` on MAP only with `--pregame`. It decides the first move during the idle time before the game, and the cached move is used if our first board matches.
  - A longer first move measured −4.7 points, so the flag stays off.
- **`map_aware=True`** plays without splits on maps dominated by one prize ([`prize_dominated`](../../splitter/agent.py#L256)): −3.9 points, rejected.
