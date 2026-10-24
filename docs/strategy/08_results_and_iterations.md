# 08 · Results and iteration history

All numbers come from [arena/run.py](../../arena/run.py) (chapter 07): both species, the first
player alternating, and fixed seeds. Win = 1, draw = 0.5. "±" is one standard error.

## 8.1 Full benchmark: Splitter v5 vs the team's bots

Command: `python -m arena.run --maps all --games 2 --time 0.2`. That is 8 opponents × 14 maps × 2
species × 2 games = **448 games per row**. The ablation uses the same seeds.

| Opponent | **Splitter** | Splitter-nosplit (ablation) |
|---|---|---|
| Apex (Othmane, alpha-beta, keeps one big group) | 78.6% | 82.1% |
| RaceMCTS (Ronita, MCTS) | **66.1%** | 53.6% |
| Expecti (Dana, expectiminimax) | **68.8%** | 56.2% |
| TacticalSplitter (Othmane, rule-based splitter) | **91.1%** | 77.7% |
| Grabber / Greedy / Starter / Rusher | 77% / 74% / 80% / 98% | 73% / 75% / 79% / 98% |
| **Overall** | **79.1% ± 1.9** | 74.3% ± 2.1 |
| Average final margin (creatures) | **+20** | +9 |
| Illegal moves / timeouts / crashes | 0 | 0 |

**By map family (Splitter vs no-split):**

| Maps | Splitter | No-split |
|---|---|---|
| Many villages (vil_10x16, vil_13x21, vil_15x25) | **91–94%** | 69–78% |
| Open symmetric (sym_*) | **75–97%** | 70–81% |
| prize_11x17 / testmap / close_8x12 | 63% / 75% / 59% | **88% / 86% / 69%** |

**Conclusion on the hypothesis "smart splitting collects humans faster":**
- **Confirmed overall,** and strongly on maps with many small houses.
- **The deathball is better when one huge house or a nearby enemy demands concentration** (prize and close-start maps).
- The hybrid rules that try to detect those cases did not beat the plain Splitter (8.4).

**The current flagship (v6 = v5 + the open-loop search fix)** scores **79.3%** against a
9-opponent panel that includes the frozen v5 (504 games, 0.2 s), and **61.6%** head-to-head
against v5 (chapter 11.8).

## 8.2 Tournament speed and the real server

**Validation of the kept strategies at 1.5 s per move (2026-10-20).** Command:
`python -m arena.run --bot Snap:v7 "Snap:v7:opponent_model=1" --opp RaceMCTS Expecti Apex --maps given,villages,prize,close --games 1 --time 1.5 --hard 2.0 --workers 4 --seed 9000`.
That is 3 opponents × 9 maps × 2 species = 54 paired games per strategy, every bot at 1.5 s, 4
workers on 8 cores so that no bot shares a core. The no-split ablation was run afterwards with the
same seeds (`--bot "Snap:v7:splits=0"`), and paired from the stored CSVs.

| Opponent | **Splitter** (flagship) | Splitter-HMM (runner-up) | Splitter-nosplit (ablation) |
|---|---|---|---|
| Apex | **86.1%** (14 W, 3 D, 1 L) | 72.2% (−13.9 ± 6.8) | 80.6% (−5.6 ± 9.8) |
| Expecti | **83.3%** (13 W, 4 D, 1 L) | 80.6% (−2.8 ± 6.4) | 55.6% (−27.8 ± 10.9) |
| RaceMCTS | **66.7%** (12 W, 6 L) | 38.9% (−27.8 ± 10.9) | 44.4% (−22.2 ± 15.2) |
| **Overall** | **78.7% ± 5.6** | 63.9% ± 6.5 (**−14.8 ± 4.9**) | 60.2% ± 6.7 (**−18.5 ± 7.0**) |
| Timeouts / illegal / crashes | 0 | 0 | 0 |
| Slowest move | 1.51 s | 1.51 s | 1.50 s |

(In brackets: the paired difference with the flagship on the same games.)

