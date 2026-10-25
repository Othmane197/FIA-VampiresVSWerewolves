# 04 · Evaluation: [splitter/evaluate.py](../../splitter/evaluate.py)

[`evaluate(state, side, to_move, remaining_plies)`](../../splitter/evaluate.py#L171) returns an
estimate of **P(side wins)** in [0, 1]. MCTS uses it at the end of every rollout (chapter 05). The
agent also uses it at the root, to decide whether we are behind and gambles become allowed
(chapter 06).

It is computed in four stages.

## 4.0 Terminal and trivial positions

- One side has no creatures: 0 or 1 (0.5 if both are gone).
- No plies left: compare totals, the server's rule (1, 0.5 or 0).

## 4.1 Immediate tactics: [`resolve_immediate`](../../splitter/evaluate.py#L45)

The player to move takes its **certain** gains first. Biggest group first, each group takes the
best of:
- a sure kill of an adjacent enemy group (≥ 1.5×);
- a conversion of an adjacent house it is big enough for.

Without this, a position where we are about to be eaten would look fine.

## 4.2 Race projection: [`project_race`](../../splitter/evaluate.py#L69)

This is the heart of the evaluation, and the reason splitting is valued correctly.

Every group is a **runner**: (position, size, clock, side). The side to move next starts at
clock 0 and the other at 0.5 (a half-move head start). Then, repeatedly:

1. **Find the earliest capture.** Among all (runner, house) pairs with runner ≥ house, take the one that finishes earliest (clock + distance).
2. **Merge-aware.** Also consider two runners of the same side meeting first (half their distance), then taking a house that **neither could take alone**.
   - This was added after a lost game where we had 19 creatures split 12 + 7, and the opponent took an 18-house prize.
   - Without merge-awareness the projection said "nobody can take the prize", so regrouping looked useless.
3. **Contest-aware: [`_contest`](../../splitter/evaluate.py#L123).** If an enemy runner can reach the house right after the capture:
   - with ≥ 1.5× our new size → the capture is **not counted**;
   - with ≥ our new size (it strikes at ≥ 50%) → it **counts half**.
   - This was added after losses where small groups raced into the enemy's zone and only fed it.
4. **Apply the capture.** The runner moves there and grows; its side's projected total gains h · [`DISCOUNT`](../../splitter/evaluate.py#L25)^t, with DISCOUNT = 0.93.
5. **Stop** when nothing can be captured or the clock passes the **horizon** = remaining plies / 2. So near the end, far houses no longer count (clock awareness).

**Why this rewards safe splitting.** Several runners collect houses *in parallel*, so a well-split
army projects more humans than one deathball, but only if its parts are big enough and not
contested.

**Snowballing is modelled too.** A runner that converts becomes bigger and can then take bigger
houses.

## 4.3 Exposure: [`exposure`](../../splitter/evaluate.py#L142)

Each projected total loses the expected creatures that the enemy can take next turn. For each of
our groups we keep the worst threat:

| Enemy distance | Enemy moves next | We move next |
|---|---|---|
| 1 (adjacent) | P(enemy wins) × size, **as soon as P ≥ 0.3** (striking first is rational) | 0.25 × size if it can sure-kill us (we may be cornered), else 0 |
| 2 | 0.12 × size if it can sure-kill us | 0.05 × size if it can sure-kill us |

This is what punishes splits that are too thin, and stepping next to an equal enemy group.

## 4.4 From margin to probability: inside [`evaluate`](../../splitter/evaluate.py#L171)

```
a, b  = projected totals (us, them) minus exposure, floored at 0.1
x     = (a − b) / (a + b)                                  ∈ (−1, 1)
k     = 6 + 14 · progress     progress = 1 − remaining/max_ply
score = 1 / (1 + e^(−k·x))
if a ≥ 1.5·b: score = 0.5·score + 0.5      (we can hunt them down without dice)
if b ≥ 1.5·a: score = 0.5·score
```

**The steepness k grows as the game ends.** A lead of 18 against 14 at ply 100 is close to a won
game, because it can only be erased by a gamble. Early in the game the same margin is still
uncertain. This fixed a lost game where we gave up a safe late lead by stepping next to the enemy.

## 4.5 Helper

[`material_balance`](../../splitter/evaluate.py#L220): (our total − theirs) / everything. The agent
uses it to switch on gambles in the last 20 plies when behind
([`SplitterAgent._choose`](../../splitter/agent.py#L164)).

## 4.6 Tunable constants, and the retired calibrated evaluation

The calibration constants are an [`EvalParams`](../../splitter/evaluate.py#L29) object passed
to `evaluate(..., ev=...)` (through MCTS): `discount` (0.93), `k0` (6) and `k1` (14) in
k = k0 + k1·progress, and `opp_strike_p` (0.3), the odds from which `exposure` counts the
opponent's strikes on us. The other risk terms (contest factors, the domination bonus) are fixed
in the code. **Both kept models use these defaults**; the flagship lowers `opp_strike_p` to 0.1
for one decision when the opponent is losing (`desperate_p`, chapter 16.6), since a losing bot
strikes at low odds.

| Model | discount | k = k0 + k1·progress | Where the values come from |
|---|---|---|---|
| Both kept models | 0.93 | 6 → 20 | Hand-set (v1–v5, lost-game analysis) |
| Retired "Splitter-Calibrated" (campaign-2 backup) | 0.845 | 8.5 → 35.5 | Fitted on game outcomes by [tools/tune_eval.py](../../tools/tune_eval.py) (chapter 14.3) |

**Why the calibrated evaluation was retired.** On hold-out games the default evaluation is
**under-confident about leads**: positions it rates 0.65–0.75 are won 92–93% of the time. The
fitted constants cut the log-loss on hold-out games by 9% and fix most of that calibration error.
In games it scored +5.9 ± 4.4 at 0.25 s and +1.3 ± 6.1 (pooled) at 1.5 s, and then exactly 0.0 ±
3.1 in campaign 3's final on fresh maps: better forecasts, no better play (lesson 3 of chapter 15).

**Removed experiments** ([15 · Failed strategies](15_failed_strategies.md)):
- endgame kiting (`kite`: maximal steepness once no humans are left): +5.1 tuning, −0.6 hold-out;
- the retired Splitter-HMM's opponent-specific strike threshold (0.5 against "careful" opponents);
- fitting the risk terms too (contest factor, coin-flip exposure, domination bonus): a better log-loss but −2.4 in games, because the recorded games come from a bot that avoids those risks.
