# 13 · Future improvements

The idea list written after campaign 1. **Campaign 2 (chapter 14) implemented and measured most of
it**; the table below gives each idea's outcome, and 13.1 the next steps that campaign 2 points
to. The sections 13.2–13.7 keep the original reasoning for each idea.

Constraints that still apply: plain Python standard library (no AI, tree or graph libraries), one
CPU core (no pondering, no multiprocessing in the bot), 2 s per move, Python 3.8.

## 13.0 What happened to each idea (campaign 2)

| Idea | Section | Outcome |
|---|---|---|
| Tree reuse between turns | 13.2.1 | Implemented; 15–49% hit rate; no gain at 0.25 s (+0.0); removed |
| Sequential halving at the root | 13.2.2 | Implemented; −0.4; removed |
| Risk-aware final choice | 13.2.3 | Implemented; +1.1 (noise); removed |
| Game clock as a resource (`tempo`) | 13.2.4 | Implemented with a referee clock; −8.3 (the clock rarely binds); removed |
| Adaptive time per move | 13.2.5 | Not useful: the limit is per move, and half the time costs 25 points |
| Transposition cache | 13.3.1 | Implemented; 15–20% hits; +0.7; removed |
| Per-map precomputation, race tables | 13.3.2–3 | Not done: speed made no difference at 0.25 s |
| Paths around obstacles | 13.4.1 | Not done (no walls on the maps) |
| Space-time safe corridors | 13.4.2 | Implemented; a corridor exists for only 1.7% of refused detachments; −1.1; removed |
| House tours | 13.4.3 | Implemented; −3.7; removed |
| Interception | 13.4.4 | Implemented; +2.6 tuning, −3.5 unseen; removed |
| Exact detachment selection | 13.5.1 | Implemented; +2.2 tuning, −1.7 unseen; removed |
| Planned rendezvous | 13.5.2 | Not done: merging groups already meet halfway |
| Retaliation-aware safety | 13.5.3 | Implemented (`covered`); +0.4; removed |
| Pincer kills | 13.5.4 | Implemented; −0.7; removed |
| Screening | 13.5.5 | Not done (needs a threat-movement model; the related *shield* plans lost 3.9) |
| Group-count control | 13.5.6 | Implemented (cap 5); +2.6 tuning, −2.8 unseen; removed |
| Sample opponent types | 13.6.1 | Approximated by half-weight coin-flip threats; −2.2; removed |
| Predictions in rollouts | 13.6.2 | Not done (the policy HMM was retired) |
| Calibrate the evaluation | 13.6.3 | **Done**: under-confident about leads (0.65–0.75 predicted, 92% won) |
| Evaluation tuning on game outcomes | 13.7.1 | **Done** (`tools/tune_eval.py`): the calibration-only fit is **the backup model** |
| SPSA / SPRT | 13.7.2 | Replaced by informative slots + early stopping (2–3× cheaper, chapter 07.8) |
| Exact endgame solver | 13.7.3 | Approximated by whole-group endgame moves; −3.7; removed |
| Watchdog move | 13.7.4 | **Done, kept** (`main.py`) |
| More diverse test opponents | 13.7.5 | **Done, kept** (`Styled:<n>`) |
| Version ladder (Elo) | 13.7.6 | Not done (`arena.history` covers the need) |
| Opening preparation | 13.7.7 | Not done (unknown tournament maps) |

## 13.1 Next steps after campaign 2

| # | Idea | Why |
|---|---|---|
| 1 | **More 1.5 s games for the backup** (calibrated evaluation), e.g. 300 games on the hold-out slots | Pooled +4.3 ± 3.6 over all stages: the only idea with a consistent mechanism; enough games could promote it to flagship |
| 2 | **Re-test tree reuse + transposition cache at 1.5 s** (`Snap:c2:reuse=1,plan_cache=1`) | Thinking time is worth a lot at 1.5 s (−25 for half the time); these give free iterations, but were only measured at 0.25 s |
| 3 | **Fit the evaluation on games from a less cautious bot** | The full fit failed because of selection bias (14.3); data from a bot that takes the risks would let the fit value the risk terms |
| 4 | **Play other teams' bots** as soon as they are available (`py:<file>`, `tools/server_match.py`) | The only truly independent validation set |
| 5 | **Opponent-type sampling done properly** (13.6.1): a per-iteration mixture of opponent configurations in the tree | Keeps exploration of dangerous replies, unlike the failed steering; untested |

