# Match findings: Dana's bot vs the teammates' bots (10 Nov 2026)

Dana's bot = `SafeAgent(DeepAgent)` (iterative-deepening alpha-beta, commit `8e75708` on top of the
`Dana` branch), 1.5 s per move. Each opponent ran its own code, unmodified, at its own time budget.

## Setup (same for every opponent)

* 24 games: 12 maps × both sides.
  * 8 standard: `testmap`, `testmap2`, `g9x15a`, `g11x21a`, `g15x29a`, `g15x29b`, `s12x18`, `s14x20`.
  * 4 large: `big40x40`, `big45x45`, `big50_30`, `big50_30b` (generated in the style of the professor's generator; the real tournament maps may differ).
* Referee: `server_rules.py` (port of the official rules). 200 plies; an illegal or empty turn loses.
* Score = wins + ½ draws. "Material share" = our creatures / all creatures at the end (less noisy than win/loss).
* Othmane's, Mohamed's and Ronita's bots run in-process through `rival_bots.py` / `tourney.py`.
* Harsha's bot starts its own process pool, so it ran as a separate program over TCP (`tcp_match.py` + `fake_server.py`), exactly like the tournament client, with a 2 s answer limit. On this 2-core machine it had 1 helper process; on the tournament machine it would have more.

## Results

| Opponent (version) | Score (W/D/L) | Material share | Large maps | Standard maps | Illegal / crashes |
|---|---|---|---|---|---|
| Harsha, parallel MCTS (`88600de`) | **81.2 %** (18/3/3) | 72.9 % | 7/1 W/L | 11 W, 3 D, 2 L | 0 / 0 |
| Ronita, RaceMCTS (`c9f42ee`, 9 Nov) | **64.6 %** (14/3/7) | 62.6 % | 8/0 | 6 W, 3 D, 7 L | 0 / 0 |
| Othmane, Apex alpha-beta | 87.5 % large / ~55–62 % standard (separate runs, see DEEP_AGENT.md) | 68 % large | | | 0 / 0 |
| Mohamed, Splitter MCTS (`aafd28c`) | **37.5 %** (9/0/15) | 61.5 % | 2/6 | 7 W, 9 L | 0 / 0 |

± one standard error is about ±10 points for 24 games.

## Findings

1. **Mohamed's bot is the strongest we have measured.** All 15 of its wins against us are on material at ply 200, 7 of them by 6 creatures or fewer, and it never lost its army. Its evaluation simulates the race for humans in sequence (captures in order, growth, merges, contested houses), it penalises standing next to an enemy that would win a battle at ≥ 30 % (exposure), and it checks that detachments cannot be caught. Our wins against it are mostly total wipe-outs (deeper tactics), which is why our material share stays above 50 % despite the losses.
2. **Our standard-map play is the weak spot, not the large maps.** Large maps: 7/8 vs Harsha, 8/8 vs Ronita, 87.5 % vs Othmane. Standard maps: about 50 % against Ronita and Othmane, under 50 % against Mohamed.
3. **`testmap` (the professor's map) is our worst map.** Lost from both sides against Othmane (twice), Mohamed and Ronita; won/drew only against Harsha. Cause, seen in traces against Othmane and Ronita: after the human race it is 16 vs 16 with an unconvertible group of 20 left. We stay split **12 + 4** for 70+ plies while the opponent merges into **16**. Their 16 attacking our 12 wins at P = 16/12 − 0.5 = **83 %**; merged, it would be 50/50 at worst. Our evaluation does not reward merging there: it only penalises *certain* kills (≥ 1.5×), not likely-gamble exposure, and no human group gives a reason to merge.
4. **Sudden material collapses come from small/medium groups ending up next to enemy groups.** Traced against Harsha: a 49 pinned on the edge next to a 98 (struck first at 25 % and won), an 18 next to a 17 (struck first at 56 % and lost). Once adjacent, the search chooses correctly; the weakness is getting adjacent. Same root cause as finding 3.
5. **Harsha's bot answers in up to 1.93 s** (search budget 1.4 s + process-pool overhead), close to the 2 s limit. On a loaded tournament machine it could miss turns. Worth telling him.
6. **No side bias in general.** Against Harsha all 3 losses came as werewolves (second mover); against Mohamed and Ronita losses are split between both sides. Probably chance.
7. **Reliability:** across 72 games against the three, our bot made 0 illegal moves, 0 crashes, max decision time 1.59 s. All opponents were equally clean.

## Next improvement to test

An **exposure term** in the evaluation (`Params.w_exposure`, already in the code, off): penalise each of our groups that a bigger enemy group could attack with P > 0.5, by (2P − 1) × its size, and the reverse for theirs. It targets findings 3 and 4 directly (it makes "join the 12" worth more than staying split next to a 16). It should be measured on the standard maps against Ronita and Mohamed, where we are weakest.
