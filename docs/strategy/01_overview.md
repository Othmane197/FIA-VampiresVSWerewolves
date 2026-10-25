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
| Small groups get picked off (3 dies to 5) | Every detachment must pass a **safety check**: no enemy can catch it on the way or right after it converts. The main body must stay bigger than nearby enemies. | [`detachment_safe`](../../splitter/planner.py#L134), [`_split_orders`](../../splitter/planner.py#L494) |
| Splitting explodes the number of possible moves | We do not search raw moves. Each turn the planner proposes **about 15 joint plans** (macro-actions), and MCTS searches over those. | [`generate_plans`](../../splitter/planner.py#L363), [`MCTS.search`](../../splitter/mcts.py#L116) |

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

Three improvement campaigns (chapters 12, 14 and 16) tested about 50 ideas. The code keeps exactly
two configurations, defined once in `MODELS` ([splitter/agent.py](../../splitter/agent.py)); every
other idea was measured and documented ([15 · Failed strategies](15_failed_strategies.md)).

| Name (arena spec) | Construction | Status |
|---|---|---|
| **Splitter** (flagship, "Splitter-R3") | `SplitterAgent(**MODELS["flagship"])`, what `main.py` plays | The campaign-2 flagship merged with RaceMCTS's long dice-driven rollouts and root plans, the anti-bait check, good-odds first strikes and the desperate-opponent model (chapter 16). Pre-registered final on fresh maps and never-used styles: **72.9%, +8.0 ± 3.9 over the backup**; real conditions vs the live teammate bots 9-1-2, 0 timeouts |
| **Splitter-Classic** (backup) | `SplitterAgent()` (all defaults); `SPLITTER_MODEL=backup` | The campaign-2 flagship (= the frozen v7): 64.9% in the same final; the most tested model, and it loses differently (more draws, far fewer wipeouts) |

Retired in campaign 3: "Splitter-Calibrated" (the campaign-2 backup: 0.0 ± 3.1 against the
Classic on fresh maps). The section below describes one turn of the shared machinery; the
flagship's extra options are listed in [10.4b](10_parameters.md).

## 1.5 What happens in one turn

1. **[`main.main`](../../main.py#L89)** receives `UPD` and updates the `GameState` through `game_state.GameState.apply_updates`. It then calls `agent.compute_moves(state)`, wrapped in try/except with [`fallback_moves`](../../main.py#L39).
2. **[`AIAgent.compute_moves`](../../ai_agent.py#L54)** calls the Splitter, and falls back to [`StarterAgent`](../../ai_agent.py#L66) if the Splitter fails.
3. **[`SplitterAgent.compute_moves`](../../splitter/agent.py#L96)** converts the board with [`State.from_game_state`](../../splitter/state.py#L156) and estimates the ply from its own turn counter. It then calls [`_safe_choose`](../../splitter/agent.py#L137).
4. **[`SplitterAgent._choose`](../../splitter/agent.py#L164)**:
   1. estimates the plies left ([`_remaining_plies`](../../splitter/agent.py#L127), from the ply cap and the game clock);
   2. evaluates the position ([`evaluate`](../../splitter/evaluate.py#L171)) to decide whether we are *behind*, which allows gambles;
   3. generates the root plans with [`generate_plans`](../../splitter/planner.py#L363), passing last turn's *intents* (commitment);
   4. runs [`MCTS.search`](../../splitter/mcts.py#L116) until the time budget (1.5 s by default) is spent.
5. **Each MCTS iteration ([`_iterate`](../../splitter/mcts.py#L157))**:
   1. replays plans from the root with sampled dice ([`State.apply`](../../splitter/state.py#L96));
   2. expands a new plan, whose children come from the same planner for both sides;
   3. rolls out 2 greedy plies ([`quick_plan`](../../splitter/planner.py#L620));
   4. scores the leaf with [`evaluate`](../../splitter/evaluate.py#L171) and backs up the result.
6. **The most visited root plan is played.** Its intents (where each group is heading) are remembered for next turn.
7. **[`_safe_choose`](../../splitter/agent.py#L137) checks the moves** with [`check_moves`](../../splitter/rules.py#L91), the server's own cheating rules. If they fail it uses [`fallback_plan`](../../splitter/planner.py#L600), and then [`_emergency_move`](../../splitter/agent.py#L214).
8. **`main.py` sends the `MOV`.**