## 13.2 Decision making

1. **Tree reuse between turns.** After our move and the opponent's reply, descend into the child for our plan, then the opponent child whose moves match the reconstructed reply (`reconstruct_flows`), and keep its statistics as the new root. The tree is open-loop (it stores plans, not boards), so the statistics transfer without re-simulation. Plans that became illegal are dropped, as at expansion. *Test:* iterations per decision and paired win rate vs `Snap:v7`.
2. **Sequential halving at the root.** With about 15 root plans and 1,500–3,000 iterations, UCT spends many visits on plans that are clearly bad. Sequential halving (as in Gumbel MuZero, Danihelka et al. 2022) gives every plan a fixed share, then repeatedly halves the field: a better use of a small budget for the one decision that matters. *Test:* paired, at 0.2 s and 1.5 s.
3. **Risk-aware final choice.** Back up the variance of rewards as well as the mean. When far ahead late in the game, prefer the plan with the lower chance of a disaster (mean − λ·std) instead of the highest mean. This is the principled version of the rejected kiting rule: it acts only when the search itself sees variance. *Test:* hold-out maps, both proxies.
4. **The game clock as a strategic resource.** The server ends the game after `MaxGameDuration` (5 minutes), usually before the 200-ply cap (chapter 06). How fast we answer changes how many plies the game lasts. When clearly ahead, use the full budget (fewer plies left for the opponent to recover); when behind, answer quickly to get more plies. Nobody in the panel does this. *Test:* fake server with the real clock (`tools/server_match.py`), since the arena has no clock.
5. **Adaptive time per move.** The limit is per move, so time cannot be banked. But forced turns (one plan, or a root where one plan has most visits early) can stop early, which matters only through idea 4.

## 13.3 Caching

1. **Transposition table for plans and evaluations.** Plan generation dominates the cost of an iteration (chapter 05.4). Inside one search, open-loop replays often reach the same board (sure outcomes are deterministic; dice matter only in random battles). Key a cache with a Zobrist hash of (groups, humans, side to move) and store `generate_plans` output and `evaluate` results. *First measure the hit rate:* if it is low, skip this. Lesson 1 says speed alone does not win, so this is worth doing only together with something that uses more iterations well (13.2.2).
2. **Per-map precomputation.** Distances, neighbours and border distances are fixed per map. Precompute them once on MAP (the idle time before the first UPD), instead of recomputing per call. Cheap and safe.
3. **Race tables per turn.** `project_race` and `race_won` recompute who reaches which house first for every plan. Computing, once per root, the arrival time of every group at every house and reusing it for all plans at that node would cut repeated work.

## 13.4 Path planning

