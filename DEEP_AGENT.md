# DeepAgent: iterative-deepening alpha-beta for Vampires vs Werewolves

This is the engine behind our tournament bot (`main.py` → `SafeAgent` → `DeepAgent`).
It replaces the depth-2 expectiminimax `SearchAgent` (`search_agent.py`, kept for comparison).
Everything else is reused unchanged: the rules port (`server_rules.py`), the legality gate and
fallbacks (`safe_agent.py`), the self-play harness and the tests.

## 1. Why a new engine

The professor's guidance (November meeting) and what we measured:

| Guidance | What it meant for the design |
|---|---|
| "Go deep with alpha-beta; depth 4 is not enough, the bot oscillates" | Iterative deepening + transposition table + a narrow, well-ordered turn generator. Typical depth at 1.5 s is 6–9 plies in the middle game (the old engine: 2). |
| "Random battles only as a last resort" | Implemented through the evaluation, not as a hard rule (section 4.3): a gamble is chosen only when its expected value beats playing on, which in practice means when we are behind. |
| "Splitting is a good idea" | Controlled splits ("exactly enough for a human group, the rest elsewhere"), up to 6 groups. It only paid off after the evaluation learned that one group cannot be in two places (section 4.2, *queue discount*). |
| Maps up to 50×50, 2 s per move | Sparse state (only occupied cells), time checks every 32 nodes, game-clock-aware budget, garbage collector off. Max decision time measured: 1.50 s on 50×50. |

## 2. Where things are

