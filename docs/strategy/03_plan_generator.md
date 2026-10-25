# 03 · Plan generator: [splitter/planner.py](../../splitter/planner.py)

## 3.1 Why macro-actions

A turn is a set of moves for all our groups, and any group may split into any parts going to any
neighbours. With g groups of n creatures the number of legal turns is astronomical; a group of 10
alone has thousands of splits. No search can enumerate that in 2 seconds of Python.

So the planner proposes a **short list of joint plans**: about 10–18 full turns, each built from a
clear intention ("this group goes to that house, that group flees"). MCTS (chapter 05) then
chooses among them.

The planner is used:
- at the root, for us: [`SplitterAgent._choose`](../../splitter/agent.py#L164);
- inside the tree, for **both** sides: [`MCTS._plans`](../../splitter/mcts.py#L81).

So the opponent is modelled as an equally clever splitter.

**Data types:**
- [`Goal`](../../splitter/planner.py#L58): a target cell, a kind, a value, and the creatures needed.
- [`Plan`](../../splitter/planner.py#L68): the moves, a prior score, a tag such as `base` or `split2+go`, and the *intents* (where each group is heading).
- [`PlanConfig`](../../splitter/planner.py#L32): every tunable (chapter 10).

## 3.2 Step 1: goals for every group: [`candidate_goals`](../../splitter/planner.py#L239)

For each of our groups (position `pos`, size `count`), a ranked list of goals:

| Kind | When | Value |
|---|---|---|
| `house` | `count ≥ h` (a sure conversion) | h · γ^d, γ = [`GAMMA`](../../splitter/planner.py#L27) = 0.9, d = distance. **×0.15** if an enemy able to convert it gets there first ([`race_won`](../../splitter/planner.py#L124)). **×0.1** if an enemy ≥ 1.5·(count+h) can be there by then (it would kill us right after). **×0.4** if an enemy ≥ count+h can be there (it would strike at ≥ 50%) |
| `kill` | `count ≥ 1.5·e` (a sure kill) | 1.3·e·γ^(d−1) + 0.5. This is also how we **hunt other bots' small detachments** |
| `flee` | An enemy can sure-kill us within 3 moves, or is within 2 and strikes at ≥ 30% | 0.8 · threat + 0.1; target from [`flee_cell`](../../splitter/planner.py#L216) |
| `merge` | We have other groups | Grows with the friend's size; **urgent (×1.5)** when threatened, ×0.6 when we have nothing else to do |
| `gamble` | Allowed when behind (`gamble="adaptive"`) or always; adjacent; P ≥ 0.3 | Strike-first value p·e − (1−p)·count |
| `approach` | Nothing else is worth doing | Walk to the closest enemy we are not afraid of, or the centre |

**Commitment.** A goal equal to the one this group chose last turn gets ×(1 + `commit_bonus`)
= ×1.35. Without it, groups changed their minds every turn and walked back and forth (observed in
lost games). The agent remembers each plan's intents ([`Plan.intents`](../../splitter/planner.py#L74))
and passes them back as `intents`.

**Why a 30% strike threshold.** When two groups are adjacent, the side to move strikes first.
Striking at 35% can be the best choice when the alternative is being struck at 65% next turn. A
real opponent (RaceMCTS) beat us exactly like that.

## 3.3 Step 2: one safe step: [`safe_step`](../../splitter/planner.py#L162)

Every order (group, count, goal) becomes one move to a neighbouring cell. For each neighbour:

- **Skip it** if it is a source this turn (Rule 5, `forbidden`).
- **Skip it** if it holds humans we cannot convert or enemies we cannot kill for sure, unless it is the target of an intended gamble.
- **Bonus** for a free conversion or a sure kill on the way.
- **Skip it** if the merged cell would exceed 255.
- **Danger** = [`enemy_attack_loss`](../../splitter/planner.py#L95): the expected creatures lost if the best adjacent enemy attacks there. Real server odds (chapter 02); an enemy is assumed to strike when P > `danger_strike_p` (0.45) or e ≥ count.
- **Score** = distance to goal + bonus + `danger_weight` · danger / size (`danger_weight` = 3). Manhattan distance breaks ties, which avoids zig-zags.

**Flee target: [`flee_cell`](../../splitter/planner.py#L216).** It maximizes
2·(distance to the nearest threat) + 0.7·min([`border_distance`](../../splitter/planner.py#L211), 3)
+ 0.6·(progress towards the nearest friend). The middle term exists because a king chased along an
edge or into a corner gets caught; several lost games ended that way.

## 3.4 Step 3: turning orders into moves: [`_Builder.build`](../../splitter/planner.py#L331)

- **Sources first.** All sources of a plan are computed before any step is chosen, so Rule 5 holds by construction.
- **Moves with the same (source, destination) are merged.** Two detachments that happen to share a first step travel together that turn.
- **`gamble` and `pincer` orders** go straight into their adjacent target.
- **Intents** (destination cell → goal) are recorded for the commitment bonus.
- **Two per-call caches** made generation about 4× faster: `step_cache` and `loss_cache`. Plans share most orders.

## 3.5 Step 4: the plan families: [`generate_plans`](../../splitter/planner.py#L363)

[`assign`](../../splitter/planner.py#L397) (inside `generate_plans`) is a greedy assignment:
biggest group first, each takes its best goal not already reserved by another group. Fixed goals
reserve their targets first; this fixed a bug where two detachments chased the same house.

| # | Family | Built by | Purpose |
|---|---|---|---|
| 1 | `base` | `assign` | Every group takes its best goal |
| 1 | `alt:<kind>` | `assign` with one fixed goal | The `alt_groups` = 4 biggest groups try their 2nd–4th goals |
| 2 | **`splitN`, `splitN+go`** | [`_split_orders`](../../splitter/planner.py#L494) | **The Splitter's core:** detachments to several houses, with the main body staying (`splitN`) or going to its own goal (`+go`) |
| 3 | `regroup`, `regroup+go` | in `generate_plans` | Small groups rejoin the biggest (which stays, or keeps going to its goal) |
| 3b | `pincer-gather`, `pincer-go` | [`_pincer_orders`](../../splitter/planner.py#L562) | Several groups converge on a house none can take alone and enter it on the same turn |
| 4 | `hunt` | `assign` with kill goals | Everyone who can kill an enemy group goes for it |
| 5 | `flee` | `assign` with flee goals | Threatened groups run; others play `base`. The prior bonus equals the threat |
| 6 | `gamble` | `assign` with a gamble goal | Only when gambles are allowed |

Every plan is checked with [`check_moves`](../../splitter/rules.py#L91) and duplicates are
dropped.

**Protected plans** ([`PROTECTED`](../../splitter/planner.py#L28)) are never cut by
`max_plans`: `base`, `flee`, `regroup`, `regroup+go`, `hunt` and the `pincer` plans. In one lost
game, with 6 groups, the many split and alt variants had pushed the only `flee` plan out of the
list, and a group was eaten.

If nothing is legal, [`fallback_plan`](../../splitter/planner.py#L600) is used: the biggest group
steps to its least dangerous free neighbour.

## 3.6 The splits in detail: [`_split_orders`](../../splitter/planner.py#L494)

For one group at `pos` with `cnt` creatures:

1. **Reserve.** The main body must stay larger than `reserve_ratio` × every enemy group within `reserve_radius` = 6 cells (+1). A radius of 3 lost close-start maps; a radius of 10 was too timid.
2. **Candidate houses.** For each house with h ≤ cnt − reserve whose race we win ([`race_won`](../../splitter/planner.py#L124)):
   1. try a detachment of **exactly k = h** (a sure conversion);
   2. if [`detachment_safe`](../../splitter/planner.py#L134) refuses it, try k = h+1, h+2 or 2h (bigger detachments deter attackers on the way);
   3. score the option h·γ^d / k (humans gained per creature committed).
3. **Combinations.** Keep the best 5 options and build every single, every pair, the best 3, and the best 4 if `max_detachments` ≥ 4. Drop combinations that break the reserve.
4. **Two plans per combination:**
   - `splitN+go`: the rest of the group pursues its own best goal (excluding the detachments' houses);
   - `splitN`: the rest stays put.
   - The other groups follow `assign`, avoiding the detachments' houses.

### The safety check: [`detachment_safe`](../../splitter/planner.py#L134)

A detachment of k creatures walks the path [`straight_path`](../../splitter/planner.py#L84) to a
house of h humans, taking d moves. For every enemy group of size e:

- **On the way:** if e ≥ k (it would strike at ≥ 50%), it must not be able to reach any path cell c_t in time, i.e. `cheb(enemy, c_t) ≤ t` must be false at every step t.
- **On arrival** (we now hold k + h):
  - no enemy with e ≥ k + h may reach the house by move d;
  - enemies with e ≥ 1.5·(k + h) must be at least `safety_margin` = 1 more move away, so the detachment always keeps one move to escape or rejoin.

**Example:** 3 creatures going to a house of 3 next to an enemy group of 5 are refused
([tests/test_planner.py](../../tests/test_planner.py) `test_detachment_safety`).

## 3.7 Pincer: [`_pincer_orders`](../../splitter/planner.py#L562)

**The idea comes from a server fact:** arrivals on one cell are summed before the battle (chapter 02).

1. **Pick the target.** Find the best house with (our biggest group) < h ≤ (our total). Take the closest groups until their sum reaches h, and require that we win the race.
2. **Gather.** If not all of them are adjacent yet: `pincer-gather` walks them towards the house. `safe_step` stops next to it, because entering alone would be a losing random battle.
3. **Enter together.** Once all are adjacent: `pincer-go` moves them all into the house on the same turn, a certain conversion.

**Test:** 6 + 6 next to a house of 10 enter together
([tests/test_agent.py](../../tests/test_agent.py) `test_converges_two_groups_on_a_big_house`).

## 3.8 Rollout policy: [`quick_plan`](../../splitter/planner.py#L620)

A cheap greedy policy for the MCTS rollouts. Every group walks with `safe_step` to its best target
(a house it can convert or an enemy it can kill), weighted by γ^d. There are no splits and no
safety checks: it must be fast.

## 3.9 Removed planner experiments

Both kept models use this planner. The backup (Splitter-Classic) uses it exactly as described
above; the flagship (Splitter-R3) also turns on three campaign-3 options: the anti-bait kill
check (`bait_check`), good-odds "strike" plans (`strike_p`), and, when the opponent is losing,
lower danger and threat thresholds (`desperate_p`, through `danger_strike_p` and `threat_p`);
plus RaceMCTS-style plans added at the root (`race_plans`). Chapter 16 and [10.4b](10_parameters.md).

- **`danger_strike_p`** (0.45) sets the odds above which `safe_step` treats an adjacent enemy as a threat. 0.3 was tested twice and was noise both times (+4.2 in a campaign-1 screen, −2.2 in campaign 2), so 0.45 stays.
- **`hunt_bonus`** (0.1, the `hunt` plan's prior) was raised by the retired Splitter-HMM against splitting opponents; it is now a fixed constant.
- **Removed after measurement** (every result is in [15 · Failed strategies](15_failed_strategies.md)):
  - campaign 1: the hybrid "no split" rules `split_enemy_dist` and `prize_lock`, and the pre-emptive plan families deny, ambush, shield and tempo;
  - campaign 2: pincer kills, exact detachment selection, safe corridors, house tours, interception, covered detachments and the group cap.
