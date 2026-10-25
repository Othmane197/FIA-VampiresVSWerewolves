# 10 · Parameters

Every tunable that exists in the code, its current value, where it lives, and what the evidence
says. Change these through `SplitterAgent(...)` keyword arguments, or in the arena with
`"Splitter:key=value,..."` (chapter 07); evaluation constants as `eval_<name>`. An unknown key
raises `TypeError`.

Δ values marked **(A)** come from the screening in chapter 12 (paired, tuning set, 0.1 s): only
large or replicated differences mean anything there.

## 10.0 The two kept models ([`MODELS`](../../splitter/agent.py#L37))

| Name | Settings | Evidence |
|---|---|---|
| **Splitter** (flagship, "Splitter-R3") | the defaults below + the campaign-3 options marked "flagship" in 10.4b | Campaign 3 final (fresh maps, never-used styles, 1.5 s): 72.9%, **+8.0 ± 3.9** over the backup; real conditions vs the live teammate bots 9-1-2, 0 timeouts (chapter 16) |
| **Splitter-Classic** (backup) | all defaults below | The campaign-2 flagship (= frozen v7): 64.9% in the same final; 79.3% vs the 9-opponent panel at 0.2 s, 78.7% at 1.5 s (chapters 08, 14) |

## 10.1 Plan generator: [`PlanConfig`](../../splitter/planner.py#L32)

| Parameter | Value | Meaning | Evidence |
|---|---|---|---|
| `splits` | True | Allow detachments | Off = the no-split ablation: 74.3% vs 79.1% |
| `max_detachments` | 3 | Detachments per group per turn | — |
| `split_groups` | 2 | How many of our biggest groups may split in one plan | Lowering it (light tree) was weaker |
| `alt_groups` | 4 | Groups that get alternative-goal variants | Lowering it (light tree) was weaker |
| `safety_margin` | 1 | Extra moves of distance from enemies ≥ 1.5× a detachment after it converts | — |
| `reserve_ratio` | 1.0 | Main body ≥ ratio × nearby enemy groups (+1) | — |
| `reserve_radius` | 6 | "Nearby" for the reserve rule | 3 lost close maps; 10: 42% vs 72% against RaceMCTS |
| `gamble` | "adaptive" | `never` / `adaptive` (only when behind) / `always` | always: no gain |
| `max_plans` | 18 | Cap on plans per node (protected plans are always kept) | 12: −1.8 (A) |
| `danger_weight` | 3.0 | Steps of detour accepted to avoid losing one creature per unit of size | 5: −0.6 (A) |
| `danger_strike_p` | 0.45 | `safe_step` treats an adjacent enemy as a threat above these odds | 0.3: +4.2 (A) in campaign 1, −2.2 ± 3.1 in campaign 2: noise |
| `commit_bonus` | 0.35 | Value bonus for keeping last turn's goal | Stopped oscillating detachments (v2); 0.7: +1.5 (A) |
| `pincer` | True | Synchronized conversion of a house too big for one group | prize map fix (v2) |
| `hunt_bonus` | 0.1 | Prior bonus of the `hunt` plan | — |

