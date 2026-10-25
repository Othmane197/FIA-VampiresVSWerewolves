# 15 · Failed strategies: the do-not-retry register

Every idea that was implemented, measured and rejected, in one place, so that none of them is
tried again by accident. Each row gives the measured result, where the details are, the most
likely reason, and what would justify a retry.

**How to read the results.** Δ = paired difference with the flagship of the time (points of win
rate, ± one standard error, on the same games). "Tuning" = the data the idea was tuned on;
"unseen" = hold-out maps, hold-out opponents or fresh dice; "1.5 s" = tournament speed.

**Where the code is.** None of these is in the current code. The campaign-1 ideas are in git
commit `79fd09c` ("New Patch HMM Experiment"). The campaign-2 ideas are in the local, gitignored
archive snapshot `arena/snapshots/splitter_c2/` (all options of chapter 14, plus the style HMM),
playable as `"Snap:c2:<option>=<value>"`. The cleaned style HMM is also in `arena/snapshots/splitter_v7/`.

## 15.1 Opponent modelling and prediction

| Idea | Result | Details | Likely reason | Retry only if |
|---|---|---|---|---|
| **Style HMM risk model + adaptive settings** (ex runner-up "Splitter-HMM") | Tuning +7.4 / +10.4; unseen +0.6 ± 1.1 (0.2 s); **1.5 s: −14.8 ± 4.9 and −4.8 ± 7.7, pooled −11.9 ± 4.1** | 11, 12, 08.2, 14 | Its risk relaxations (ignore 30–50% threats from "careful" opponents, smaller reserve against passive ones) are punished by deeper-searching opponents at 1.5 s | A new mechanism that is tested at 1.5 s first |
| Search steering by the opponent model (priors at opponent nodes, PUCT, trust-gated) | RaceMCTS −9; overall −0.7 to +0.3 | 11.7 | Under-explores the strong opponents' dangerous replies | Never in this form; sample opponent types instead (13.6.1, untested) |
| Policy HMM (which expert policy the opponent follows) | 35–97% next-cell accuracy, no win-rate gain when used | 11.6 | Accurate prediction ≠ better decisions: the search already assumes a strong opponent | — |
| Goal recognizer (Bayesian inverse planning) | Only used through the two rows below | 11.6 | — | — |
| Pre-emptive plans (deny, ambush, shield, tempo) from predicted targets | **−3.9 pts** | 11.7 | Acting on a wrong prediction costs a whole plan | — |
| Soft opponent model (coin-flip threats count half, `eval_coin_weight=0.5`) | −2.2 ± 3.6 (tuning) | 14.3 | The full weight is the v3 lesson: real bots strike first at 35–44% | — |

## 15.2 Planner, path planning and swarm orchestration

