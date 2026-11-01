# 19 · Campaign 6 (final iteration): hunted groups in the endgame

**Goal:** fix the one measured weakness left by campaign 5 (18.4, 18.6 item 1), choose the
strongest model as the flagship and the runner-up as the backup, and apply the choice. This is
the project's last improvement iteration.

## 19.1 The mechanism and its implementation

Once no humans are left, a group that a bigger enemy group kills for sure (at least 1.5 times
its size) is eventually caught: on a king-move board one pursuer always corners a single group.
Our evaluation did not see this. `exposure` ignores enemies more than 2 cells away, and 6-ply
rollouts end long before the group is cornered. The flagship lost 25 groups this way on
campaign 5's ladder (the backup 7), and in Harsha's thetrap wins our 6 + 2 never merged.

**New evaluation constant `hunted`** ([`EvalParams`](../../splitter/evaluate.py#L29), option
`eval_hunted=<λ>`, default 0 = off). In [`exposure`](../../splitter/evaluate.py#L142), once no
humans are left, a group loses at least λ · its size, at any distance, when both hold:
- some enemy group kills it for sure;
- none of its own side's groups kills that enemy for sure in turn.

It applies to both sides, so hunting the enemy's stray splinters gains value too. It is the
maximum with the existing adjacent-strike risk, not an addition, so nothing is counted twice.
The cost is one comparison per pair of groups.

*The option failed its validation (19.4) and was deleted from the code afterwards, with its
unit test. The campaign's code, option included, is frozen in the local snapshot
`arena/snapshots/splitter_c6/` (`Snap:c6:eval_hunted=1.0` in the arena).*

## 19.2 Checks before any validation game

- **Inert when off:** with λ = 0 both models make the same decisions as their frozen versions on 300 of 300 test positions (`Snap:c3` for the flagship, `Snap:v7` for the backup).
- **The puzzle:** in the thetrap position (6 + 2 against 9, no humans), the static values become 0.40 merged against 0.03 split (λ = 0.5) and 0.00 split (λ = 1.0); without the term both are 0.40. The search then plans to merge while retreating. Unit test `TestHunted` covers the merge, the "at any distance" case, the deterrence of a group big enough to kill the hunter, and "off while humans are left".
- **Decisions on the 300 positions:** λ = 0.5 / 1.0 change 71 / 74 of the flagship's decisions and 35 / 49 of the backup's. Almost all of these positions still have humans: the search looks ahead into endgames, and small value changes reorder near-equal plans.
- **thetrap replay** (6 games against Harsha-1core, seed 15000, diagnostic): 0 – 1 – 5 without the term, 0 – 1 – 5 with λ = 0.5, **2 – 1 – 3 with λ = 1.0**. Against RaceMCTS-live: 3 – 0 – 3 without, 3 – 1 – 2 with either λ.
- The teammates' branches were fetched before the run: no new commits since campaign 5. The real-conditions matches use `--no-update`, so the whole run works offline.

## 19.3 Decision rules, written before the games

No screen: the tuning screens' noise (about ±6 per comparison) is larger than the expected
effect of a term that acts only in endgames. The 160 games per bot go to unused data instead.

1. **Validation V** (`fresh3`, still unused; Apex-live, RaceMCTS-live, Expecti-live, Harsha-1core, Styled:19–24, still unused; both sides; 1.5 s; `--seed 12000`; no early stopping; 160 games per bot). Bots:
   - the flagship `Splitter` (R3);
   - `Splitter:eval_hunted=0.5` and `Splitter:eval_hunted=1.0`;
   - the backup `Splitter-Classic`;
   - `Splitter-Classic:eval_hunted=1.0`.
2. **Flagship:** a candidate qualifies if its paired difference to `Splitter` is positive and above 1.0 SE, with 0 timeouts, illegal moves or crashes. Of the qualifying candidates, the one with the larger difference becomes the flagship; otherwise the flagship stays R3. The bar is 1.0 SE, not campaign 5's 1.5 SE, for three reasons:
   - the mechanism was measured before building it;
   - the term changes the evaluation only once no humans are left;
   - there is no screen whose games could be pooled.
3. **The Classic line:** `Splitter-Classic:eval_hunted=1.0` replaces the Classic by the same rule (positive, above 1.0 SE against `Splitter-Classic`, 0 problems).
4. **Backup = the runner-up**, the second-strongest distinct model.
   - If the flagship changed, the backup is whichever of R3 and the best Classic line has the larger paired difference against the new flagship on the validation games.
   - Otherwise it is the best Classic line.
   - λ-variants of the chosen flagship are not distinct models.
5. **Real conditions R:** every chosen model not yet played under real conditions plays `tools/teammate_matches.py --no-update` (4 games against each of Apex-live, RaceMCTS-live, Expecti-live and Harsha-1core; with `--options eval_hunted=<λ>`). R3 and the Classic passed in earlier campaigns. Any timeout or illegal move cancels that model:
   - the flagship falls back to R3, and the backup is recomputed by rule 4;
   - a cancelled Classic line falls back to R3 if the flagship changed, otherwise to the Classic.
6. **Apply:** the run writes the chosen models into `MODELS` in `splitter/agent.py` and runs the unit tests. Any failure or error (unexpected successes are allowed) restores the previous `MODELS`. The result goes in `c6_state.json` and `c6_run.log` in the session scratchpad.

## 19.4 Results

Run unattended from 31 October 23:13 to 1 November 07:51 (`c6_run.py` in the session scratchpad,
below-normal priority, 3 workers, offline). CSV: `arena/results/c6_validation.csv`.

### Validation V (`fresh3`, Styled:19–24, live bots, 160 games per bot; rule 1)

| Bot | Score | Live bots (64 games) | Styled (96 games) | Problems |
|---|---|---|---|---|
| **`Splitter`** (R3, the flagship) | **73.4%** | 68.0% | 77.1% | 12 timeouts in 3 games (see below) |
| `Splitter:eval_hunted=0.5` | 72.8% | 65.6% | 77.6% | 0 |
| `Splitter:eval_hunted=1.0` | 69.4% | 55.5% | 78.6% | 0 |
| **`Splitter-Classic`** (the backup) | 62.5% | **71.1%** | 56.8% | 0 |
| `Splitter-Classic:eval_hunted=1.0` | 62.5% | 74.2% | 54.7% | 0 |

| Paired comparison (same games) | All | Live bots | Styled | Rule |
|---|---|---|---|---|
| `eval_hunted=0.5` − flagship | −0.6 ± 3.9 | −2.3 ± 7.6 | +0.5 ± 4.2 | 2: does not qualify |
| `eval_hunted=1.0` − flagship | −4.1 ± 4.1 | **−12.5 ± 7.2** | +1.6 ± 4.8 | 2: does not qualify |
| Classic `eval_hunted=1.0` − Classic | 0.0 ± 3.7 | +3.1 ± 5.9 | −2.1 ± 4.7 | 3: does not qualify |
| Flagship − Classic | **+10.9 ± 4.6** | −3.1 ± 7.9 | +20.3 ± 5.5 | — |

**By rules 2–4, the flagship stays R3 and the backup (the runner-up) stays the Classic.** No
model was new, so by rule 5 there were no real-conditions matches. By rule 6 the run left
`splitter/agent.py` untouched.

**The 12 timeouts of the flagship were caused by the machine, not by the bot:**
- **Same moment:** they came in three games that ran at the same time, one per worker (rows 195–197 of the CSV), on `f3_13x23v` against Styled:23 and Styled:24, with moves of 2.2 to 4.3 s.
- **Both sides slowed:** in the same games the opponents' searches timed out too (1 and 4 times).
- **Same clock time as a Windows Update:** a download started at 01:30 and an install at 01:59, about a quarter of the way into the run.
- **Nowhere else:** in all other games no bot exceeded 1.60 s.

Without those three game slots, the comparisons are −1.0 ± 4.0 (λ = 0.5) and −4.5 ± 4.2
(λ = 1.0): the decision does not depend on them.

**Did the term do what it was built for?** Partly. Groups lost to a sure kill once no humans
were left, while the merged total would have been safe (counted as in 18.6): flagship 9, λ = 0.5
12, λ = 1.0 5. The weakness was much rarer on these maps than on campaign 5's ladder (25), and
λ = 1.0, while it cut those losses, lost more groups overall (66 against 49) and scored 12.5
points worse against the live bots. Counting hunted groups as lost also makes the search treat
the enemy's hunted groups as already won. It then chases them, and leaves its own groups in
reach of the intelligent opponents (likely reason, not measured).

## 19.5 Conclusion: the final models

- **Flagship `Splitter` = Splitter-R3** (unchanged since campaign 3), **backup `Splitter-Classic`** = the campaign-2 flagship, v7 (unchanged). After the option was deleted, both make the same decisions as their frozen versions on 300 of 300 test positions; 48 tests pass (1 expected failure).
- **The flagship is the strongest version measured.** Against the backup on four untouched map families (campaigns 3 to 6: `fresh`, `fresh2`, `fresh4`, `fresh3`) it scores +8.0 ± 3.9, +9.0 ± 4.9, +5.3 ± 4.0 and +10.9 ± 4.6. Inverse-variance pooled: **+8.0 ± 2.1** (3.8 SE). It also beat v5 on the campaign-5 ladder (+5.3 ± 4.5).
- **The backup is the runner-up, and a real alternative.** Its advantage over the flagship lies elsewhere: against the teammates' live bots the two are level (flagship − backup pooled over the four families **+1.1 ± 3.5**), while the flagship's margin comes from the randomized styles (+12.4 ± 2.6). The backup scored better against the live bots on this validation (71.1% against 68.0%). If the tournament field turns out to be bots very like the teammates', the backup is not a weaker choice.
- **This was the last iteration.** Since campaign 3, every proposed improvement has failed its validation on unused data: campaign 4's fixes, campaign 5's thinking time and Harsha's settings, and this hunted-group term. The flagship is at a robust local optimum for changes that can be built and validated in a night. What is left (the contact solver, deeper transit rollouts, the endgame solver, pooled threats; 18.6) would need new mechanisms and several validation rounds.