- **The flagship holds its level at tournament speed** (78.7%; 79.3% against the larger 9-opponent panel at 0.2 s).
- **Splitting matters even more at tournament speed:** the deathball loses 18.5 points (5 points at 0.2 s, 8.1). This confirms the project's hypothesis where it counts. The earlier small sample against RaceMCTS (3 W, 5 L in 24 games) was noise: 12 W, 6 L here.
- **The runner-up is clearly worse at 1.5 s** (3 standard errors). Its code was checked against the measured version (commit `79fd09c`): with search steering off, the two are identical, so this is a real effect, not a clean-up bug.
- **Hypothesis:** its risk relaxations (counting 30–50% threats only at ≥ 50% against "careful" opponents, a smaller reserve radius against passive ones) are cheap at 0.2 s, when opponents search shallowly. With 1.5 s, RaceMCTS and Apex search deep enough to punish them. This is consistent with lesson 12.3: the gain at 0.2 s never replicated on unseen data.
- **Ranking at 1.5 s:** flagship > runner-up > deathball.
- **Consequence:** the flagship is the only configuration recommended for the tournament.
- **Follow-up (campaign 2, chapter 14):** a second 1.5 s run confirmed the runner-up's deficit (−4.8 ± 7.7; pooled −11.9 ± 4.1). It was retired and replaced as the backup by the calibrated evaluation, "Splitter-Calibrated" (+1.3 ± 6.1 at 1.5 s, statistically equal to the flagship).

**Campaign 2 at 1.5 s** (hold-out slots, chapter 14.3):

| Run | Flagship | Calibrated evaluation | Other |
|---|---|---|---|
| Stage C (RaceMCTS, Expecti, Apex, Styled:1–3; 48 games) | 53.1% | 58.3% (+5.2 ± 8.5) | half the thinking time: 31.2% (**−25.0 ± 10.9**) |
| Stage D, pre-registered (RaceMCTS, Expecti, Apex, Styled:4–6; 52 games) | 51.0% | 48.1% (−2.9 ± 8.9) | Splitter-HMM: 46.2% (−4.8 ± 7.7) |

(Win rates on informative slots are lower than on the full panel by design: only contested games
are played, chapter 07.8.)

**Real server** (official exe, `MaxPlayDuration` = 2 s):
- `main.py` (Splitter) against Apex (through `tools/play_bot.py`) on testmap.xml;
- 200 plies, **won 18 – 14**, no cheating or timeout entries in the server trace, slowest move 1.48 s.

