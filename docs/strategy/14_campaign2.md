# 14 · Campaign 2: exploring the future-improvement ideas

**Goal:** implement the ideas of chapter 13 (and new ones), measure each against the flagship,
validate the promising ones at tournament speed on unseen data, and keep only what reliably helps.

**Baseline:** the flagship "Splitter" (= `Snap:v7`), 78.7% ± 5.6 at 1.5 s against RaceMCTS,
Expecti and Apex (chapter 08.2).

**Lessons carried over from campaign 1 (chapter 12):**
1. Tuning-set gains of +7 to +11 vanished on unseen data, so every candidate is validated on hold-out maps and opponents.
2. The runner-up was neutral at 0.2 s but −14.8 at 1.5 s, so **the final validation is at the tournament's 1.5 s**.
3. A new, third validation set: **`Styled:<n>` opponents** (14.1).

## 14.1 New testing infrastructure

| Tool | What it does | Where |
|---|---|---|
| `Styled:<n>` opponents, `--panel styled` | Reproducible random opponent *styles*: gamble policy, caution, reserve, split rate, search or greedy. They share our planner, so they are not independent of our bot, but none of them plays like a teammate's bot | [`styled_config`](../../arena/opponents.py#L244) |
| Game clock, `--game-seconds` | The server's `MaxGameDuration` in the referee: the game ends when both bots' thinking time adds up to it | [`play_game`](../../arena/referee.py#L59) |
| Evaluation fitting | Texel-style tuning of the evaluation constants on recorded games, with a check set and a calibration table | [tools/tune_eval.py](../../tools/tune_eval.py) |
| Keep-awake | The benchmark asks Windows not to sleep while it runs. Campaign 2's first screen was hit by two overnight sleeps (moves "lasting" 6,400 s and 44,800 s); those game keys were excluded from the paired comparison | [`keep_awake`](../../arena/run.py#L245) |

## 14.2 The candidates and how each was implemented

During the campaign, all candidates were options of `SplitterAgent` / `PlanConfig`, off by
default, run as `"Splitter:<option>=<value>"` in one shared pool. *Root only* = used only for our
root plans (a `ROOT_ONLY` list in the agent), because it is too slow for every tree node.

**After the campaign, all of this code was removed from `splitter/`** (14.4). It is kept in the
local, gitignored archive snapshot `arena/snapshots/splitter_c2/`, where every option still works
as `"Snap:c2:<option>=<value>"` (for example `"Snap:c2:reuse=1,plan_cache=1"`, the first re-test
candidate of chapter 13.1).

### Decision making and search ([splitter/mcts.py](../../splitter/mcts.py))

| Option | Idea | Implementation |
|---|---|---|
| `reuse=1` | **Tree reuse between turns** | After our move and the opponent's reply, `MCTS.subtree_after` finds the child for our played plan, then its child whose moves equal the opponent's reconstructed reply (`OpponentTracker`, chapter 11.2). `MCTS._make_root` keeps the statistics of the root plans that are generated again today and adds the new ones. The tree is open-loop, so its statistics carry over without re-simulation. **Hit rate:** 49% of turns against RaceMCTS, 35% against our own bot, 15–17% against Apex and Expecti |
| `root_policy=sh` | **Sequential halving at the root** | `MCTS._sequential_halving`: log2(n) rounds of equal time; within a round the surviving root plans are searched round-robin, then the worse half is dropped; the best mean wins |
| `risk_lambda=0.5` | **Risk-aware final choice** | Nodes also sum squared rewards. When the best plan's mean is ≥ 0.6, `MCTS._final_choice` picks, among plans with ≥ 30% of the top visits, the best mean − λ·std |
| `rollout_policy=plan` | Smarter rollouts | Rollout moves = the planner's top plan instead of `quick_plan` |
| `opp_max_plans=18` | Wider opponent model | 18 opponent plans per node instead of 12 |
| `endgame_moves=1` | **Endgame moves** | With no humans left and ≤ 3 groups, every whole-group step in each direction is added to the root plans (`_endgame_plans`), so the search can manoeuvre exactly |
| `tempo=0.3` | **The game clock as a resource** | When behind and the clock (not the ply cap) will end the game, think only 30% of the budget, to get more plies (14.4) |

### Caching

| Option | Implementation | Measured |
|---|---|---|
| `plan_cache=1` | **Transposition cache** inside one search: `generate_plans` results keyed by (position, side, behind) and `evaluate` results keyed by (position, side to move, plies left) ([`MCTS._plans`](../../splitter/mcts.py#L81), `MCTS._evaluate`) | Positions repeat a lot when there are few groups: 93% of plan generations on thetrap and 62% on prize_11x17 were repeats, 0% on vil_13x21. In real games: 124–207 cache hits per decision at 0.25 s |

The profile of a 1.5 s decision (vil_13x21, 8 groups) shows where the time goes: plan generation
50%, rollouts 22%, evaluation 14%, legality checks 14%.

### Path planning and swarm orchestration ([splitter/planner.py](../../splitter/planner.py))

| Option | Idea | Implementation |
|---|---|---|
| `corridors=1` (root only) | **Safe corridors** | When the straight path is refused, `safe_corridor` searches (cell, time) breadth-first for a path where no enemy ≥ k can be adjacent at any step, ending with detachment_safe's arrival rules, within d + 2 moves. The detachment's first step is imposed through `Goal.via` |
| `split_dp=1` (root only) | **Exact detachment selection** | `_best_detachment_set`: the subset of the 8 best options (≤ `max_detachments`, sum of sizes ≤ creatures available) with the most discounted humans, added as one more split plan |
| `tour_bonus=0.5` | **House tours** | A split option's value also counts the best next house that the converted detachment (k + h) could take |
| `intercept=1` | **Interception** | A kill goal more than 2 moves away aims at the first step of the enemy's path to its best house (`_intercept_cell`) instead of its current cell |
| `pincer_kill=1` | **Pincer kills** | `_pincer_kill_orders`: our groups adjacent to an enemy group, each too small, but together ≥ 1.5×, enter it on the same turn (arrivals are summed) |
| `covered=1` | **Retaliation-aware safety** | `detachment_safe(..., cover=)`: a threat met while the detachment is still next to the main body is ignored when the main body kills the attacker for sure afterwards |
| `group_cap=5` | **Group-count control** | No new splits once we have 5 groups |

**Corridors, an analytical note.** At first it looked as if corridors could never help: if a
path cell c_t is within t of an enemy, the triangle inequality bounds the enemy's distance to the
target by d. But in the king metric a cell has many *different* shortest paths, and the straight
path (diagonal first) is only one of them; corridors find another one of the same length. On
random positions, a corridor exists for 1.7% of refused detachments (863 of 52,097), so the
option rarely changes anything.

### Prediction and evaluation ([splitter/evaluate.py](../../splitter/evaluate.py))

| Option | Idea | Implementation |
|---|---|---|
| `eval_coin_weight=0.5` | **Soft opponent model** (chapter 13.6.1, without the HMM) | Adjacent threats at 30–50% odds count half: the average of a careful and a gambling opponent |
| `eval_*` | **Evaluation tuning on outcomes** | All constants of the evaluation are now an [`EvalParams`](../../splitter/evaluate.py#L29) object: `discount`, sigmoid `k0` and `k1`, `contest_half`, `coin_weight`, `dom_bonus`. [tools/tune_eval.py](../../tools/tune_eval.py) fits them by coordinate descent on the log-loss of game results (14.3) |
| `danger_strike_p=0.3` | Re-test of the campaign-1 screening winner | `safe_step` treats adjacent enemies as threats from 30% odds |

### Robustness ([main.py](../../main.py))

**Watchdog** ([`Watchdog`](../../main.py#L51)). `compute_moves` runs in a worker thread; `main.py`
waits at most `SPLITTER_WATCHDOG` (1.8 s) after the UPD, then sends the fallback move. While a
late worker is still running, the agent is not called again (its state is not thread-safe), and
the fallback is used. Test: `test_watchdog_sends_the_fallback_when_late`. On by default: it does
not change any decision made in time, it only replaces a late answer (a skipped turn, which can
desynchronize the protocol) by a legal one.

### Ideas not implemented, and why

| Idea | Reason |
|---|---|
| BFS paths around obstacles | Maps have no walls; `safe_step` already steps around houses it cannot take. Little to gain |
| Planned rendezvous | Two merging groups already walk towards each other (both have the other as `merge` goal), so they meet halfway |
| Screening (main body between enemy and detachments) | Needs a model of where the threat will move; the closest measured relative, the predicted *shield* plans, lost 3.9 points |
| Opening preparation | Only valid for known maps; the tournament maps are unknown, and a longer first move measured −4.7 |
| SPSA / SPRT, Elo ladder | Testing tools rather than playing strength; the paired shared-pool design and `arena.history` cover the need for now |

## 14.3 Results

### Stage A: screening (tuning maps, 0.25 s, 136 paired games per candidate)

Opponents: RaceMCTS, Expecti, Apex, TacticalSplitter and the frozen flagship `Snap:v7`, on the
14 tuning maps, both species. Paired difference with the flagship on the same games (4 game keys
excluded because of the overnight sleeps).

| Candidate | Δ vs flagship |
|---|---|
| interception (`intercept=1`) | +2.6 ± 3.4 |
| group cap 5 | +2.6 ± 3.2 |
| exact detachment selection (`split_dp=1`) | +2.2 ± 2.7 |
| tree reuse + transposition cache | +1.8 ± 3.4 |
| risk-aware final choice (λ = 0.5) | +1.1 ± 3.8 |
| transposition cache alone | +0.7 ± 2.4 |
| covered detachments; 18 opponent plans | +0.4 |
| tree reuse alone | +0.0 ± 3.1 |
| sequential halving | −0.4 ± 3.8 |
| pincer kills | −0.7 ± 3.3 |
| corridors | −1.1 ± 3.2 |
| coin-flip threats at half weight; `danger_strike_p=0.3` | −2.2 |
| house tours (0.5); endgame moves | −3.7 |
| planner rollouts | **−5.9 ± 3.4** |

**Reading:** no candidate is distinguishable from the flagship (all within about 1 standard
error, except planner rollouts: a rollout that costs a full plan generation leaves too few
iterations). The flagship is already at a local optimum for these ideas at this sample size.

### Evaluation fitting

`python tools/tune_eval.py --train <224 old + 224 new tuning-map games> --check <128 hold-out games>`
(the 224 older games, from 2026-10-19, were deleted in the results clean-up; the 224 newer ones
are `arena/results/traces/20261020-171040_Splitter`, the hold-out ones `traces/20261020-170854_Splitter`):
14,725 training positions, 4,524 check positions.

| | Train log-loss | Check log-loss (hold-out maps) |
|---|---|---|
| Current evaluation | 0.399 | 0.387 |
| Fitted | 0.364 | **0.351** (−9%) |

Fitted constants: discount 0.93 → 0.845; steepness k = 6 + 14·progress → 8.5 + 27·progress;
contested captures count fully (`contest_half` 0.5 → 1.0); coin-flip exposure dropped
(`coin_weight` 1 → 0); no domination bonus.

**Calibration (hold-out positions), predicted → observed win rate:**

| Predicted | 0.03 | 0.15 | 0.25 | 0.35 | 0.46 | 0.51 | **0.65** | **0.75** | 0.85 | 0.97 |
|---|---|---|---|---|---|---|---|---|---|---|
| Current | 0.06 | 0.15 | 0.23 | 0.28 | 0.46 | 0.54 | **0.92** | **0.93** | 0.91 | 0.98 |
| Fitted | 0.05 | 0.14 | 0.22 | 0.38 | 0.49 | 0.51 | 0.78 | 0.92 | 0.91 | 0.97 |

The current evaluation is **under-confident about leads**: positions it rates 0.65–0.75 are won
92–93% of the time. The fit corrects most of it.

**Caveat:** a better predictor is not automatically a better guide for the search. The games were
played by a bot that avoids coin-flip exposure, so the data cannot show what happens without
that term (selection bias). Both the full fit and a calibration-only fit (steepness and discount
only) are tested in games (stage B).

### Stage B: replication on unseen data (hold-out maps, 0.25 s, 144 paired games per candidate)

Opponents: RaceMCTS, Expecti, Apex and `Styled:1`–`Styled:6`, on the 8 hold-out maps (none of
them used in stage A or in the evaluation fit), both species, seed 5100.

| Candidate | Stage A (tuning) | **Stage B (unseen)** |
|---|---|---|
| exact detachment selection | +2.2 ± 2.7 | −1.7 ± 3.8 |
| group cap 5 | +2.6 ± 3.2 | −2.8 ± 3.8 |
| interception | +2.6 ± 3.4 | −3.5 ± 4.3 |
| tree reuse + transposition cache | +1.8 ± 3.4 | −3.5 ± 4.3 |
| all five together (bundle) | — | −4.5 ± 4.1 |
| evaluation fit, all constants | — | −2.4 ± 4.0 |
| **evaluation fit, calibration only** (`eval_discount=0.845,eval_k0=8.5,eval_k1=27`) | — | **+5.9 ± 4.4** |

**Every stage-A winner changed sign on unseen data**, as campaign 1 predicted: they were noise.
Combining them did not help either (−4.5).

**The evaluation fit splits in two:**
- **Calibration only** (sharper sigmoid, stronger distance discount; risk terms unchanged): +5.9. By opponent: Expecti +18.8, Styled:2 and Styled:3 +21.9, Apex and RaceMCTS 0, Styled:6 −12.5 (16 games each).
- **All constants** (also drops the coin-flip exposure and the contest discount): −2.4. This confirms the selection-bias caveat: the risk terms do not improve *prediction* on games where the bot avoids risk, but they are what makes it avoid risk.

**Why the calibrated evaluation could help.** The current sigmoid is too flat for clear leads
(positions at 0.65–0.75 are won 92%). A flat evaluation makes the search value a sure, moderate
lead almost like a coin flip, so it can drift into risky plans when ahead. A sharper one makes
it protect clear leads, and the stronger discount makes it prefer nearer gains.

### Stage C: tournament speed (1.5 s, hold-out slots, 48 paired games)

`--slots arena/slots/holdout.json --drop-worse --time 1.5 --hard 2.0 --workers 4 --seed 6100`,
against RaceMCTS, Expecti, Apex and `Styled:1`–`Styled:3`: 44 minutes instead of more than
3 hours for the full panel (chapter 07.8).

| Candidate | Δ vs flagship at 1.5 s |
|---|---|
| calibrated evaluation | +5.2 ± 8.5 (RaceMCTS +10, Styled:3 +17.9, Expecti −16.7, Styled:1 −12.5) |
| half the thinking time (`time_limit=0.75`) | **−25.0 ± 10.9**, dropped after round 2 |

- **Calibrated evaluation:** same direction and size as stage B. Pooled with stage B (inverse-variance): **+5.8 ± 3.9**, 1.5 standard errors. Promising, not conclusive.
- **Thinking time matters a lot at 1.5 s:** half the time costs 25 points. The 1.5 s budget is well used.

### Stage D: pre-registered verification (written before the run)

**Run:** the flagship, the calibrated evaluation and the runner-up Splitter-HMM, at 1.5 s, on the
hold-out slots with **fresh dice** (`--seed 7100`), against RaceMCTS, Expecti, Apex and
**`Styled:4`–`Styled:6`** (not used in stage C).

**Decision rule, fixed in advance:**
1. The calibrated evaluation becomes the flagship if its stage-D difference is positive **and** the pooled difference over stages B, C and D is above 2 standard errors. The previous flagship (v7 defaults) then becomes the backup.
2. Otherwise the v7 flagship stays. The backup is whichever of the calibrated evaluation and Splitter-HMM has the higher pooled difference at 1.5 s.

**Result** (52 paired games, 1.5 s, 62 minutes):

| Candidate | Stage D | Pooled at 1.5 s |
|---|---|---|
| calibrated evaluation | −2.9 ± 8.9 | **+1.3 ± 6.1** (stages C, D); +4.3 ± 3.6 with stage B (0.25 s) |
| Splitter-HMM (campaign-1 runner-up) | −4.8 ± 7.7 | **−11.9 ± 4.1** (with the 54-game run of chapter 08.2) |

**Decision (by the rule above):**
1. Stage D is negative, so **the v7 flagship stays the flagship.**
2. Backup: the calibrated evaluation (+1.3 ± 6.1, statistically equal to the flagship) is far ahead of Splitter-HMM (−11.9 ± 4.1, about 3 standard errors worse). **The calibrated evaluation becomes the backup; Splitter-HMM is retired and its code removed.**

### Stage E: the game clock as a resource (`tempo`)

Flagship vs the same bot with `tempo=0.3` (think 30% of the budget when behind on a clock-limited
game), both told about the clock, with a 50 s game clock at 0.3 s per move (`--game-seconds 50`),
tuning slots, 60 paired games: **−8.3 ± 6.9** (RaceMCTS −27.8).

The clock **never ended a game** (73 wipe-outs, 47 at the ply cap): search bots do not always use
their full time, so a game clock rarely binds. On the real server, 300 s at 1.5 s per move is about
100 moves each, the same as the 200-ply cap. With the clock not binding, `tempo` only meant thinking
less when behind, which stage C showed is expensive. **Rejected.**

## 14.4 Verification of the kept models

| Check | Result |
|---|---|
| **Decision-level identity.** With a fake clock (+1 ms per call, so both searches run exactly the same iterations) and the same seed, the cleaned flagship and the frozen `Snap:v7` chose moves for 300 random positions | **300 / 300 identical decisions** |
| Same check for the backup | 244 / 300 identical; the 56 differences come only from its calibrated evaluation |
| The planner after clean-up vs `Snap:v7` | byte-for-byte identical |
| Unit, end-to-end and tooling tests | 37 tests pass (`python -m unittest discover tests`) |
| `SPLITTER_MODEL=backup` really plays the backup through `main.py` / `AIAgent` | `test_tournament_client_selects_the_model` |

**The two kept models** (defined once, in `MODELS` in [splitter/agent.py](../../splitter/agent.py)):

| Role | Arena name | Construction | Tournament |
|---|---|---|---|
| **Flagship** | `Splitter` | `SplitterAgent()` (v7 defaults) | `python main.py <ip> <port>` |
| **Backup** | `Splitter-Calibrated` | `SplitterAgent(eval_discount=0.845, eval_k0=8.5, eval_k1=27)` | `SPLITTER_MODEL=backup python main.py <ip> <port>` |

## 14.5 What campaign 2 taught us

1. **The flagship is at a robust local optimum.** Seventeen independent ideas, from search algorithms to path planning, all landed within noise of it, and the best of them changed sign on unseen data.
2. **Selection on a screen is noise-chasing at this sample size.** The top three of 17 at +2.2 to +2.6 were the expected maximum of 17 noisy zero-effect estimates (about +1.5 SE). Replicating on unseen data is not optional.
3. **The evaluation is the most promising lever.** It is the only idea with a mechanism (measured under-confidence, a 9% better log-loss on hold-out games) and a consistently positive sign at 0.25 s. It did not prove itself at 1.5 s, which makes it a good backup and the first thing to test with more games.
4. **Thinking time matters at 1.5 s** (−25 points for half the time). Search speed-ups that did nothing at 0.25 s (cache, tree reuse) might matter at tournament speed. They were not re-tested there: their mechanism checks (49% reuse hits against RaceMCTS, 15–20% cache hits) suggest small gains at best.
5. **Testing got 2–3× cheaper with the same reliability** (chapter 07.8): informative slots, early stopping and resumable runs. Adjudication was measured and rejected: late gambles flip 2–7% of "decided" games.

All failed ideas of both campaigns are listed in [15 · Failed strategies](15_failed_strategies.md),
so that they are not tried again by accident.
