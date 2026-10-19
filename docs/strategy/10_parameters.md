# 10 · Parameters

Every tunable, its current value, where it lives, and what the evidence says. Change these through
`SplitterAgent(...)` keyword arguments, or in the arena with `"Splitter:key=value,..."`
(chapter 07).

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
| `max_plans` | 18 | Cap on plans per node (protected plans are always kept) | — |
| `danger_weight` | 3.0 | Steps of detour accepted to avoid losing one creature per unit of size | — |
| `commit_bonus` | 0.35 | Value bonus for keeping last turn's goal | Stopped oscillating detachments (v2) |
| `pincer` | True | Synchronized conversion of a house too big for one group | prize map fix (v2) |

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
| Exposure, adjacent, enemy moves next | P · size if P ≥ 0.3 | `exposure` |
| Sigmoid steepness k | 6 → 20 with game progress | `evaluate` |
| Domination bonus | score → 0.5·score + 0.5 if a ≥ 1.5·b | `evaluate` |

## 10.3 Search: [`MCTS`](../../splitter/mcts.py#L43)

| Parameter | Value | Meaning | Evidence |
|---|---|---|---|
| `c` | 0.6 | UCT exploration constant | — |
| `prior_bias` | 0.6 | Weight of the planner's prior (progressive bias) | — |
| `rollout_depth` | 2 | Greedy plies after the tree, before `evaluate` | Variant `Splitter-norollout` available |
| `widen_k`, `widen_alpha` | 2.0, 0.5 | Children allowed = 2·√(N+1) (root fully expanded) | — |
| opponent `gamble` | "always" | The opponent model strikes first when adjacent with P ≥ 0.3 | v3 lesson |
| `light_tree` | False | Fewer plan variants below the root | True: 35% vs 48% against RaceMCTS |

## 10.4 Agent: [`SplitterAgent`](../../splitter/agent.py#L33)

| Parameter | Value | Meaning |
|---|---|---|
| `time_limit` | 1.5 s (env `SPLITTER_TIME`) | Budget per move; the server allows 2 s |
| `search` | "mcts" | "greedy" = play the planner's top plan (ablation `Splitter-greedy`) |
| `max_ply` | 200 | The server's `MaxPlays` (plies in total) |
| `game_seconds` | 300 | The server's `MaxGameDuration`, used to estimate the plies left (None in the arena) |
| behind threshold | `evaluate` < 0.35, or the last 20 plies with less material | Enables gambles when `gamble="adaptive"` |
| `seed` | None | Random seed of the search (set in tests) |
| `verbose` | False (env `SPLITTER_VERBOSE=1`) | Print the root statistics every turn |