| Component | File / function |
|---|---|
| State (immutable tuple) | `deep_agent.py`: `state_from_game`, `_freeze` |
| Transition (official rules, chance outcomes) | `deep_agent.apply_turn` |
| Battle probability (port of `Board.GetProba`) | `deep_agent.win_probability` |
| Turn generator | `deep_agent.gen_turns` |
| Evaluation | `deep_agent.evaluate`, `terminal_value` |
| Search: negamax alpha-beta, PVS, TT, chance nodes | `deep_agent.Searcher.negamax`, `Searcher.turn_value` |
| Iterative deepening + time control | `deep_agent.Searcher.search`, `DeepAgent._budget` |
| All tunable numbers | `deep_agent.Params` |
| Legality gate + fallbacks (unchanged design) | `safe_agent.SafeAgent` |
| Tests | `test_deep_agent.py` (+ the existing test files) |
| Benchmarks | `tourney.py` (head-to-head), `rival_bots.py` (teammates' bots as opponents) |

## 3. Search

### 3.1 Negamax alpha-beta (course, chapter 2)
Minimax written in its *negamax* form: the value of a position for the player to move is
`max over turns of ( - value of the child for the other player )`, so a single function serves both
players. Alpha-beta pruning keeps a window `[alpha, beta]`; as soon as one turn proves that the
opponent would never allow this position (`alpha >= beta`), the remaining turns are skipped.
With perfect move ordering alpha-beta visits about `b^(d/2)` nodes instead of `b^d`, which is what
makes depth affordable.

**Principal variation search (PVS)**: after the first (best-ordered) turn, each other turn is first
searched with a zero-width window `[alpha, alpha+ε]`, a cheap yes/no test of "can this beat the
best so far?". Only if the answer is yes is it searched again with the full window. Same result,
fewer nodes (−4 % measured at depth 5 on 12 mid-game positions; identical values, checked).

### 3.2 Iterative deepening under a time limit (course, chapter 2, "time-constrained α-β")
Search depth 1, then 2, 3, … until the budget is spent. If time runs out in the middle of an
iteration, we keep the best turn of the last completed iteration, or a turn of the interrupted one
that was fully searched and scored better. A new iteration is not started if the previous one
suggests it cannot finish (`last_iteration_time × 3 > time left`).

### 3.3 Transposition table (course: hash table of evaluated positions)
Key = (state, side to move); the state is an immutable tuple, so Python hashes it directly (the
course's Zobrist XOR is the same idea, done by hand). Each entry stores depth, value, bound type
(exact / lower / upper) and the best turn. Two uses:
1. a position reached through different move orders is not searched twice;
2. **move ordering**: the best turn of the previous iteration is tried first in the next one,
   which is what makes alpha-beta prune well.
The generated turn lists are cached too (`gen_cache`): iterative deepening revisits the same
nodes at every depth, and turn generation was 83 % of the run time before this cache.

### 3.4 Chance nodes (course: expectiminimax)
A turn that starts a random battle has two outcomes (win / lose) with the official probability P
and the rounded expected survivors (`apply_turn`). Its value is the probability-weighted average
of the two children. Pruning inside it: Star1 (Ballard 1983, beyond the course). The bounds
`[-WIN, WIN]` let us stop as soon as the average provably falls outside `[alpha, beta]`.
Random battles are rare in the tree (at most one per turn, and only where the generator allows
them), so this costs little.

## 4. Evaluation (`evaluate`)

Score for the player to move, in `(-1, 1)` (+ the confidence bonus, 4.3); finished games are
`±WIN = ±1.2`, just above the best unfinished score (minus a tiny amount per ply so that faster
wins / slower losses are preferred).

### 4.1 Raw score
```
raw = (our creatures − theirs)                                   material: the win condition
    + w_humans × human race                                      (4.2)
    + kill terms: enemy groups we can wipe out (×0.8 if adjacent and we move, small if far)
                  − our groups they can wipe out (×0.6 if within 2 cells)
```

### 4.2 Human race with distance and queue discounts
Every human group of size h goes to the side whose nearest group *strong enough to convert it
for sure* (≥ h creatures) arrives first; ties go to the player to move. Its value is
`h × gamma^(distance − 1)` (gamma = 0.9), so every step toward a target improves the score. This
removes the flat regions where a shallow search oscillates.

**Queue discount (decisive on big maps).** A single group was first credited with *every* human
group it was nearest to, as if it could be in several places at once. So a single merged blob
looked as good as several collectors, and on 50×50 maps our bot merged everything and was
out-harvested. Now each group's targets are sorted by distance and the k-th is multiplied by
`queue^k` (queue = 0.6). Spreading out to work in parallel becomes visibly valuable.
Measured on 5 large maps (25×40 to 50×50, 20 games vs the old bot at 0.3 s/move):
37.5 % → 55 % (queue) → 67.5 % (queue + up to 6 groups).

### 4.3 Risk: tanh squashing, the confidence bonus, the terminal score
`value = tanh(raw / (0.25 × creatures + 0.5 × humans left)) + confidence`
(confidence = +0.1 for the player we play for, −0.1 for the other).
* tanh turns a lead into something like a winning chance. It is concave when ahead and convex
  when behind.
* **The scale depends on the humans left.** While many humans remain, a lead can still change, so
  the scale is wide (soft). Once they are gone, a material lead decides the game (the bigger side
  avoids battles until ply 200), so the scale is narrow (sharp). With a fixed wide scale the bot
  thought being 49 vs 63 with no humans left was only mildly bad, and gambled to escape it.
* **Confidence bonus.** A coin flip for the whole game is worth exactly 0 (½·WIN − ½·WIN). Without
  the bonus, an even position is also worth 0, so the search was indifferent between playing on
  and a 50/50 all-in battle, and took it (observed: 19 vs 19, lost on the coin flip). With the bonus,
  playing on is worth +0.1 > 0. A gamble is chosen only when the alternative is clearly worse,
  i.e. when we are losing. This is the professor's advice, *derived* from expected value rather
  than hard-coded. The same bonus makes the opponent (in our search) *want* to gamble against us,
  so the search avoids handing it good gambles.
* **Terminal score.** WIN was first 2.0, twice the best unfinished score. Then a 21 % shot at an
  instant win (0.21 × 2 = 0.42) looked better than a solid lead (+0.28), and the bot threw a
  winning game (76 vs 65) on a 27-vs-65 battle. With WIN = 1.2 (just above 1 + confidence) the
  scales are consistent. This was the largest single gain we measured (about +5 points vs the old
  engine).

## 5. Turn generator (`gen_turns`)

All legal turns are astronomically many. Per group we propose a few goal-directed options:

1. one step toward each of the 3 most valuable human groups it can convert for sure
   (+ the second-best path to the best one);
2. **split**: exactly h creatures toward a human group of size h, the rest toward another one;
3. attack an adjacent enemy group it can kill for sure (alone or pooled with friends), or step
   toward a killable one;
4. flee if an enemy group nearby could kill it or win a battle against it;
5. step toward the nearest friendly group (merging is needed to reach the 1.5× threshold);
6. **adjacent random battles**: against humans if P ≥ 0.25; against monsters *always*, even a
   3 % lottery ticket. Other bots do try those against a big group of ours, and the side that
   is attacked must see it coming (observed: our 64 next to their 4, lost on a 3 % roll);
7. positional steps (toward / away from the enemy, toward a big human group) and "stay".

Steps are chosen among the cells that bring the group one step closer, preferring the **least
exposed** cell (0 = safe, 1 = an adjacent enemy could start a likely battle, 2 = adjacent enemies
can kill us for sure), then the straightest one. (Observed bug before this: on `thetrap`, two
cells were equally close to the humans, one adjacent to the enemy. The bot took the exposed one
and turned a forced win into a coin flip.)

Joint turns are enumerated best-first (sum of each group's option ranks), filtered by Rule 5
(no cell both source and target) and by "at most one random battle per turn". At most 30 turns
at the root and 16 inside the tree. Branching factor ≈ 3–16, which is what allows depth.

## 6. Time and robustness

* Budget 1.5 s per move (server limit 2 s). The clock is checked every 32 nodes.
* **Game clock**: the server config also has `MaxGameDuration = 5 min` for 200 plies, i.e. 1.5 s
  per ply *for both players together*. `DeepAgent._budget` lowers our budget when the remaining
  game time requires it.
* **Garbage collector off**: with 10^5–10^6 table entries, one automatic collection paused the
  program ~0.2 s (measured 1.69 s for a 1.50 s search). Our data are tuples freed by reference
  counting, so the cyclic collector is not needed.
* Measured max decision time: 1.503 s (normal maps), 1.539 s (50×50 with 62 groups on the board).
* **Counts fit in one byte.** The protocol sends each count as one byte: a move of 256+ creatures
  is illegal and forfeits the game (observed on a 50×50 map: we were winning 309 vs 228 and forfeited
  by moving a group of 260). The generator never moves more than 255 from a cell in one turn (the
  rest stays) and avoids piling more than 255 on one cell. Same cap in `SafeAgent`'s brute-force
  fallback. Covered by `test_deep_agent.test_counts_fit_in_a_byte`.
* `SafeAgent` still checks every turn against the official rules and falls back to the generator
  or a brute-force legal move if anything goes wrong.

## 7. Results

(See section 8 for how to reproduce. "Score" = wins + ½ draws, ± one standard error.)

All at the professor-style rules (our `server_rules.py` referee), both species on every map.

| Opponent | Setting | Games | Score (W/D/L) |
|---|---|---|---|
| Old engine (`SearchAgent`, depth-2 expectiminimax) | 0.3 s/move, 17 standard + 5 large maps | 44 | **65.9 %** ± 7.1 (22/14/8) |
| Old engine | 0.3 s/move, 5 large maps, before the queue discount | 20 | 37.5 % ± 10.8 |
| Old engine | 0.3 s/move, 5 large maps, queue discount + 6 groups | 20 | 67.5 % ± 10.5 |
| Othmane's Apex (alpha-beta, 1.65 s) | full time, `SafeAgent(DeepAgent)`, 8 standard + 2 large maps | 20 | **60.0 %** ± 11.0 (10/4/6) |

Search depth (mid-game, 1.5 s): 6–9 plies on standard maps, 4–6 on 50×50 (old engine: 2).
Speed: 20–35 k nodes/s. Max decision time: 1.56 s, 0 illegal moves, 0 crashes in all runs above.

Calibration A/B (0.3 s vs the old engine, 44 games each): squash 0.6 / 0.25+0.5 h / 0.2+0.6 h →
64.8 % / 65.9 % / 59.1 %. Differences are within noise; 0.25 + 0.5 h was kept because it is the
one that refuses the bad gamble of section 4.3.

**Known weakness:** on the densest 50×50 map (30 human-group pairs, 576 humans) Apex out-collected
us from both sides (231 vs 369). At depth 4–6 the long-range collection plan comes from the
evaluation only; a better plan estimate (e.g. a greedy route per group) is the next thing to try.
Noise warning: ± is one standard error; small symmetric maps are often decided by who moves first
plus one coin-flip battle.

## 8. Reproducing

```bash
python3 test_deep_agent.py                  # legality + exact transition + timing
python3 tourney.py deep expecti --maps all --seeds 1                 # vs our previous engine
./fetch_rivals.sh                            # copies teammates' branches into rivals/ (read only)
python3 tourney.py deep rival:Othmane --maps 1,2,5,8,10,11,15,16     # vs a teammate's bot
python3 tourney.py 'deep:{"time_limit":0.3,"queue":1.0}' expecti --maps big50_15.xml,big40x40.xml
```

## 9. Limits and ideas not done

* Python speed caps us at ~20–35k nodes/s. Depth on 50×50 maps is 4–6, so long-range planning
  rests on the evaluation (human race), not on search.
* The opponent model is our own generator: a turn it never proposes (an exotic split, say) is not
  anticipated, although the legality gate makes us safe against crashes, not against surprises.
* Quiescence search (extend leaves where a sure kill is pending) was not added; the kill terms of
  the evaluation approximate it.
* Many small symmetric maps are decided by who moves first plus a forced coin flip; equal bots
  score ~50 % there, so wins and losses on those maps are mostly noise.