**Constants in [planner.py](../../splitter/planner.py):**
- [`GAMMA`](../../splitter/planner.py#L27) = 0.9: distance discount of goal values.
- [`PROTECTED`](../../splitter/planner.py#L28): the plan tags never truncated.

## 10.2 Evaluation: [evaluate.py](../../splitter/evaluate.py)

| Item | Value | Where |
|---|---|---|
| Race discount | `discount` = 0.93 per move ([`EvalParams`](../../splitter/evaluate.py#L29); backup **0.845**) | `project_race` |
| Race horizon | remaining plies / 2 | `evaluate` |
| Head start of the side to move next | 0.5 move | `evaluate` |
| Contest factors | 0 (sure-kill contest) / 0.5 (≥ 50% contest) | `_contest` |
| Exposure, adjacent, enemy moves next | P · size if P ≥ `strike_p` = 0.3 | `exposure` |
| Sigmoid steepness k = `k0` + `k1`·progress | 6 + 14·progress: 6 → 20 (backup **8.5 + 27·progress**: 8.5 → 35.5) | `evaluate` |
| Domination bonus | score → 0.5·score + 0.5 if a ≥ 1.5·b | `evaluate` |

## 10.3 Search: [`MCTS`](../../splitter/mcts.py#L48)

| Parameter | Value | Meaning | Evidence |
|---|---|---|---|
| `c` | 0.6 | UCT exploration constant | 0.4: −0.9, 0.9: −3.0 (A) |
| `prior_bias` | 0.6 | Weight of the planner's prior (progressive bias) | 0.2: −0.9, 1.2: +1.8 (A) |
| `rollout_depth` | 2 | Greedy plies after the tree, before `evaluate` | 0: +3.6, 4: **−6.0** (A); 0 combined with kiting failed validation |
| `widen_k`, `widen_alpha` | 2.0, 0.5 | Children allowed = k·√(N+1) (root fully expanded) | k = 1: +2.4, k = 4: +2.7 (A) |
| opponent `gamble` | "always", 12 plans | The modelled opponent may strike first when adjacent with P ≥ 0.3 | v3 lesson; 18 plans: +0.4 ± 3.1 (campaign 2) |
| `ev` | `EvalParams()` | Evaluation constants used at the leaves | both models use the defaults |

## 10.4 Agent: [`SplitterAgent`](../../splitter/agent.py#L2)

| Parameter | Value | Meaning |
|---|---|---|
| `time_limit` | 1.5 s (env `SPLITTER_TIME`) | Budget per move; the server allows 2 s |
| `search` | "mcts" | "greedy" = play the planner's top plan |
| `max_ply` | 200 | The server's `MaxPlays` (plies in total) |
| `game_seconds` | 300 | The server's `MaxGameDuration`, used to estimate the plies left (None in the arena) |
| behind threshold | `evaluate` < 0.35, or the last 20 plies with less material | Enables gambles when `gamble="adaptive"` |
| `eval_discount`, `eval_k0`, `eval_k1` | 0.93, 6, 14 | Evaluation constants (`EvalParams`); the retired Splitter-Calibrated used 0.845, 8.5, 27 |
| `seed` | None | Random seed of the search (set in tests) |
| `verbose` | False (env `SPLITTER_VERBOSE=1`) | Print the root statistics every turn |

Tournament-client environment: `SPLITTER_TIME` (1.5), `SPLITTER_MODEL` (`flagship` / `backup`),
`SPLITTER_WATCHDOG` (1.8 s: fallback move if the agent is later than that), `SPLITTER_VERBOSE`.

## 10.4b Campaign 3 options (chapter 16)

Off by default (the backup uses none); the flagship turns on the eight marked below.

| Parameter | Default (flagship) | Where | Meaning | Evidence |
|---|---|---|---|---|
| `rollout_policy` | "quick" (**"race"**) | `MCTS` | RaceMCTS's stochastic goal policy in rollouts, on our exact rules | Part of Splitter-R: +6.2 ± 4.6 (hold-out + live bots), +5.9 ± 4.1 (fresh maps) |
| `rollout_strike` | 0.0 (**0.45**) | `MCTS` | In race rollouts, strike first from these odds (both sides) | idem |
| `rollout_depth_contact` | 0 (**6**) | `MCTS` | Rollout depth when opposing groups are within `contact_radius` = 3 cells or no humans are left | Uniform depth 4 / 8: +1.7 / +0.8 (16.4) |
| `leaf_mix` | 1.0 (**0.5**) | `MCTS` | Leaf value = (1 − mix) · before the rollout + mix · after | Part of Splitter-R |
| `race_root` | False (**True**) | agent | RaceMCTS-style plans added at the root, at half the top prior | Ablation −1.7 ± 6.6 without vs −0.8 with (screen, 16.4) |
| `bait_check` | False (**True**) | `PlanConfig` | Discount kills whose victim cell sits next to another strong enemy | Puzzle test; part of Splitter-R |
| `strike_p` | 0.0 (**0.6**) | `PlanConfig` | "strike" plans against adjacent enemies beaten with these odds, even when not behind | +5.0 ± 6.9 (screen, 16.5) |
| `desperate_p` | 0.0 (**0.1**) | agent | When the opponent is losing (our value ≥ 0.65), it is expected to strike from these odds: sets the three thresholds below and the race-rollout strikes for that decision | +7.5 ± 7.7 (screen); Expecti-live +18.8 in the final (16.6–16.7) |
| `gamble_p` | 0.3 | `PlanConfig` | Gamble goals from these odds (the modelled desperate opponent's: `desperate_p`) | — |
| `threat_p` | 0.3 | `PlanConfig` | An enemy within 2 cells that strikes with these odds is a threat to flee from | — |
| `eval_opp_strike_p` | 0.3 | `EvalParams` | Exposure: the opponent strikes us from these odds | — |


## 10.5 Removed parameters (measured, then deleted from the code)

| Parameter | What it did | Result |
|---|---|---|
| `split_enemy_dist` | No split while an enemy group ≥ half our size is this close | 6: 77.3%, 4: 76.3% vs 79.1% |
| `prize_lock` | No split while a house needs our whole army | No effect |
| `light_tree` | Fewer plan variants below the root | 35% vs 48% against RaceMCTS |
| `kite` | Steepest sigmoid once no humans are left | +5.1 tuning, −0.6 hold-out |
| `preempt`, `preempt_min_prob` | Pre-emptive plan families from the goal recognizer | −3.9 pts |
| `opp_priors`, `opp_selection` | Opponent model steers the opponent's plan priors (PUCT) | Hurt vs RaceMCTS (−9) |
| `opp_eval` | Switch for the model's risk hooks | Was always on in the (retired) runner-up |
| `map_aware` | Deathball on prize-dominated maps | −3.9 pts |
| `first_move_time`, `--pregame` | Longer first move / pre-game analysis | −4.7 pts |
| `opponent_model`, `adapt` | The style-HMM runner-up "Splitter-HMM" and its adaptive settings | −11.9 ± 4.1 at 1.5 s (pooled) |
| **Campaign 2** (chapter 14): `pincer_kill`, `split_dp`, `corridors`, `tour_bonus`, `intercept`, `covered`, `group_cap` (planner); `plan_cache`, `reuse`, `root_policy`, `risk_lambda`, `rollout_policy`, `opp_max_plans` (search); `endgame_moves`, `tempo` (agent); `eval_contest_half`, `eval_coin_weight`, `eval_dom_bonus` (evaluation) | See chapter 14.2 | All within noise or worse on unseen data; full list with results in [15](15_failed_strategies.md) |
| **Campaign 3** (chapter 16): `trust_plans` (planner); `plan_cache`, `reuse` (re-tested at 1.5 s), `opp_race` (search) | Skip plan re-checks; transposition cache; tree reuse; aggressive opponent replies at the first opponent layer | No speed-up / −0.8 vs +5.8 with and without the speed half / −2.5 ± 7.6; code in the local snapshot `arena/snapshots/splitter_c3/` |
| Model "Splitter-Calibrated" (campaign-2 backup: `eval_discount=0.845, eval_k0=8.5, eval_k1=27`) | Evaluation fitted on game outcomes | 0.0 ± 3.1 vs the Classic on fresh maps (16.7): retired; still expressible with those three options |
| **Campaign 4** (chapter 17): `keep_away` (agent) with `PlanConfig.keep_away_p`; `race_root_safe` (agent) | Keep out of a desperate opponent's reach once no humans are left; safer race root plans when not behind | Screens +13.3 and +12.5, validation together +1.4 ± 4.3: not adopted; code in the local snapshot `arena/snapshots/splitter_c4/` |