**Real-conditions matches against the teammates** ([tools/teammate_matches.py](../../tools/teammate_matches.py),
chapter 07.5; 2026-10-21): the flagship through `main.py`, the real protocol (2 s per move,
200 plies, 5-minute clock), 1.5 s per move for every bot, one game at a time, no speed-ups.
11 of 12 planned games (the run was stopped during Expecti's game 3). Full table, game by game:
`arena/results/teammates/20261021-161347_flagship/summary.md`.

| Opponent (teammate) | Games | W - D - L | Score | Avg. margin |
|---|---|---|---|---|
| Apex (Othmane) | 3 | 3 - 0 - 0 | 100% | +6.0 |
| TacticalSplitter (Othmane) | 3 | 3 - 0 - 0 | 100% | +3.7 |
| RaceMCTS (Ronita) | 3 | 2 - 0 - 1 | 67% | +4.3 |
| Expecti (Dana) | 2 | 1 - 1 - 0 | 75% | +1.5 |
| **All** | **11** | **9 - 1 - 1** | **86%** | **+4.1** |

- **Safety:** 0 illegal or empty moves, 0 dropped connections, 0 watchdog fallbacks. Slowest move 1.50 s, except **one 9.3 s move** in Apex game 1 (won anyway). It was a normal agent answer, not a watchdog fallback, and Apex also timed out once in that game, so the whole process (watchdog included) appears to have been frozen, most likely by a stall of the machine.
- **By side:** as Vampires (moving first) 7 wins and 1 draw in 8 games; as Werewolves 2 wins and 1 loss in 3 games (the loss: RaceMCTS on testmap).
- **Sample size:** 11 games give about ±10% per opponent group; this is a check of real-conditions behaviour, not a precise strength estimate (chapter 14 has those).
- An earlier run of the same day (79%, since deleted) was superseded: its schedule tied each map to one side (fixed since).

## 8.3 Iteration history: every change came from a lost game

| Version | Change | Lost game that motivated it | Measured effect |
|---|---|---|---|
| v1 | Baseline: planner + MCTS + race evaluation | none | 81% vs the panel (84 games), 100% on villages |
| v2 | **Merge-aware race** ([`project_race`](../../splitter/evaluate.py#L68)), **commitment** (`commit_bonus`), **pincer** ([`_pincer_orders`](../../splitter/planner.py#L564)) | prize_11x17: our 19 creatures were split 12 + 7 while Apex took the 18-house and hunted us | prize map won vs Apex as both species; 82.7% overall |
| v3 | **The opponent model may strike at P ≥ 0.3** (`gamble="always"` in the tree); exposure counts those strikes; **evaluation steepness grows with game progress** | testmap: we stepped our 16 next to RaceMCTS's 14, it struck first at 44% and won. thetrap: same, at 35% | |
| v4 | **Protected plans** (`PROTECTED`); **flee into open space** ([`flee_cell`](../../splitter/planner.py#L217)) | vil_10x16: with 6 groups the only `flee` plan was truncated and a group was eaten; chased groups died in corners | Apex 73% → 92%; v4 beat v3 head-to-head (12 W, 8 D, 4 L) |
| v5 | **Contest-aware race** ([`_contest`](../../splitter/evaluate.py#L122)), **reserve radius 6**, stronger house penalty near big enemies, planner caches (×4 speed) | close_8x12: splitting 8 into 3 + 5 next to the enemy fed it every house | RaceMCTS 48% → 72% (108-game set); 79.1% on the full 448-game set |
| v6 | **Open-loop expansion fix:** a plan is checked before being expanded in a sampled future (chapter 11.8) | Found while integrating the opponent model: 4.1% of turns crashed the search and played the fallback move | **+2.2 pts** overall, **61.6%** head-to-head vs v5; RaceMCTS 66% → 73%, Expecti 69% → 81% |
| v6 | HMM opponent model, goal recognizer, policy HMM, search steering, pre-emptive plans, adaptive settings, pre-game analysis, map-aware deathball, kiting, parameter screening (chapters 11, 12) | — | None replicated on unseen data. The best one (style HMM risk model + adaptive settings) became the runner-up "Splitter-HMM" (retired in v8) |
| v7 | **Clean-up** (2026-10-20): every rejected experiment deleted from the code (preserved in commit `79fd09c`); external-bot loading, server matches between any two programs, stored result history; Pylance and Ruff clean | — | Flagship behaviour unchanged (v6 defaults) |
| v8 | **Campaign 2** (2026-10-21, chapter 14): 17 ideas from chapter 13 plus new ones (search, caching, path planning, swarm, prediction, evaluation fitting, game clock); watchdog in `main.py`; faster testing (informative slots, early stopping, resume) | Lessons of campaign 1 (validate at 1.5 s, unseen data) | No idea beat the flagship reliably. The calibrated evaluation becomes the backup; Splitter-HMM is retired. The flagship is decision-for-decision identical to v7 (300/300); 37 tests pass |

## 8.4 Ideas tested and rejected in campaign 1 (switches deleted from the code unless noted)

The complete register of both campaigns, with reasons and retry conditions, is
[15 · Failed strategies](15_failed_strategies.md).

| Variant | Result | Why rejected |
|---|---|---|
| `light_tree=True` (fewer plans below the root) | vs RaceMCTS 35% vs 48% | A weaker opponent model outweighs the extra iterations |
| Planner caches alone (4× more iterations) | 50% vs v4 head-to-head | Caches kept (time safety margin), but speed was not the bottleneck |
| `reserve_radius=10` | vs RaceMCTS 42% vs 72% | Too timid: hardly ever splits |
| `gamble="always"` for our own plans | 58.3% vs 60.4% (adaptive) | No gain (the option stays; `adaptive` is the default) |
| `split_enemy_dist=6` | 77.3% vs 79.1% (448 games) | Gain on 96 games was noise |
| `split_enemy_dist=4` | 76.3% vs 79.1% | Worse |
| `prize_lock=True` | 64.1% vs 64.1% | No effect |
| Opponent model steering the search (I1, PUCT priors) | RaceMCTS −9 | Under-explores dangerous replies (chapter 11.7) |
| Pre-emptive plans (deny, ambush, shield, tempo) | −3.9 pts | Chapter 11.7 |
| Map-aware deathball | −3.9 pts | Chapter 11.7 |
| Longer first move / `--pregame` | −4.7 pts | Chapter 11.7 |
| Endgame kiting (+ rollout depth 0) | +11.3 tuning, −0.6 hold-out | Over-fitting caught by the hold-out set (chapter 12) |

## 8.5 Next steps

See [13 · Future improvements](13_future_ideas.md).
