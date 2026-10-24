# 16 · Campaign 3: Splitter-R, the flagship merged with RaceMCTS

**Goal:** merge the flagship with the one real strength of Ronita's RaceMCTS (long, dice-driven
rollouts) plus the top-ranked fixes of the code review, without importing RaceMCTS's
weaknesses; test the result against the teammates' **live** bots, unseen opponent styles and our
own flagship; keep it only if it wins on data never used to build it.

**References, kept unchanged:** the flagship `Splitter` and the backup `Splitter-Calibrated`
(chapter 14). Verified after every change: the flagship still makes the same decisions as the
frozen `Snap:v7` on 300 of 300 test positions.

**Sources:** the merger study ("The Splitter: progression, methodology and the RaceMCTS merger
study", Proposal A) and the code review ("The Splitter: code review and ranked edge plan",
ranked suggestions 1 to 3).

## 16.1 What was built (all options, off by default)

| Option | From | What it does | Where |
|---|---|---|---|
| `rollout_policy="race"` | Merger A, step 1 | RaceMCTS's rollout policy on our exact rules: each group takes its best goal (convert h / (d + 0.5), sure kill 1.2 e / (d + 0.5), regroup, flee, chase), its second with probability 0.15; never steps into a fight it cannot win for sure | [`race_rollout_plan`](../../splitter/planner.py#L714) |
| `rollout_strike=0.45` | Merger A, step 2 | In race rollouts, a group adjacent to an enemy it beats with at least these odds strikes first (both sides) | `race_rollout_plan` |
| `rollout_depth_contact=6` | Merger A, step 3 | Rollouts this deep when opposing groups are within 3 cells or no humans are left; `rollout_depth` (2) elsewhere | [`in_contact`](../../splitter/mcts.py#L324), [`MCTS._iterate`](../../splitter/mcts.py#L231) |
| `leaf_mix=0.5` | Merger A, step 4 | Leaf value = (1 − mix) · value before the rollout + mix · value after it | `MCTS._iterate` |
| `race_root=True` | Merger A, step 6 | RaceMCTS's plan families (all groups to their best goal, whole-group splits to two houses, regroup, one group on its second goal) added at the root only, at half the top prior | [`race_plans`](../../splitter/planner.py#L813), [`SplitterAgent._choose`](../../splitter/agent.py#L169) |
| `bait_check=True` | Code review, rank 2 | A kill goal is discounted (× 0.1 / × 0.4) when another enemy next to the victim's cell could kill / strike the hunter right after; such kills get no hunt plan | [`bait_factor`](../../splitter/planner.py#L110) |
| `trust_plans=True` | Code review, rank 3 | The planner skips re-checking plans its builder made legal by construction; the tree and the safety net still check | `generate_plans` |
| `plan_cache=True` | Code review, rank 3; merger study, new ideas | Transposition cache inside one search: plans keyed by (board, side, behind), leaf values by (board, side to move, plies left). Ported from the campaign-2 archive | [`MCTS._plans`](../../splitter/mcts.py#L90), [`MCTS._evaluate`](../../splitter/mcts.py#L109) |
| `strike_p=0.6` | Code review, rank 4 (light) | Iteration 2: a separate "strike" plan when one of our groups is next to an enemy it beats with at least these odds but not for sure (between 1.1x and 1.5x its size), even when we are not behind. The flagship only offers such strikes when losing. The base plan is unchanged; the search judges the dice | [`generate_plans`](../../splitter/planner.py#L364) (section 6b) |
| `opp_race=True` | Code review, rank 5 (cheap form) | Iteration 2: the opponent's first reply (the layer just below the root) also considers RaceMCTS-style aggressive plans, at half the top prior. Our tree's opponent is otherwise our own cautious planner | [`_with_race_replies`](../../splitter/mcts.py#L311) |
| `reuse=True` | Code review, rank 3; merger study, new ideas | Tree reuse between turns: last turn's node for our played plan, then the opponent reply that replayed without dice turns the board we left into the board we see. A random battle on the way means no exact match and a fresh tree. Guarded so a tree is only reused for the exact position it was built for | [`MCTS.subtree_after`](../../splitter/mcts.py#L209), [`MCTS._make_root`](../../splitter/mcts.py#L188) |

RaceMCTS's code itself is **not** imported: its simulator (`game_engine.py`) treats a defender 1.5x
bigger as a sure defence, which the real server does not.

## 16.2 New opponents and data for this campaign

- **The teammates' live bots** (`Apex-live`, `RaceMCTS-live`, `Expecti-live`): their tournament entry points with their own presets and budgets. Othmane's live preset is the new "champion" Apex (Voronoi territory + quiescence search, 1.65 s, pushed 2026-10-22); Dana's is `SafeAgent` around her expectiminimax (1.2 s); Ronita's is RaceMCTS at 1.6 s.
- **A fresh map family** (`--maps fresh`: 8 maps, seeds 201 to 208, from 9 x 13 to 20 x 32), never used for any tuning or earlier validation.

## 16.3 Decision rules, written before the runs

1. **Gate (stage 0):** rollout depth 4 and 8 vs the flagship at 1.5 s, tuning slots. The rollout half of the merger goes ahead if the better depth is not clearly worse (paired difference + 2 SE > 0); otherwise only the root plans and the two fixes are kept for testing.
2. **Screen (stage 1, tuning slots, 1.5 s):** the full merger and its ablations against the flagship; a variant goes on if it is not clearly worse and the full merger's components each show no clear harm.
3. **Validation (stage 2, hold-out slots + live bots, 1.5 s):** the chosen variant must be positive against the flagship.
4. **Final, pre-registered (stage 3, fresh maps, fresh seed, 1.5 s):** Splitter-R replaces the flagship only if its fresh-map paired difference is positive **and** stages 2 and 3 pooled are above 2 standard errors. If positive but under 2 SE, it becomes a third reference model (not the flagship). Otherwise it is recorded as failed (chapter 15).
5. **Real conditions:** whatever is adopted plays 4 games against each live teammate bot over the real protocol (`tools/teammate_matches.py`), with no illegal moves and no timeouts allowed.
6. **Iteration 2 screen** (written before its games; tuning slots, 1.5 s, `--seed 9600`): Splitter-R as the first bot against `Splitter-R:strike_p=0.6`, `Splitter-R:opp_race=true` and both together. A component is kept if its own variant's paired difference to Splitter-R is positive; the kept components form **R2** only if the variant combining them is not clearly worse than Splitter-R (difference + 2 SE > 0). Otherwise there is no R2.
   **Stage 3 set-up, fixed now:** the flagship (first bot), the backup, Splitter-R (and R2 if it exists) against the three live bots and **Styled:7 to 12, styles never used before** (Styled:1 to 6 were used in validation), on the 8 fresh maps, both sides, `--seed 9700`, 1.5 s: 144 games per bot. Styles 7 to 12 range from a gambling deathball (7) and a greedy splitter (8) to cautious splitters that never gamble (10 to 12); like all Styled bots they share our planner, so they are not independent of it.
7. **R2 in the final** (amends rule 4): if R2 exists, stage 3 plays it beside Splitter-R. R2 is the one judged for adoption only if, on the fresh maps, it beats Splitter-R (paired difference > 0) **and** its own difference to the flagship is above 2 SE on stage 3 alone, since it had no separate validation. Otherwise rule 4 is applied to Splitter-R as written.
8. **Iteration 3 screen** (written before its games; tuning slots, 1.5 s, `--seed 9650`): the current candidate C (R2 if rule 6 made one, else Splitter-R) against `C:desperate_p=0.1`. Kept if the paired difference is positive; the candidate with it then takes R2's place in rule 7 (same test: beat Splitter-R on the fresh maps and be above 2 SE against the flagship on stage 3 alone).

## 16.4 Results

### Stage 0: the rollout-depth gate (no code)

`python -m arena.run --bot Splitter "Splitter:rollout_depth=4" "Splitter:rollout_depth=8" --slots arena/slots/tuning.json --drop-worse --time 1.5 --hard 2.0 --workers 3 --seed 9300`
(60 paired games per variant on the tuning slots, 73 minutes; 3 workers after a CPU check).

| Variant | Paired Δ vs flagship | By opponent |
|---|---|---|
| Rollout depth 4 everywhere | **+1.7 ± 5.0** | Expecti +25.0, Snap:v7 +6.2, Apex −4.2, RaceMCTS −5.6 |
| Rollout depth 8 everywhere | **+0.8 ± 6.7** | Expecti +25.0, Snap:v7 +15.6, Apex **−20.8**, RaceMCTS −16.7 |

- **Gate passed** (rule 1): neither depth is clearly worse at 1.5 s. At 0.1 s depth 4 had cost 6 points; with 15 times more thinking time that cost is gone.
- **Uniform depth cuts both ways:** depth 8 gains a lot against some opponents and loses a lot against others. This supports the merger study's design: deep rollouts **only in contact**, where tactics decide (`rollout_depth_contact`).
- 0 timeouts, 0 illegal moves; slowest move 1.52 s.

### Stage 1: the merger and its ablations (tuning slots, 1.5 s)

Five configurations in one paired pool, 60 games each, 133 minutes at below-normal CPU priority
(3 workers), `--seed 9400`. "Rollout half" = race rollouts, first strikes at 45%, depth 6 in
contact, leaf mixing 0.5; "speed half" = trusted plans, transposition cache, tree reuse.

| Variant | Paired Δ vs flagship | Notable |
|---|---|---|
| R-full (everything) | −0.8 ± 7.4 | Apex **+16.7 ± 7.1** |
| R without the rollout half | −0.8 ± 6.8 | frozen flagship −18.8 |
| **R without the speed half** | **+5.8 ± 7.8** | Apex **+20.8 ± 7.4**, frozen flagship +18.8, TacticalSplitter −37.5 (4 games) |
| R without the root plans | −1.7 ± 6.6 | |

- No variant is clearly better or worse overall: with 60 games one standard error is about 7 points.
- **Consistent signal:** every variant with race rollouts beat the plain Apex (+8 to +21). Deep, dice-driven rollouts in contact help most against an alpha-beta deathball.
- **Timing warning:** with deep rollouts the slowest move reached 1.64 s (one long rollout ran past the 1.5 s deadline). Fixed afterwards: race rollouts now stop at the deadline.

### Mechanism check: iterations per move (5 mid-game positions, 1.5 s, one core)

| Configuration | Iterations per move | Cache hits | vs flagship |
|---|---|---|---|
| Flagship | 4,778 | 0 | — |
| R without the speed half | 3,462 | 0 | −28% |
| R with trusted plans + cache | 3,544 | 1,455 | −26% |
| R with trusted plans only | 3,420 | 0 | −28% |
| R with cache only | 3,597 | 1,495 | −25% |

- **The speed half does not speed anything up:** +2 to +4% iterations at most. The cache hits often, but its key (a sorted copy of the board) costs about what a hit saves; skipping redundant legality checks changes nothing measurable (their share was inflated by the old profiler run). With no mechanism, the speed half is dropped.
- **Splitter-R's real cost is thinking time:** deep rollouts and the second leaf evaluation cost about 28% of the iterations, 65% on the big village map (1,377 vs 3,899). This is the weakness the next iteration works on.
- The flagship really runs about **4,000 to 9,000 iterations per move**, 5 to 10 times the profiled figure quoted in the code review.

**Decision (rule 2):** the candidate is **Splitter-R = rollout half + root plans + anti-bait check**,
registered as `MODELS["r"]` (arena name `Splitter-R`, tournament `SPLITTER_MODEL=r`), with the new
deadline guard on race rollouts.

### Stage 2: validation (hold-out slots + the live bots, 1.5 s)

`python -m arena.run --bot Splitter Splitter-R --slots arena/slots/c3_validation.json --drop-worse --games 1 --time 1.5 --hard 2.0 --workers 3 --seed 9500 --out arena/results/c3_stage2.csv`

The slot file is the 41 hold-out slots (RaceMCTS, Expecti, Apex, Styled:1 to 6) plus the three
live bots on all 8 hold-out maps: 65 slots, 260 games. The teammates' code was re-fetched just
before (no new pushes since 22 October). This run plays the Splitter-R of stage 1; the rollout
speed-up of iteration 2 (below) came after it started and does not change decisions.

139 minutes (3 workers). **Splitter-R +6.2 ± 4.6 over the flagship (130 paired games): positive, rule 3 passed.**

| | Score | Wins | Draws | Losses | vs the live bots (Apex / RaceMCTS / Expecti) |
|---|---|---|---|---|---|
| Flagship | 56.5% ± 4.3 | 60 | 27 | 43 | 84.4% / 56.2% / 75.0% |
| **Splitter-R** | **62.7% ± 4.2** | **79** | **5** | 46 | 87.5% / 62.5% / 65.6% |

| Paired Δ (R − flagship) by opponent | Games | Δ |
|---|---|---|
| Styled:4 | 10 | **+35.0 ± 15.0** |
| Styled:6 / Styled:1 / Styled:3 | 14 / 4 / 14 | +17.9 / +25.0 / +10.7 (each within 2 SE) |
| RaceMCTS-live / Styled:5 / Apex-live | 16 / 10 / 16 | +6.2 / +5.0 / +3.1 |
| Expecti-live / RaceMCTS (old preset) / Styled:2 | 16 / 10 / 12 | −9.4 ± 14.6 / −10.0 ± 23.3 / −8.3 ± 14.9 |

- **How R gains: it turns draws into wins.** 27 flagship draws become 5; R wins 19 more games and loses only 3 more. The race rollouts (with first strikes) make it play for the win when the flagship settles for a standstill.
- **The gain is largest against a style no teammate plays:** Styled:4 is a gambler (it strikes whenever adjacent, hunts hard, splits one detachment at a time). The flagship scored only 15% against it; R +35. The race rollouts, where both sides strike first, model such a bot far better than the flagship's 2-ply rollouts. So the gain does not come from fitting the teammates' bots.
- **Moving second is the common weak spot:** with one game per slot the Vampires always moved first; as Werewolves (moving second) the flagship scores 47.7% and R 50.8%, against 65.4% and 74.6% moving first.
- **To watch in stage 3:** Expecti-live, the only live bot where R scores lower (−9.4, within noise).
- 0 timeouts, 0 illegal moves; slowest move 1.54 s (the deadline guard holds; the flagship's slowest 1.60 s).

## 16.5 Iteration 2: weaknesses found and what was built

### Where Splitter-R's thinking time goes (profile, 4 positions, 1.5 s per search)

| Piece | Flagship share | Splitter-R share | Calls per iteration (flagship / R) |
|---|---|---|---|
| Rollout policy (`quick_plan` / `race_rollout_plan`) | 18% | **35%** | 1.9 / 4.4 |
| Plan generation | 30% | 22% | |
| Legality checks | 24% | 17% | |
| Leaf evaluation | 8% | 8% | 1.0 / 2.0 |

- **The cost is the deep rollouts, not the leaf mixing:** the second evaluation is cheap (8% in both). Most leaves count as "in contact" (an enemy group within 3 cells), so most rollouts run 6 plies.
- **Fix, decisions unchanged:** `race_rollout_plan` rewritten to keep only the best two goals (it sorted them all), inline the distances and list the sure-killers once per group. Same moves and same random draws on 1,896 real positions and on 500 random ones (unit test), and the **same decisions on 300 of 300 positions** under a fixed clock. Per call 74 to 49 µs; **+9% iterations per move** (+15 to 28% on the big village map). The flagship's code is untouched (still 300/300 identical to the frozen v7).

### Two tactical gaps that apply to any opponent

- **No first strike at good odds unless losing.** With `gamble="adaptive"`, our planner proposes a strike that is not a sure kill only when its evaluation is under 0.35 or it is behind late in the game. Yet 13 against 10 wins 80% of the time (expected loss about 5 of ours for 10 of theirs), and waiting lets the enemy strike us at 38%. These situations are rare but decisive: **1.2% of positions** from 28 arena games (14 maps, against our own bot and RaceMCTS; about 2 or 3 per game, always in contact fights). Built: the `strike_p` option (cost: 1.5% of the iterations).
- **The tree's opponent is always our own cautious planner.** Bolder bots (RaceMCTS-style whole-group moves, unsafe splits) never appear among the replies we search. Built: the `opp_race` option, only for the opponent's first reply (cost: 7% of the iterations).

Both are off by default; their screen and how a modified candidate is judged are rules 6 and 7 in 16.3.

## 16.6 Iteration 3: what the stage-2 losses show

Splitter-R wins more, but **it loses by being wiped out**: 39 of its 46 losses are wipeouts (the
flagship: 26 of 43), and in the 20 slots where it did worse than the flagship, 16 ended with R
wiped out, some early (ply 34). Two causes, from the logs of the games not won
(`arena/results/logs/20261024-190540_Splitter+Splitter-R`):

| After our move, one of our groups stands next to an enemy that... | Flagship (5,057 moves) | Splitter-R (2,545 moves) |
|---|---|---|
| kills it for sure | 0.6% | 2.7% |
| beats it at 50 to 99% | 0.2% | **8.4%** |
| beats it at 30 to 49% | 0.6% | 2.0% |
| beats it at 1 to 29% | 1.5% | 4.7% |

1. **More first-strike exposure.** Replaying 4 hold-out games (R vs the flagship, 0.5 s) and recording the plan behind every exposed move: the RaceMCTS-style root plans leave a group within a 50%+ strike on 14 to 25% of the moves they are chosen for (`race:base`, `race:split`; our own base plan: 0.5%). RaceMCTS's step rule only avoids enemies 1.5x bigger, and that came in with the plans. Most other exposures happen when R is already behind, where a gamble is rational.
2. **A blind spot shared by both models: the desperate opponent.** Example (ho_11x11, ply 33): R leads 40 to 26, no humans left, and steps its 40 next to an enemy 17 that it would kill for sure next turn. The 17 strikes first at **21%, wins, and wipes R out**. Neither model sees this: the tree's opponent only gambles from 30%, the evaluation's exposure term starts at 30%, R's rollouts at 45%. Yet for a losing opponent any chance beats a sure loss, and a smart one (here Expecti's expectiminimax) takes it. Strikes under 30% destroyed at least half our army in 5 of R's lost games and 2 of the flagship's, all by Expecti. Re-run on that exact position: **the flagship and R both step next to the 17 in 6 of 6 searches.**

**Built: `desperate_p` (one value, 0.1, from the observed killing strikes at 11 to 27%; no tuning).**
When our evaluation says the opponent is losing (value ≥ 0.65, or the last 20 plies with more
material: the mirror of our own "behind" rule), the opponent is modelled as rational as we are:

- the tree's opponent gets gamble plans from these odds (`PlanConfig.gamble_p`, normally 0.3);
- our planner treats cells next to such enemies as dangerous from these odds and flees from them (`danger_strike_p`, `threat_p`);
- the evaluation counts the opponent's strikes from these odds (`EvalParams.opp_strike_p`, normally 0.3);
- in R's race rollouts, the opponent strikes from these odds.

On the ply-33 position, both models then stay out of reach in 6 of 6 searches (a unit test now
checks it). Off by default: the references are unchanged (300/300 and 244/300 identical
decisions to the frozen v7). The race root plans' exposure (cause 1) is left to the search for
now: they are also where R's gains against deathball bots come from.