| Idea | Result | Details | Likely reason | Retry only if |
|---|---|---|---|---|
| Hybrid "no split" rules: `split_enemy_dist` (4 / 6) | 76.3% / 77.3% vs 79.1% (448 games) | 08.4 | Splitting is worth more than it risks | — |
| `prize_lock` (no split while a prize needs the whole army) | No effect | 08.4 | The search already declines bad splits | — |
| Map-aware deathball (no splits on prize-dominated maps) | **−3.9 pts** | 11.7 | Too coarse a map classifier | — |
| `reserve_radius=10` | RaceMCTS 42% vs 72% | 08.4 | Too timid: hardly ever splits | — |
| Exact detachment selection (`split_dp`) | Tuning +2.2 ± 2.7, **unseen −1.7 ± 3.8** | 14.3 | Noise; the 5-option combinations already contain the best set almost always | — |
| Interception (kill goals aim at the enemy's next cell) | Tuning +2.6 ± 3.4, **unseen −3.5 ± 4.3** | 14.3 | Noise; chasing the current cell is as good when the target is slower to commit | — |
| Group cap (no new splits at 5 groups) | Tuning +2.6 ± 3.2, **unseen −2.8 ± 3.8** | 14.3 | Noise; protected plans already handle many groups | — |
| Safe corridors (space-time detours) | −1.1 ± 3.2 (tuning) | 14.2, 14.3 | A corridor exists for only 1.7% of refused detachments | A less conservative threat model (enemy intent) |
| House tours (value the next house a detachment can chain) | −3.7 ± 3.7 (tuning) | 14.3 | Over-values far chains; the race projection already counts snowballing | — |
| Pincer kills (adjacent groups enter an enemy cell together) | −0.7 ± 3.3 (tuning) | 14.3 | Rare, and the opponent usually moves away first | — |
| Covered detachments (ignore threats next to our main body) | +0.4 ± 3.1 (tuning) | 14.3 | Rare situation | — |
| Endgame moves (every whole-group step when no humans are left) | −3.7 ± 3.8 (tuning) | 14.3 | More root plans dilute the search | — |
| Endgame kiting (+ rollout depth 0) | Tuning +11.3, **unseen −0.6 ± 2.0** | 12 | Over-fitting caught by the hold-out set | — |
| `danger_strike_p=0.3` | Campaign 1 +4.2 (screening only); campaign 2 −2.2 ± 3.1 | 12, 14.3 | Noise both times | — |
| Keep away from a desperate opponent once no humans are left (`keep_away`, flagship, campaign 4) | Solves the two tempo puzzles (5/5, was 0/5); screen +13.3 ± 7.3; **validation (with `race_root_safe`) +1.4 ± 4.3** | 17.4 | The situations are rare and the flagship mostly wins them anyway | A larger validation, or a position-level test on the positions where it changes the move |
| Safer race root plans when not behind (`race_root_safe`, flagship, campaign 4) | Screen +12.5 ± 6.7; **validation (with `keep_away`) +1.4 ± 4.3**; slowest move 1.74 s | 17.4 | The exposure it removes is also where the race plans' wins come from | — |
| Good-odds first strikes for the backup (`strike_p=0.6` on Splitter-Classic, campaign 4) | −4.2 ± 6.2 (screen) | 17.4 | With 2-ply quick rollouts, the Classic cannot value a strike's follow-up; it works in the flagship, whose race rollouts strike too | — |
| The desperate-opponent model for the backup (`desperate_p=0.1` + `keep_away` on Splitter-Classic, campaign 4) | Screen +1.7 ± 5.7, **validation +1.0 ± 3.8** | 17.4 | Noise; the Classic's quick rollouts never strike, so only part of the model acts | — |

## 15.3 Search and decision making

| Idea | Result | Details | Likely reason | Retry only if |
|---|---|---|---|---|
| Light tree (fewer plan variants below the root) | RaceMCTS 35% vs 48% | 05.4 | A weaker opponent model outweighs the extra iterations | — |
| Planner rollouts (rollout = the planner's top plan) | **−5.9 ± 3.4** (tuning) | 14.3 | A full plan generation per rollout step leaves too few iterations | — |
| Rollout depth 4 | −6.0 (screening, 0.1 s) | 12 | Too few iterations at 0.1 s | **Retried at 1.5 s in campaign 3** (16.4): depth 4 +1.7 ± 5.0, depth 8 +0.8 ± 6.7; uniform depth swings ±20 by opponent. Deep rollouts **in contact only** became part of Splitter-R (not a failure any more) |
| Aggressive opponent replies at the first opponent layer (`opp_race`, campaign 3; deleted, code in `Snap:c3`) | −2.5 ± 7.6 (tuning, 60 games, 1.5 s); Apex −12.5 | 16.5 | Costs 7% of the iterations; a deathball's replies do not look like RaceMCTS's | A much cheaper `race_plans`, or a measured opponent that plays them |
| Trusted plans (skip re-checking builder-made plans, `trust_plans`, campaign 3; deleted) | No measurable speed-up at 1.5 s (3,420 vs 3,462 iterations) | 16.4 | The re-checks' share was inflated by the profiler | — |
| Sequential halving at the root | −0.4 ± 3.8 (tuning) | 14.3 | No gain with ~15 root plans and a progressive-bias prior | — |
| Risk-aware final choice (mean − 0.5·std when ahead) | +1.1 ± 3.8 (tuning) | 14.3 | Noise | — |
| 18 opponent plans per node (instead of 12) | +0.4 ± 3.1 (tuning) | 14.3 | Noise | — |
| Exploration c = 0.9 / 0.4; prior weight 0.2 / 1.2; widening k = 1 / 4; max plans 12; danger weight 5; commitment 0.7 | all within ±3 (screening) | 12 | Defaults are at a local optimum | — |
| Tree reuse between turns | +0.0 ± 3.1 (tuning); with the cache −3.5 ± 4.3 (unseen). **Campaign 3, 1.5 s:** inside the "speed half", −0.8 ± 7.4 with it vs +5.8 ± 7.8 without (tuning, 60 games) | 14.3, 16.4 | Works mechanically (15–49% hits) but adds no measurable strength, at 0.25 s or at 1.5 s | — (the 1.5 s test is done) |
| Transposition cache (plans + evaluations) | +0.7 ± 2.4 (tuning). **Campaign 3, 1.5 s:** 1,495 hits per move but only +2 to +4% iterations | 14.3, 16.4 | The key (a sorted copy of the board) costs about what a hit saves | An incremental (Zobrist) position key |
| Planner caches alone (4× speed, campaign 1) | 50% head-to-head | 08.4 | Speed not the bottleneck at 0.2 s (kept for the time margin) | — |
| `gamble="always"` for our own plans | 58.3% vs 60.4% | 08.4 | No gain (`adaptive` stays the default) | — |

## 15.4 Evaluation

| Idea | Result | Details | Likely reason | Retry only if |
|---|---|---|---|---|
| Full evaluation fit (all constants, incl. contest, coin-flip exposure, domination bonus) | Better log-loss (−9%) but **−2.4 ± 4.0** in games | 14.3 | Selection bias: the recorded games come from a bot that avoids the risks these terms describe | Games recorded from a bot without those terms |
| Calibration-only fit (sharper sigmoid, discount 0.845; campaign-2 backup "Splitter-Calibrated") | +5.9 ± 4.4 (0.25 s), +5.2 ± 8.5 and −2.9 ± 8.9 (1.5 s); **campaign 3 final on fresh maps: 0.0 ± 3.1**: retired | 14.3, 16.7 | Better forecasts, no better decisions (lesson 3) | — |

## 15.5 Time, clock and game-level ideas

| Idea | Result | Details | Likely reason | Retry only if |
|---|---|---|---|---|
| Longer first move / pre-game analysis (`--pregame`) | **−4.7 pts** | 11.7 | The first move is rarely decisive | — |
| Game clock as a resource (`tempo=0.3`: think less when behind) | **−8.3 ± 6.9**; the clock never ended a game | 14.3 | Search bots do not use their full time, so the clock rarely binds; thinking less is expensive | A server whose clock really binds |
| Half the thinking time (`time_limit=0.75`) | **−25.0 ± 10.9** at 1.5 s | 14.3 | (Not an idea to adopt: it shows that thinking time matters) | — |

## 15.6 Testing shortcuts

| Idea | Result | Details | Retry only if |
|---|---|---|---|
| Adjudication by material ratio | 3×: 0 errors but only 6% of plies saved; 2×: 13% saved, 0.6–1.2% wrong; 1.5×: 2–4% wrong | 07.8 | — |
| Adjudication by stalemate (no humans, totals unchanged for N plies) | 20–34% saved but **2–7% of games misjudged** (late gambles flip games) | 07.8 | — |
| More workers at 1.5 s | Shrinks every bot's thinking time: tests another speed | 07.8 | — |

## 15.7 General lessons (why so many ideas failed)

1. **Screening winners are mostly noise.** With n candidates, the best one shows about +1.5 to +2 standard errors by chance. Every winner of both screens changed sign or vanished on unseen data, except the one with a clear mechanism (the open-loop expansion fix of campaign 1).
2. **Speed matters for the verdict.** The style HMM was neutral at 0.2 s and clearly harmful at 1.5 s. Always validate at 1.5 s.
3. **Better prediction ≠ better play.** The opponent HMMs predicted well and the full evaluation fit predicted better, but both lost games. The search optimizes decisions, not forecasts, and data recorded under one policy cannot value risks that policy avoided.
4. **The flagship's design is at a robust local optimum.** About 40 measured variations in two campaigns found one real improvement (the search bug fix). Future gains need new information (more 1.5 s games, new opponents) or a new mechanism, not more parameter variations.
5. **Campaign 3 confirmed lesson 4: the gains came from new mechanisms found in lost games.** Deep rollouts in contact (a strength of RaceMCTS) turned draws into wins; the "desperate opponent" came from reading how Splitter-R was wiped out (a 21% strike by a losing bot). Both passed hold-out and fresh-map tests; the speed tricks and the extra opponent replies, chosen from theory, did not. Before the next idea, measure how the current best loses (exposure and battle-odds tables, chapter 16.6).
6. **Campaign 4: a fix that is right on its puzzles can still be invisible in games.** The tempo fix solves the positions it targets 5/5, and both screen winners showed +13; on fresh data they gave +1.4. A puzzle proves a mechanism, not a gain: the gain depends on how often the situation decides a game. For rare situations, measure at the position level, or accept that the effect is too small to matter.
