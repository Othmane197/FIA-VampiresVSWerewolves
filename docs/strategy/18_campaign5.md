# 18 · Campaign 5: more thinking time, Harsha's MCTS, and the strongest version

**Goal:** (1) test optimization 1 of 17.5, more thinking time per move; (2) review the newest
teammate MCTS (Harsha's, pushed 28 October), compare it with our flagship and merge what
complements it; (3) keep only the best model as the flagship and verify, on data nothing was
selected on, that it is the strongest version we have produced; (4) study the non-MCTS bots for
ideas (18.6).

**References:** the flagship `Splitter` (Splitter-R3) and the backup `Splitter-Classic`; earlier
generations for the final ladder: `Snap:v5fix` (campaign 1's v5 baseline) and the Classic (= v7,
campaign 2's flagship).

## 18.1 Harsha's MCTS against ours (from reading the code)

Harsha's `ai_agent.py` (branch `Harsha`, commit 88600de) is, in its own words, rebuilt "around the
pattern that beat it in testing (Ronita's approach)": RaceMCTS's whole-turn plans and race
evaluation, plus **root parallelism**.

| Part | Harsha | Our flagship (Splitter-R3) |
|---|---|---|
| Rules model | the starter kit's `game_engine.BoardState` | our exact copy of the server (`splitter/rules.py`) |
| Root plans | RaceMCTS families: all groups to their best goal, one group on its 2nd/3rd goal, regroup, whole-group splits to two houses (max 12); steps avoid only enemies 1.5x bigger | our planner (exact-size safe detachments, flee, hunt, pincer, strike, gamble when behind) **plus** the same race families (`race_plans`) |
| Opponent in the tree | the same plan generator | our planner, gambling from 30% (10% when desperate) |
| Rollouts | race policy, ε = 0.15, **8 plies at every leaf**, no first strikes | race policy with first strikes from 45%, 6 plies in contact, 2 elsewhere, leaf mixing 0.5 |
| Evaluation | race projection (no merges, no contests, no exposure), `ours / (ours + theirs)`, 1.5x bonus | race projection with merges and contest factors, exposure, a sigmoid that sharpens late, 1.5x bonus |
| Selection | plain UCT, **c = 0.9**, untried plans in random order | UCT c = 0.6 + planner priors (progressive bias) + progressive widening |
| Time and cores | 1.4 s on **every core but one** (7 independent trees here, visit counts summed) | 1.5 s on one core (a project rule) |

**Strengths:** many more simulations per move (root parallelism scales almost linearly in
iterations); long rollouts everywhere; a simple, robust plan list.
**Weaknesses:** the starter kit's battle model (it treats a defender 1.5x bigger as a sure defence,
which the server does not), no split safety (whole-group splits walk into enemy reach), no
exposure in the evaluation (it ignores first strikes), no strikes or gambles in its plans, no
priors (it spends visits on bad plans), and it needs the cores: one tree alone is RaceMCTS with
fewer features.

**What could complement ours** (parallelism is excluded by the project rule):
1. **8-ply rollouts in contact** (`rollout_depth_contact=8`, ours: 6).
2. **More exploration** (`c=0.9`, ours: 0.6; screened only on the campaign-1 bot, never on R3).

Everything else Harsha has, our flagship already has (campaign 3 merged RaceMCTS).

## 18.2 Data and opponents

- **Harsha in the arena:** `Harsha-1core` runs one of Harsha's trees in-process with its own settings (its process pool cannot run inside the arena). Its full multi-core client is measured over the real protocol (run D2), from a copy of his branch whose pool is capped at 3 processes (`HARSHA_CORES`; the original uses all cores but one), so that the laptop stays usable.
- **Othmane's Apex V3.1** (25 October, "dynamic multi-splitting, battle EV correction and horizon calibration") is the current `Apex-live`.
- **New data:** map families **`fresh3`** (validation) and **`fresh4`** (final ladder), 8 maps each, seeds 401–408 and 501–508; styles **Styled:19–24** (validation) and **Styled:25–30** (ladder). None was used before.

## 18.3 Decision rules, written before the games

1. **D1, diagnostic** (no decision): the flagship and the backup against `Harsha-1core` and `Apex-live` (V3.1) on the 14 tuning maps, both sides, 1.5 s, `--seed 14000`.
2. **D2, diagnostic** (no decision): the flagship's real client (`main.py`) against Harsha's real client (3 processes) over the real protocol (`tools/server_match.py`), testmap and thetrap, 2 games per map and connection order (8 games).
3. **Screen S** (tuning slots, 1.5 s, `--seed 11000`, `--drop-worse`): `Splitter` against `Splitter:time_limit=1.7` (optimization 1), `Splitter:rollout_depth_contact=8` and `Splitter:c=0.9`.
4. **Selection:** a component is kept if its paired difference to the flagship is positive. One kept: it is the candidate. Two or more: two candidates, the combination of all kept components and the best single one.
5. **Validation V** (`fresh3`; Apex-live, RaceMCTS-live, Expecti-live, Harsha-1core, Styled:19–24; both sides; 1.5 s; `--seed 12000`; no early stopping): the flagship and the candidates (160 games each).
6. **Adoption:** a candidate qualifies if its validation difference is positive, its screen and validation games pooled are above 1.5 SE (the combination, which has no screen games, on its validation games alone), and it has 0 timeouts and 0 illegal moves. Of the qualifying candidates, the one with the larger validation difference becomes the new flagship.
7. **Real conditions R:** the adopted candidate plays `tools/teammate_matches.py` (4 games against each of Apex-live, RaceMCTS-live, Expecti-live, Harsha-1core; `--time 1.7` if it thinks longer). Any timeout or illegal move cancels the adoption. Watchdog answers (late searches) are reported.
8. **Ladder L, the "strongest version" check** (`fresh4`; the three live bots, Harsha-1core, Styled:25–30; both sides; 1.5 s; `--seed 13000`; no early stopping): the final flagship, the current flagship (if they differ), the Classic (v7) and `Snap:v5fix`. The final flagship is "the strongest version we produced" if its paired difference to each earlier generation is positive on this data; the result is reported as measured, whatever it is.

## 18.4 Results

Run unattended on 31 October, 04:32 to 13:05 (`c5_run.py` in the session scratchpad, every step
at below-normal priority, 3 workers). No timeout, illegal move or crash in any game of any bot.
CSVs: `arena/results/c5_{d1,screen,ladder}.csv` and
`arena/results/server_matches/20261031-060503_Splitter_vs_Harsha.csv`.

### D1: both models against Harsha (one core) and Apex V3.1 (tuning maps, 112 games; no decision)

| Bot | Harsha-1core | Apex-live (V3.1) |
|---|---|---|
| **Splitter** (flagship) | **71.4%** | **80.4%** |
| Splitter-Classic (backup) | 53.6% | 67.9% |
| Flagship − backup (paired) | +17.9 ± 10.4 | +12.5 ± 8.4 |

On one core, Harsha's tree is RaceMCTS with fewer features, and the flagship, which already
contains RaceMCTS's strengths, beats it clearly. The backup (no race rollouts) is nearly level with it.

### D2: the real clients over the real protocol, Harsha with 3 processes (8 games; no decision)

**4 – 4 (50.0% ± 17.7)**, 0 timeouts and 0 cheats on both sides. testmap 3 – 1, **thetrap 1 – 3**.
With three trees (about 3× our iterations), Harsha's client is level with ours. Since thetrap
was the only map it won, we replayed it afterwards (12 arena games with full logs, seed 15000;
diagnostic). The flagship went 0 – 1 – 5 against Harsha-1core and 3 – 0 – 3 against RaceMCTS-live.
Three mechanisms:

1. **Moving second on thetrap is a coin flip by design.** The first player steps next to the 4-human house and next to us. Equal 4 against 4, we must strike at 50% before it converts. Both D2 games as the second player ended at ply 2, one won and one lost.
2. **The 18-ply line.** Harsha plays the same line every game: splits 2 + 2 to the right-hand houses, merges to 7, and waits next to the last house of 2. Our 8 then chooses between striking first (64%) and taking the house to 10 against 7 (it strikes back at 35%): about 65% either way. This repeats the campaign-3 thetrap loss (16.7).
3. **The 35-ply line: a real weakness (see 18.6, item 1).** We split 8 into 6 + 2 at ply 6 to race for the right-hand houses, which Harsha's 4 reaches first; it converts all 5 humans and becomes 9. With no humans left, 9 ≥ 1.5 × 6: our 6 can be killed for sure, while our merged 8 could not be. Our groups stayed side by side for about 15 plies without merging, until the 6 was cornered and struck at 33% out of desperation. In the position after ply 15, the search rates staying split at 0.36 and merging into one 8 at 0.11 to 0.29. In reality the split is lost: one bigger pursuer always corners a single group on a king-move board, while the merged 8 keeps about 40% from the first strike when contact comes. Our rollouts (6 plies) end long before the 6 is cornered.

### Screen S: the flagship against its three variants (tuning slots, 1.5 s, early stopping; rules 3 and 4)

| Variant | Paired difference to the flagship | Games | Avg / slowest move | Kept? |
|---|---|---|---|---|
| `time_limit=1.7` (optimization 1) | −7.5 ± 5.7 | 60 | 1.46 / 1.73 s (flagship 1.23 / 1.51 s) | no |
| `rollout_depth_contact=8` (Harsha) | −11.7 ± 6.5 | 60 | 1.28 / 1.68 s | no |
| `c=0.9` (Harsha) | −17.8 ± 7.5 | 45 (dropped) | 1.36 / 1.51 s | no |

**Nothing was kept, so by rules 4–7 there was no validation, no adoption and no real-conditions
run.** Likely reasons:

- **More time.** The variant really thought longer (1.46 s on average against 1.23 s), but +13% of the iterations is worth only a few points at most: halving the time cost 25 points (14.3), and the gain per extra iteration shrinks as time grows. That is below what 60 games resolve, and the estimate came out negative. It would also have cut the margin to the server's 2 s limit (the slowest move was 1.73 s).
- **8-ply contact rollouts.** They cost iterations, and their effect depends on the opponent (Expecti −40, Apex −17, RaceMCTS 0), as with the uniform depths of campaign 3 (16.4).
- **c = 0.9.** Our planner priors already steer exploration. More exploration spends visits on bad plans, which Harsha (with no priors) has to do anyway. It also lost on the campaign-1 bot (10.3).

### Ladder L: the "strongest version" check (`fresh4`, Styled:25–30, 480 games; rule 8)

| Bot | Score | Final flagship minus this bot (paired) |
|---|---|---|
| **Splitter** (flagship, unchanged) | **68.4%** | — |
| Splitter-Classic (v7, campaign 2) | 63.1% | **+5.3 ± 4.0** |
| `Snap:v5fix` (v5, campaign 1) | 63.1% | **+5.3 ± 4.5** |

**By rule 8, the flagship is the strongest version we produced**: its difference to each earlier
generation is positive on data nothing was selected on. On this data alone the margin is small
(about 1.3 SE). Two further readings make the picture precise:

- **Over three untouched map families, the flagship beats the backup at about 3 SE.** Campaign 3's final (`fresh`), campaign 4's validation (`fresh2`) and this ladder (`fresh4`) give +8.0 ± 3.9, +9.0 ± 4.9 and +5.3 ± 4.0. Inverse-variance pooled: **+7.2 ± 2.4**.
- **The margin comes from the styled opponents, not from the live bots.** Against Apex-live, RaceMCTS-live, Expecti-live and Harsha-1core, flagship − backup was −6.2 ± 6.5 on this ladder (−0.8 ± 8.1 against v5). Pooled over the three families it is +2.1 ± 3.9 against the live bots and +10.1 ± 3.0 against the styled ones. Against the teammates' intelligent bots, the flagship is not measurably stronger than the backup. The endgame weakness of D2 (18.6, item 1) is a candidate reason: on this ladder the flagship lost 25 groups to it, the backup 7.

The slowest move of the ladder was 1.84 s, by the flagship in one game out of 160. From 12:14
on, another project's jobs were running on the same machine. That is still under the 2 s limit,
and the tournament client's watchdog answers at 1.8 s.

## 18.5 Conclusion

- **Flagship and backup are unchanged:** `Splitter` (Splitter-R3) and `Splitter-Classic` (v7). No code of either model changed in this campaign; the 48 tests pass (1 expected failure, the known tempo puzzle).
- **Optimization 1 (more thinking time) does not pay.** 1.7 s gave −7.5 ± 5.7 on the screen. The 1.5 s default stays, with its 0.5 s margin under the server's limit.
- **Harsha's MCTS:** strong because of its cores, not its design. On one core the flagship scores 71.4% against it; against its 3-process client it is level (4 – 4). Its two settings that could have complemented ours (8-ply contact rollouts, c = 0.9) both lost on the screen. The one thing it does that we lack is parallelism, which the project rules exclude.
- **"The strongest version we can achieve"** cannot be claimed. What the data shows: the flagship is the strongest version **measured** (positive against every earlier generation on untouched data, and +7.2 ± 2.4 against the backup over three untouched families). Every cheap lever tried in campaigns 4 and 5 (time, rollout depth, exploration, small rule fixes) failed to improve it. Further gains need a new mechanism aimed at how it loses to intelligent bots; the measured candidate is 18.6, item 1.

## 18.6 The non-MCTS bots: what they do that we do not, and a plan to merge it

Read from the code (branches of 25–31 October): Othmane's **Apex V3.1** (iterative-deepening
alpha-beta), Dana's **Expecti / SafeAgent** (depth-2 expectiminimax), and the simple bots
(Grabber, Rusher, Turtle; Greedy, PotentialField, ShallowMinimax, TacticalSplitter).

| Bot | Idea | Do we have it? |
|---|---|---|
| Apex V3.1 | Zobrist transposition table inside alpha-beta | Tried in MCTS (campaigns 2 and 3): positions rarely repeat on big maps, no gain |
| Apex V3.1 | **Transit pruning**: far from every enemy (4+ cells) and not next to a house, only moves that do not increase the distance to the target; branching ~2, so 10–14 plies deep in transit | No: our rollouts are 2 plies outside contact |
| Apex V3.1 | Battles resolved at their expected value in the search | We sample the exact outcome distribution (more faithful) |
| Apex V3.1 | Domination bonus only once no humans are left; 25-turn race projection | Partly: our 1.5x bonus applies to the projected sizes; a deferred bonus was noise in campaign 2 (`eval_dom_bonus`) |
| Apex V3.1 | Edge repulsion when fleeing; "coalition merger" when houses run out or a 1.5x threat is within 2 | Yes: `flee_cell` border term, protected `regroup` plans with threat urgency |
| Apex V3.1 | Group cap by map size (3 / 5 / 6) | Tried (campaign 2 `group_cap`): noise |
| Dana | **Pooled kill potential**: several groups next to one enemy add up to 1.5x (the server sums arrivals) | **No**: our exposure and step safety look at one enemy at a time, and our tree's opponent never pools a strike |
| Dana | Tempo term (houses both reach at the same time go to the side to move); smooth race | Yes: the 0.5-move head start and the discounted race projection |
| Dana | Expectiminimax with **chance nodes** over battle outcomes, depth 2 | No: our search samples dice; no exact short-range tactics |
| Dana | Three-tier legality gate (search, ranked candidate, brute force) | Yes: our safety net and watchdog |
| Rival bots | Potential fields, greedy reflexes, rushing, turtling, fragmentation and recombination | Covered as plan families or as styles we beat (Styled bots, chapter 14) |

**How often each gap decides something** (measured on all 1,612 of our groups destroyed in the
stored logs, before building anything, the lesson of campaign 4): groups lost to a **pooled**
attack that no single enemy group could have made: **7 (0.4%)**, mostly against Expecti, whose
generator pools by design. Coin flips in standoffs of equal armies decided a large share of the
backup's losses to RaceMCTS-live (17.4), and most lost games end in a wipeout after the house
race (16.6).

**Plan, ranked by expected gain against intelligent opponents per unit of work:**

1. **Contact solver with chance nodes** (Dana's expectiminimax, code review rank 4). For our groups within 2 cells of an enemy: enumerate strike / step away / hold / merge, score each with the exact battle-outcome distribution (`rules.win_probability` and binomial survivors) over 2–3 plies, opponent replies included, and add the best one or two as protected "contact" plans; MCTS still decides. *Reliability:* puzzles from the stored losses first (the 21% strike, the cornered 23-vs-23, the pooled kills), then a screen, a validation on an unused map family, real conditions; a hard time cap (abandon the solver past 20% of the budget).
2. **Transit depth** (Apex's transit pruning, translated to MCTS): in positions where no enemy is within 4 cells, roll out deeper (6 plies) with the cheap quick policy, since the branching there is tiny. *Reliability:* measure iterations per move first (a cost cap of 10%), then the usual screen and validation.
3. **Pooled threats** (Dana): count pooled enemy strikes in `exposure` and in `safe_step`'s danger, and let the tree's opponent plan pooled sure kills. *Reliability:* only after 1 and 2, since it acts in 0.4% of losses; puzzles first, then a large validation or a position-level test.
4. **Endgame solver** (Apex's alpha-beta): with no humans and at most 3 groups per side, a depth-limited exact search replaces MCTS. *Reliability:* compare with MCTS on stored endgame positions before any game.

Each item goes through the method of campaigns 3–5 (rules written first, tuning screen, a new
map family for validation, the 1.5 SE bar, real conditions), with the flagship's frozen
decisions checked after every change.
