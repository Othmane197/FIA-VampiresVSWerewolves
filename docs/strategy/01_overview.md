# 01 · Overview

## 1.1 The problem

Vampires vs Werewolves ([Projectv10.pdf](../../Projectv10.pdf)) is a two-player, turn-based game
on an n × m grid.

- Each species starts as one group. Human houses are scattered over the board.
- On its turn, a player moves any number of its groups one cell in any of the 8 directions. A group can also be split: part of it moves and the rest stays, or the parts go to different cells.
- **Converting humans** needs at least as many creatures as there are humans in the house. The converted humans join our species.
- **Killing an enemy group for sure** needs 1.5× its size. Every other fight is a random battle.
- The game ends when a species disappears or the time or ply limit is reached. The bigger species wins.
- We have **2 seconds per move**, and an illegal move ends the game (chapter 02).

The PDF asks that the AI "take into account the opponent's moves and not be a reflex agent." It
also forbids libraries that implement AI, trees or graphs. Everything here is plain Python
standard library.

## 1.2 The idea: "The Splitter"

Most bots, including Othmane's Apex alpha-beta and the starter kit, keep **one big group** (a
"deathball") and walk it from house to house. That is safe but slow: one group collects one house
at a time.

**The Splitter grows faster by collecting several houses at once:**

- From a big group it sends **detachments of exactly h creatures** to houses of h humans. A detachment of h converts a house of h for sure, and comes back with 2h creatures.
- The **main body keeps the rest** and stays big enough to be safe.

There are two dangers, and the design answers both:

| Danger | Answer | Where |
|---|---|---|
| Small groups get picked off (3 dies to 5) | Every detachment must pass a **safety check**: no enemy can catch it on the way or right after it converts. The main body must stay bigger than nearby enemies. | [`detachment_safe`](../../splitter/planner.py#L112), [`_split_orders`](../../splitter/planner.py#L456) |
| Splitting explodes the number of possible moves | We do not search raw moves. Each turn the planner proposes **about 15 joint plans** (macro-actions), and MCTS searches over those. | [`generate_plans`](../../splitter/planner.py#L338), [`MCTS.search`](../../splitter/mcts.py#L97) |

The idea was tested, not assumed. The same bot with splitting switched off wins 74% of its games
instead of 79%, with half the material margin (chapter 08).

## 1.3 Architecture

```
main.py  (protocol loop: NME, SET/HUM/HME/MAP, then UPD -> MOV; watchdog: fallback move at 1.8 s)
  └─ ai_agent.AIAgent                     tournament entry point, starter strategy as last resort
       └─ splitter/agent.py  SplitterAgent    time budget, intents memory, fallbacks, final legality check
            ├─ splitter/planner.py  generate_plans   joint plans = macro-actions (chapter 03)
            ├─ splitter/mcts.py     MCTS.search      open-loop UCT over plans    (chapter 05)
            ├─ splitter/evaluate.py evaluate         P(win) of a position        (chapter 04)
            └─ splitter/state.py + rules.py          exact server rules          (chapter 02)

arena/   benchmarking: maps, opponents (in-repo, external and randomized-style bots), referee,
         runner (informative slots, early stopping, resume), stored history     (chapter 07)
tools/   fake server, server matches between any two programs, real-server probes, evaluation
         fitting, informative-slot selection, doc index generator               (chapter 07)
tests/   39 unit, end-to-end and tooling tests
```

| Package / file | Role |
|---|---|
| [main.py](../../main.py) | Network loop of the tournament client (starter kit, made crash-proof) |
| [network.py](../../network.py), [game_state.py](../../game_state.py) | Binary protocol and the board kept from server messages (starter kit, unchanged) |
| [ai_agent.py](../../ai_agent.py) | `AIAgent` (what `main.py` plays) delegates to the Splitter |
| [splitter/](../../splitter) | The AI (this documentation) |
| [arena/](../../arena), [tools/](../../tools), [tests/](../../tests) | Verification and benchmarking (chapter 07) |

## 1.4 The two kept models

Two improvement campaigns (chapters 12 and 14) tested about 40 ideas. The code keeps exactly two
configurations, defined once in `MODELS` ([splitter/agent.py](../../splitter/agent.py)); every
other idea was measured, documented ([15 · Failed strategies](15_failed_strategies.md)) and
deleted from the code.

| Name (arena spec) | Construction | Status |
|---|---|---|
| **Splitter** (flagship) | `SplitterAgent()`, what `main.py` plays | Best measured: 79.3% vs the 9-opponent panel at 0.2 s, **78.7% at the tournament's 1.5 s**, 61.6% head-to-head vs v5 |
| **Splitter-Calibrated** (backup) | `SplitterAgent(eval_discount=0.845, eval_k0=8.5, eval_k1=27)`; `SPLITTER_MODEL=backup` | The same bot with its evaluation fitted on game outcomes: +5.9 ± 4.4 on unseen data at 0.25 s, +1.3 ± 6.1 at 1.5 s (statistically equal) |

At 1.5 s: flagship ≈ backup > the retired opponent-model variant (−11.9 ± 4.1) > the deathball
(no splits, −18.5 ± 7.0). The flagship is the tournament bot.

## 1.5 What happens in one turn

1. **[`main.main`](../../main.py#L89)** receives `UPD` and updates the `GameState` through `game_state.GameState.apply_updates`. It then calls `agent.compute_moves(state)`, wrapped in try/except with [`fallback_moves`](../../main.py#L39).
2. **[`AIAgent.compute_moves`](../../ai_agent.py#L53)** calls the Splitter, and falls back to [`StarterAgent`](../../ai_agent.py#L65) if the Splitter fails.
3. **[`SplitterAgent.compute_moves`](../../splitter/agent.py#L82)** converts the board with [`State.from_game_state`](../../splitter/state.py#L156) and estimates the ply from its own turn counter. It then calls [`_safe_choose`](../../splitter/agent.py#L123).
4. **[`SplitterAgent._choose`](../../splitter/agent.py#L150)**:
   1. estimates the plies left ([`_remaining_plies`](../../splitter/agent.py#L113), from the ply cap and the game clock);
   2. evaluates the position ([`evaluate`](../../splitter/evaluate.py#L169)) to decide whether we are *behind*, which allows gambles;
   3. generates the root plans with [`generate_plans`](../../splitter/planner.py#L338), passing last turn's *intents* (commitment);
   4. runs [`MCTS.search`](../../splitter/mcts.py#L97) until the time budget (1.5 s by default) is spent.
5. **Each MCTS iteration ([`_iterate`](../../splitter/mcts.py#L122))**:
   1. replays plans from the root with sampled dice ([`State.apply`](../../splitter/state.py#L96));
   2. expands a new plan, whose children come from the same planner for both sides;
   3. rolls out 2 greedy plies ([`quick_plan`](../../splitter/planner.py#L582));
   4. scores the leaf with [`evaluate`](../../splitter/evaluate.py#L169) and backs up the result.
6. **The most visited root plan is played.** Its intents (where each group is heading) are remembered for next turn.
7. **[`_safe_choose`](../../splitter/agent.py#L123) checks the moves** with [`check_moves`](../../splitter/rules.py#L91), the server's own cheating rules. If they fail it uses [`fallback_plan`](../../splitter/planner.py#L562), and then [`_emergency_move`](../../splitter/agent.py#L184).
8. **`main.py` sends the `MOV`.**
