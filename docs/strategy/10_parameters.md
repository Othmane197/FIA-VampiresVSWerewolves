# 10 · Parameters

Every tunable, its current value, where it lives, and what the evidence says. Change these through
`SplitterAgent(...)` keyword arguments, or in the arena with `"Splitter:key=value,..."`
(chapter 07).

Δ values marked **(A)** come from the screening in chapter 12 (paired, tuning set, 0.1 s): only
large or replicated differences mean anything there.

## 10.1 Plan generator: [`PlanConfig`](../../splitter/planner.py#L31)

| Parameter | Value | Meaning | Evidence |
|---|---|---|---|
| `splits` | True | Allow detachments | Off = the no-split ablation: 74.3% vs 79.1% |
| `max_detachments` | 3 | Detachments per group per turn | — |
| `split_groups` | 2 | How many of our biggest groups may split in one plan | Lowering it (light tree) was weaker |
| `alt_groups` | 4 | Groups that get alternative-goal variants | Lowering it (light tree) was weaker |
| `safety_margin` | 1 | Extra moves of distance from enemies ≥ 1.5× a detachment after it converts | — |
| `reserve_ratio` | 1.0 | Main body ≥ ratio × nearby enemy groups (+1) | — |
| `reserve_radius` | 6 | "Nearby" for the reserve rule | 3 lost close maps; 10: 42% vs 72% against RaceMCTS |
| `split_enemy_dist` | 0 (off) | No split while an enemy group ≥ half our size is this close | 6: 77.3%, 4: 76.3% vs 79.1% |
| `prize_lock` | False | No split while a house needs our whole army | No effect |
| `gamble` | "adaptive" | `never` / `adaptive` (only when behind) / `always` | always: no gain |
| `max_plans` | 18 | Cap on plans per node (protected plans are always kept) | 12: −1.8 (A) |
| `danger_weight` | 3.0 | Steps of detour accepted to avoid losing one creature per unit of size | 5: −0.6 (A) |
| `danger_strike_p` | 0.45 | `safe_step` treats an adjacent enemy as a threat above these odds | 0.3: +4.2 (A), not validated |
| `commit_bonus` | 0.35 | Value bonus for keeping last turn's goal | Stopped oscillating detachments (v2); 0.7: +1.5 (A) |
| `pincer` | True | Synchronized conversion of a house too big for one group | prize map fix (v2) |
| `hunt_bonus` | 0.1 | Prior bonus of the `hunt` plan (raised by the opponent model against splitters) | — |
| `preempt` | "" (off) | Pre-emptive families from the opponent model: `deny,ambush,shield,tempo` | **−3.9 pts** (chapter 11) |
| `preempt_min_prob` | 0.3 | Minimum probability of a predicted target before acting on it | — |

**Constants in [planner.py](../../splitter/planner.py):**
- [`GAMMA`](../../splitter/planner.py#L26) = 0.9: distance discount of goal values.
- [`PROTECTED`](../../splitter/planner.py#L27): the plan tags never truncated.

## 10.2 Evaluation: [evaluate.py](../../splitter/evaluate.py)

| Item | Value | Where |
|---|---|---|
| Race discount | [`DISCOUNT`](../../splitter/evaluate.py#L24) = 0.93 per move | `project_race` |
| Race horizon | remaining plies / 2 | `evaluate` |
| Head start of the side to move next | 0.5 move | `evaluate` |
| Contest factors | 0 (sure-kill contest) / 0.5 (≥ 50% contest) | `_contest` |
| Exposure, adjacent, enemy moves next | P · size if P ≥ `strike_p` (0.3; **0.5 against an opponent the HMM has seen never take long shots**) | `exposure` |
| Sigmoid steepness k | 6 → 20 with game progress | `evaluate` |
| `kite` | off; on = steepness 20 once no humans are left | `evaluate` (+5.1 tuning, −0.6 hold-out: rejected) |
| Domination bonus | score → 0.5·score + 0.5 if a ≥ 1.5·b | `evaluate` |

## 10.3 Search: [`MCTS`](../../splitter/mcts.py#L43)

| Parameter | Value | Meaning | Evidence |
|---|---|---|---|
| `c` | 0.6 | UCT exploration constant | 0.4: −0.9, 0.9: −3.0 (A) |
| `prior_bias` | 0.6 | Weight of the planner's prior (progressive bias) | 0.2: −0.9, 1.2: +1.8 (A) |
| `rollout_depth` | 2 | Greedy plies after the tree, before `evaluate` | 0: +3.6, 4: **−6.0** (A) |
| `widen_k`, `widen_alpha` | 2.0, 0.5 | Children allowed = k·√(N+1) (root fully expanded) | k = 1: +2.4, k = 4: +2.7 (A) |
| opponent `gamble` | "always" | The modelled opponent may strike first when adjacent with P ≥ 0.3 | v3 lesson |
| `light_tree` | False | Fewer plan variants below the root | True: 35% vs 48% against RaceMCTS |
| `opp_selection` | "puct" | Selection at opponent nodes when the model steers the search | — |
| `opp_priors` | True (only used if the model is on) | I1: the model steers the opponent replies (trust-gated) | Hurts vs strong bots: use `opp_priors=0` |
| `opp_eval` | True (only used if the model is on) | I2 + I3: opponent strikes in rollouts, opponent-specific strike threshold | **This is where the model's gain comes from** (chapter 12) |

## 10.4 Agent: [`SplitterAgent`](../../splitter/agent.py#L33)

| Parameter | Value | Meaning |
|---|---|---|
| `time_limit` | 1.5 s (env `SPLITTER_TIME`) | Budget per move; the server allows 2 s |
| `search` | "mcts" | "greedy" = play the planner's top plan (ablation `Splitter-greedy`) |
| `max_ply` | 200 | The server's `MaxPlays` (plies in total) |
| `game_seconds` | 300 | The server's `MaxGameDuration`, used to estimate the plies left (None in the arena) |
| behind threshold | `evaluate` < 0.35, or the last 20 plies with less material | Enables gambles when `gamble="adaptive"` |
| `opponent_model` | FINAL_OM | HMM opponent model (chapter 11) |
| `adapt` | True | I5: risk settings follow the opponent's measured style (with the model) |
| `map_aware` | False | Deathball on maps dominated by one prize: −3.9 pts, rejected |
| `first_move_time` | 0 | Longer first move (arena test of `--pregame`): −4.7, rejected |
| `seed` | None | Random seed of the search (set in tests) |
| `verbose` | False (env `SPLITTER_VERBOSE=1`) | Print the root statistics every turn |
