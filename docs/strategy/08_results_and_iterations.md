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
- The hybrid rules that try to detect those cases did not beat the plain Splitter (8.3).

## 8.2 Tournament speed and the real server

**1.5 s per move for every bot** (24 games: Apex, RaceMCTS, Expecti × 4 maps × 2 sides):

| Opponent | Result |
|---|---|
| Apex | 7 W, 1 L |
| Expecti | 4 W, 4 L |
| RaceMCTS | 3 W, 5 L |

- **Our bot was always safe:** 0 timeouts and 0 illegal moves; the slowest move took 1.54 s.
- **The sample is small** (±17% per opponent), but RaceMCTS seems to gain more from extra time than we do. Running about 100 games at this speed is the most useful next measurement.

**Real server** (official exe, `MaxPlayDuration` = 2 s):
- `main.py` (Splitter) against Apex (through `tools/play_bot.py`) on testmap.xml;
- 200 plies, **won 18 – 14**, no cheating or timeout entries in the server trace, slowest move 1.48 s.

## 8.3 Iteration history: every change came from a lost game

| Version | Change | Lost game that motivated it | Measured effect |
|---|---|---|---|
| v1 | Baseline: planner + MCTS + race evaluation | none | 81% vs the panel (84 games), 100% on villages |
| v2 | **Merge-aware race** ([`project_race`](../../splitter/evaluate.py#L51)), **commitment** (`commit_bonus`), **pincer** ([`_pincer_orders`](../../splitter/planner.py#L598)) | prize_11x17: our 19 creatures were split 12 + 7 while Apex took the 18-house and hunted us | prize map won vs Apex as both species; 82.7% overall |
| v3 | **The opponent model may strike at P ≥ 0.3** (`gamble="always"` in the tree); exposure counts those strikes; **evaluation steepness grows with game progress** | testmap: we stepped our 16 next to RaceMCTS's 14, it struck first at 44% and won. thetrap: same, at 35% | |
| v4 | **Protected plans** (`PROTECTED`); **flee into open space** ([`flee_cell`](../../splitter/planner.py#L199)) | vil_10x16: with 6 groups the only `flee` plan was truncated and a group was eaten; chased groups died in corners | Apex 73% → 92%; v4 beat v3 head-to-head (12 W, 8 D, 4 L) |
| v6 | **Open-loop expansion fix:** a plan is checked before being expanded in a sampled future (chapter 11.7) | Found while integrating the opponent model: 4.1% of turns crashed the search and played the fallback move | **+2.2 pts** overall, **61.6%** head-to-head vs v5; RaceMCTS 66% → 73%, Expecti 69% → 81% |
| v6 | HMM opponent model, pre-emptive plans, adaptive settings, pre-game analysis, map-aware deathball (chapters 11, 12) | — | none replicated on unseen data: all off by default |
| v5 | **Contest-aware race** ([`_contest`](../../splitter/evaluate.py#L104)), **reserve radius 6**, stronger house penalty near big enemies, planner caches (×4 speed) | close_8x12: splitting 8 into 3 + 5 next to the enemy fed it every house | RaceMCTS 48% → 72% (108-game set); 79.1% on the full 448-game set |

## 8.4 Ideas tested and rejected (measured, then switched off)

| Variant | Result | Why it is off |
|---|---|---|
| `light_tree=True` (fewer plans below the root) | vs RaceMCTS 35% vs 48% | A weaker opponent model outweighs the extra iterations |
| Planner caches alone (4× more iterations) | 50% vs v4 head-to-head | Kept for safety margin, but speed was not the bottleneck |
| `reserve_radius=10` | vs RaceMCTS 42% vs 72% | Too timid: hardly ever splits |
| `gamble="always"` for our own plans | 58.3% vs 60.4% (adaptive) | No gain |
| `split_enemy_dist=6` | 77.3% vs 79.1% (448 games) | Gain on 96 games was noise |
| `split_enemy_dist=4` | 76.3% vs 79.1% | Worse |
| `prize_lock=True` | 64.1% vs 64.1% | No effect |

## 8.5 Next steps

1. **About 100 games at 1.5 s against RaceMCTS and Expecti,** to know where we really stand at tournament speed.
2. **Opponent modelling.** Detect whether the opponent strikes at low odds or ever splits, and adapt the strike threshold and `reserve_radius`.
3. **Choose split or deathball from the map at game start.** Use the house-size distribution and the distance between starts: prize and close-start maps favour the deathball (8.1).
4. **Tree reuse between turns.** Keep the subtree matching the opponent's actual reply.
5. **Endgame kiting.** When ahead and no house is reachable, keep at distance ≥ 2 from equal or bigger enemy groups until the end.