1. **Paths around obstacles.** Today distance is Chebyshev and detachments follow [`straight_path`](../../splitter/planner.py#L77). Houses we cannot convert and enemy groups are obstacles (stepping on them starts a battle). A BFS distance field from each target, computed once per turn and shared by all plans, gives true distances and better goals on cluttered maps.
2. **Space-time safe corridors.** [`detachment_safe`](../../splitter/planner.py#L112) checks only the straight path, and refuses the split if any cell of it can be intercepted. Instead, build a danger map: cell c is unsafe at step t for a detachment of k if an enemy of ≥ k can reach c within t moves. Then search a path in (cell, time) that avoids unsafe cells (A* with Chebyshev distance as the heuristic). Splits that are refused today because of one exposed cell would get a safe detour. *Test:* split rate and win rate on `villages` and `holdout`, plus the safety unit tests.
3. **House tours.** A detachment of h converts a house and becomes 2h, which can then take a house of up to 2h. Planning a short tour (a greedy prize-collecting path over nearby houses) chooses better detachment sizes and targets than one goal at a time. The race projection already rewards snowballing ([`project_race`](../../splitter/evaluate.py#L67)), so the planner would only need to propose such tours.
4. **Interception instead of pursuit.** For a hunt, aim at the cell the enemy group is heading to (the `heading` feature, or its nearest convertible house) rather than where it stands now.

## 13.5 Swarm orchestration

1. **Exact detachment selection.** Choosing which houses to split for is a knapsack problem: creatures available (group − reserve) against houses with value h·γ^d. Today [`_split_orders`](../../splitter/planner.py#L456) enumerates combinations of the best 5 options. A small dynamic program over the creature budget finds the best set exactly, and is cheap for groups ≤ 255.
2. **Planned rendezvous.** After converting, a detachment either drifts or merges back through the `merge` goal. Choosing the meeting cell explicitly (it minimizes rejoin time plus exposure along both paths) would bring the army back together faster before a big house or a fight.
3. **Retaliation-aware safety.** A detachment next to our main body is protected even if a bigger enemy could reach it: an attacker that wins ends up next to a group that kills it for sure. A rational opponent with lookahead will not attack. The safety check could accept such positions ("covered" detachments), allowing more splits near the main body. Risk: reckless opponents attack anyway, so this needs the hold-out proxies.
4. **Pincer kills.** The server sums arrivals on a cell before resolving the battle (chapter 02). Two groups that are each too small to kill an enemy group for sure can do it together if their sum is ≥ 1.5× the enemy: the same mechanism as [`_pincer_orders`](../../splitter/planner.py#L524), applied to enemy groups instead of houses.
5. **Screening.** The main body positions itself between the strongest enemy group and our detachments, so interception paths go through it. The rejected *shield* family was driven by predictions; this one is purely geometric.
6. **Group-count control.** In lost games with 6+ groups, plans got truncated and coordination broke (chapter 03.5). A soft cap on the number of groups, or a merge bonus that grows with the group count, keeps the swarm manageable.

## 13.6 Prediction

1. **Sample opponent types instead of narrowing.** The steering experiment failed because it put most of the search into the "likely" replies. Instead, at the start of each MCTS iteration, sample one opponent type from the style HMM's belief (for example: careful, gambler, deathball) and use that type's settings for the whole iteration. Dangerous replies keep their share of iterations in proportion to their probability, and nothing is pruned.
2. **Predictions in the rollouts.** Rollouts are cheap to get wrong. The archived policy HMM predicted Greedy and Starter at 92–97% (chapter 11.6); using the best-predicting expert as the opponent's rollout policy makes leaf values more realistic at no cost to tree exploration.
3. **Calibrate the evaluation.** Plot the predicted P(win) of [`evaluate`](../../splitter/evaluate.py#L169) against actual results, from the stored traces (`--save-all-logs`). If, say, 0.7 positions are won 85% of the time, the sigmoid is too flat. Calibration errors show which stage of the evaluation is wrong.

## 13.7 Other unexplored areas

1. **Evaluation tuning on game outcomes** (Texel-style tuning, as in chess engines). From the recorded traces, fit the evaluation's constants (the discount `DISCOUNT`, the sigmoid steepness, the contest and exposure factors) by logistic regression of the final result on the evaluation of every position. Plain Python gradient descent is enough. *Overfitting control:* fit on tuning maps and opponents, validate on `holdout`, as in chapter 12.
2. **Automatic parameter tuning with early stopping.** SPSA perturbs all constants at once and needs few games per step. SPRT (sequential probability ratio test) stops an A/B test as soon as the result is clear, often after a fraction of the games. Together they would replace the manual screening of chapter 12.
3. **Exact endgame solver.** Once no humans are left and there are few groups, the game is small: positions with only sure kills are deterministic. An expectimax over raw moves, limited to the last plies, can play these endgames exactly instead of through plans.
4. **Watchdog move.** Python cannot interrupt a running computation. A timer thread started with each UPD sends the fallback move if no answer exists at 1.8 s, with a lock so only one MOV is ever sent. This protects against an unexpectedly slow machine, a garbage-collection pause or a pathological position. *Test:* the protocol tests, with an artificially slow agent.
5. **More diverse test opponents.** To avoid overfitting to our teammates' bots, generate opponents with randomized styles (random `PlanConfig` values, gamble policy, split rate) and use them as a third validation set. Play other teams' bots as soon as they are available: `py:<file>` for Python files, `tools/server_match.py` for anything else (chapter 07.5).
6. **Version ladder.** `arena/results/history.csv` already stores every run. A small script turning the paired comparisons into Elo ratings per version would show progress over time and catch regressions.
7. **Opening preparation, only for known maps.** If the tournament maps are published in advance, deep first-move searches can be computed offline. The longer first move tested in the arena (−4.7) does not support doing this for unknown maps.
