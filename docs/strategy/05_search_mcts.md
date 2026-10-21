# 05 · Search: Monte Carlo Tree Search over joint plans: [splitter/mcts.py](../../splitter/mcts.py)

The PDF requires an AI that anticipates the opponent's moves. We use **MCTS**, because:

- **The game has chance** (random battles). MCTS averages over sampled dice naturally, where minimax would need expectation nodes.
- **The branching factor is large even with macro-actions** (15 plans × 12 opponent plans per ply). MCTS spends its time on the promising lines instead of a uniform depth.
- **It is anytime.** It can be stopped at any moment and still return its best move, which is essential with a hard 2 s limit.

## 5.1 Tree and nodes

- **[`Node`](../../splitter/mcts.py#L26)** stores:
  - the plan that leads to it, and which side played it;
  - visits and the sum of rewards (always from the **root** side's point of view);
  - the plan's normalized prior;
  - the list of plans not yet expanded.
- **Turns alternate:** root = our turn, children = our plans, grandchildren = the opponent's replies, and so on.
- **Plans at a node come from [`MCTS._plans`](../../splitter/mcts.py#L66):**
  - *our side:* the agent's `PlanConfig` (`inner_cfg`);
  - *the opponent:* a config with `gamble="always"` and at most 12 plans. We assume it strikes first whenever adjacent with P ≥ 0.3, because real opponents do (chapter 04).
  - Priors are normalized to [0, 1] by the best sibling.

## 5.2 One iteration: [`MCTS._iterate`](../../splitter/mcts.py#L122)

1. **Selection.** From the root, repeatedly pick a child with [`MCTS._select`](../../splitter/mcts.py#L76):
   ```
   score = Q + c·√(ln N / n) + prior_bias · prior / (1 + n)
   ```
   - Q = mean reward from the point of view of the side that moves at that node;
   - c = 0.6, prior_bias = 0.6;
   - unvisited children first.
   - The prior term (*progressive bias*) makes the planner's favourite plans get searched first; its effect fades as real visits accumulate.
2. **Open-loop replay.** Nodes do not store boards. Each iteration re-applies the plans from the root with [`State.apply`](../../splitter/state.py#L96) and **fresh dice**, so chance is averaged over iterations. If a stored plan has become illegal in this sampled future (a group died in a battle), the descent stops there ([`check_moves`](../../splitter/rules.py#L91)).
3. **Expansion with progressive widening.**
   - The plan to expand is first checked with `check_moves` in *this* sampled future: plans are generated once per node, but open-loop replays can reach the node with different dice. Without this check an illegal plan raised inside `State.apply`, the whole search for the turn was lost, and the fallback move was played. That was the case on 4.1% of v5's turns; the fix is worth +2.2 points (chapter 11.8).
   - A node may have at most k(N) = 2·√(N+1) children ([`MCTS._widen_limit`](../../splitter/mcts.py#L92)), so new plans are added in prior order as the node gets visited.
   - The root is fully expanded: every root plan is tried at least once.
4. **Rollout.** 2 plies of the greedy [`quick_plan`](../../splitter/planner.py#L582).
5. **Evaluation.** [`evaluate`](../../splitter/evaluate.py#L169) at the leaf, with the remaining plies reduced by the depth reached.
6. **Backpropagation.** Visits + 1 and reward added along the path.

## 5.3 The decision: [`MCTS.search`](../../splitter/mcts.py#L97)

- **The root plans are given by the agent,** with the commitment intents applied.
- **It iterates until the deadline,** then returns the **most visited** root plan (ties broken by mean value).
- **Robust edge cases:**
  - no plan → `None`;
  - a single plan → returned immediately, with no search;
  - if the budget runs out before the first iteration finishes, the planner's best plan is returned.

[`MCTS.root_stats`](../../splitter/mcts.py#L177) lists visits, value and tag for every root plan.
It is printed when the bot runs with `SPLITTER_VERBOSE=1`.

## 5.4 Speed

- **Iteration rate:** about 1,000–2,000 iterations per second in a mid-game position, in plain Python.
- **Where the time goes:** plan generation dominates, so it uses caches (chapter 03, `_Builder`).
- **Light tree** (an experiment with fewer plan variants below the root, since removed): faster, but measurably weaker (35% vs 48% against RaceMCTS), because the modelled opponent got worse.
- **Faster is not automatically stronger at short budgets:** the 4× planner speed-up (campaign 1) and the transposition cache (campaign 2) gave no measurable gain at 0.2–0.25 s.
- **But thinking time matters at 1.5 s:** the flagship with half its budget (0.75 s) lost **25.0 ± 10.9 points** against the same opponents (chapter 14.3).
- **Profile of a 1.5 s decision** (8 groups): plan generation 50%, rollouts 22%, evaluation 14%, legality checks 14%.

## 5.5 Evaluation constants, and removed search experiments

`MCTS(ev=...)` passes the evaluation constants to every leaf evaluation; this is the only
difference between the flagship and the backup (chapter 04.6).

**Removed after measurement** ([15 · Failed strategies](15_failed_strategies.md)):
- campaign 1: search steering by the opponent model (priors at opponent nodes, PUCT; RaceMCTS −9), and the retired Splitter-HMM's risk hooks (opponent strikes in rollouts, its own strike threshold);
- campaign 2: tree reuse between turns, a transposition cache, sequential halving at the root, a risk-aware final choice, planner rollouts and 18 opponent plans per node. Tree reuse and the cache worked mechanically (15–49% reuse hits, 15–20% cache hits) but showed no gain at 0.25 s; they are the two worth re-testing at 1.5 s (the code is in the local archive `arena/snapshots/splitter_c2/`).
