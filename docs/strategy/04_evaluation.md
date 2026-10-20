# 04 · Evaluation: [splitter/evaluate.py](../../splitter/evaluate.py)

[`evaluate(state, side, to_move, remaining_plies)`](../../splitter/evaluate.py#L152) returns an
estimate of **P(side wins)** in [0, 1]. MCTS uses it at the end of every rollout (chapter 05). The
agent also uses it at the root, to decide whether we are behind and gambles become allowed
(chapter 06).

It is computed in four stages.

## 4.0 Terminal and trivial positions

- One side has no creatures: 0 or 1 (0.5 if both are gone).
- No plies left: compare totals, the server's rule (1, 0.5 or 0).

## 4.1 Immediate tactics: [`resolve_immediate`](../../splitter/evaluate.py#L27)

The player to move takes its **certain** gains first. Biggest group first, each group takes the
best of:
- a sure kill of an adjacent enemy group (≥ 1.5×);
- a conversion of an adjacent house it is big enough for.

Without this, a position where we are about to be eaten would look fine.

## 4.2 Race projection: [`project_race`](../../splitter/evaluate.py#L51)

This is the heart of the evaluation, and the reason splitting is valued correctly.

Every group is a **runner**: (position, size, clock, side). The side to move next starts at
clock 0 and the other at 0.5 (a half-move head start). Then, repeatedly:

1. **Find the earliest capture.** Among all (runner, house) pairs with runner ≥ house, take the one that finishes earliest (clock + distance).
2. **Merge-aware.** Also consider two runners of the same side meeting first (half their distance), then taking a house that **neither could take alone**.
   - This was added after a lost game where we had 19 creatures split 12 + 7, and the opponent took an 18-house prize.
   - Without merge-awareness the projection said "nobody can take the prize", so regrouping looked useless.
3. **Contest-aware: [`_contest`](../../splitter/evaluate.py#L104).** If an enemy runner can reach the house right after the capture:
   - with ≥ 1.5× our new size → the capture is **not counted**;
   - with ≥ our new size (it strikes at ≥ 50%) → it **counts half**.
   - This was added after losses where small groups raced into the enemy's zone and only fed it.
4. **Apply the capture.** The runner moves there and grows; its side's projected total gains h · [`DISCOUNT`](../../splitter/evaluate.py#L24)^t, with DISCOUNT = 0.93.
5. **Stop** when nothing can be captured or the clock passes the **horizon** = remaining plies / 2. So near the end, far houses no longer count (clock awareness).

**Why this rewards safe splitting.** Several runners collect houses *in parallel*, so a well-split
army projects more humans than one deathball, but only if its parts are big enough and not
contested.

**Snowballing is modelled too.** A runner that converts becomes bigger and can then take bigger
houses.

## 4.3 Exposure: [`exposure`](../../splitter/evaluate.py#L123)

Each projected total loses the expected creatures that the enemy can take next turn. For each of
our groups we keep the worst threat:

| Enemy distance | Enemy moves next | We move next |
|---|---|---|
| 1 (adjacent) | P(enemy wins) × size, **as soon as P ≥ 0.3** (striking first is rational) | 0.25 × size if it can sure-kill us (we may be cornered), else 0 |
| 2 | 0.12 × size if it can sure-kill us | 0.05 × size if it can sure-kill us |

This is what punishes splits that are too thin, and stepping next to an equal enemy group.

## 4.4 From margin to probability: inside [`evaluate`](../../splitter/evaluate.py#L152)

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

[`material_balance`](../../splitter/evaluate.py#L205): (our total − theirs) / everything. The agent
uses it to switch on gambles in the last 20 plies when behind
([`SplitterAgent._choose`](../../splitter/agent.py#L169)).

## 4.6 Opponent-specific risk and endgame switches

- **`evaluate(..., strike_p=...)`** passes the threshold to [`exposure`](../../splitter/evaluate.py#L123): the lowest odds at which the enemy is assumed to strike an adjacent group of ours.
  - Default 0.3 (the v3 lesson).
  - With the opponent model on, MCTS sets it to **0.5** once the style HMM has seen this opponent never take long-shot attacks.
  - This, together with opponent strikes in rollouts, is where the model's measured gain comes from (chapter 12).
- **`evaluate(..., kite=True)`** makes the sigmoid maximally steep once no humans are left, so a lead counts as decided and the search keeps its distance.
  - +5.1 on the tuning set, −0.6 on the hold-out set: rejected (chapter 12).
