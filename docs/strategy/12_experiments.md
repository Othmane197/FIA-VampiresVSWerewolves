# 12 · Improvement campaign: finding changes that reliably beat the baseline

**Goal:** after the opponent-model work (chapter 11), find changes that **reliably** beat the
baseline, **without over-fitting to our teammates' bots** (the tournament opponents are other
students' bots we have never seen).

**Baseline:** Splitter v6e defaults = v5 plus the open-loop search fix (chapter 11.7). That fix
alone is +2.2 points over v5.

## 12.1 Method

| Principle | How |
|---|---|
| **Separate tuning and validation data** | *Tuning:* RaceMCTS, Expecti and our own frozen baseline (`Snap:v5fix`), on the 14 tuning maps. *Validation:* opponents **never used for tuning** (Apex, TacticalSplitter, Grabber, Greedy, Starter, Rusher) plus two **style proxies** no teammate represents (a deathball version `splits=0` and an aggressive `gamble=always,c=0.9` version of our bot), on the 8 **hold-out maps** (`arena/maps.py` family `holdout`, fresh seeds, never looked at while tuning) |
| **Paired comparisons** | Every candidate plays exactly the same games (opponent, map, side, seed) as the baseline in **one shared pool**. `arena/run.py --bot A B C ...` prints the paired difference and its standard error (`compare`) |
| **Successive stages** | Screen many candidates fast (0.1 s/move), combine the best, validate on hold-out (0.2 s), replicate on fresh dice (`--seed`) |
| **Only general changes** | Search, evaluation and planner parameters, and generic strategy switches. No rule keyed to a specific bot |
| **Acceptance** | Positive on the tuning set, **not negative on the hold-out set**, and confirmed on fresh dice |

**Faster testing (new in `arena/run.py`):**
- one pool for all configurations, with the **longest games scheduled first**, so there are no idle-worker tails;
- `--panel fast` for screening;
- all 8 cores by default.

A 15-configuration screen (2,520 games) takes about 23 minutes.

## 12.2 Results

### Stage A: screening (tuning set, 0.1 s, 168 paired games per candidate)

| Candidate | Δ vs baseline | vs RaceMCTS |
|---|---|---|
| **opponent model without search steering** (`opponent_model=1,opp_priors=0`) | **+7.4 ± 3.4** | +17.9 |
| endgame kiting (`kite=1`) | +5.1 ± 3.8 | +17.0 |
| rollout depth 0 | +3.6 ± 3.7 | +7.1 |
| widening 4 / 1; prior weight 1.2; commitment 0.7 | +1.5 … +2.7 | — |
| max plans 12; danger weight 5; c = 0.4; prior weight 0.2 | −1.8 … −0.6 | — |
| exploration c = 0.9 | −3.0 ± 3.8 | — |
| rollout depth 4 | **−6.0 ± 4.0** | — |
| opponent model, adaptive settings only (`opp_eval=0`) | +0.3 ± 3.9 | — |

### Stage A2: combinations (tuning set, 0.1 s)

| Candidate | Δ vs baseline |
|---|---|
| opponent model without steering | **+10.4 ± 3.5** (reproduces Stage A) |
| kiting + rollout depth 0 | +11.3 ± 4.1 |
| model + kiting + `danger_strike_p=0.3` | +10.7 ± 3.6 |
| model + kiting + widening 4 | +7.7 ± 3.9 |
| model + kiting + rollout depth 0 | +7.4 ± 3.9 |
| model + kiting | +6.0 ± 3.8 |
| `danger_strike_p=0.3` (planner's step safety uses the 30% strike threshold) | +4.2 ± 3.8 |

**The gains do not stack:** combinations land at the level of the best single change.

### Stage B: validation (hold-out opponents and maps, 0.2 s, 256 paired games)

The baseline already scores 85–100% against the weak hold-out bots. Only the strong unseen styles
(the baseline scores 52% and 61% against them) leave room to discriminate.

| Candidate | Δ overall | vs aggressive proxy | vs deathball proxy |
|---|---|---|---|
| **opponent model without steering** | **+1.8 ± 2.0** | **+10.9** | **+12.5** |
| kiting + rollout depth 0 | −0.6 ± 2.0 | −3.1 | +1.6 |
| both combined | +0.4 ± 1.7 | +7.8 | −4.7 |

**Over-fitting caught:** "kiting + rollout depth 0" had the *best* tuning score (+11.3) and **no
effect on unseen opponents and maps**, so it was rejected.

### Stage C: replication on fresh dice

| Test | Result |
|---|---|
| Head-to-head vs the baseline itself (22 maps, 176 games, seed 5000) | 47.4% ± 3.8: neutral. Expected: against our own bot there is no risk style to exploit (the tuning runs vs `Snap:v5fix` were also neutral, +3.6 / +0.9) |
| Paired, all 10 non-self opponents, 22 maps (seed 7000, 440 games) | **+1.8 ± 1.7** (RaceMCTS +11.4, aggressive proxy +8.0, Grabber −5.7, Greedy −3.4) |
| **Pre-registered confirmatory test:** strong opponents only (RaceMCTS, Expecti, both proxies), 22 maps, seed 9000, 352 games. Hypothesis fixed *before* the run: "gains against strong opponents" | **−3.4 ± 2.5** (RaceMCTS −8.0, aggressive proxy −9.1): **hypothesis rejected** |

## 12.3 Verdict

| Change | Tuning set | Unseen data (pooled) | Decision |
|---|---|---|---|
| **Open-loop expansion fix** (chapter 11.7) | — | **+2.2 pts** over v5 on 504 paired games; **61.6%** head-to-head vs v5; clear mechanism (4.1% of turns were lost) | **adopted (default)** |
| Opponent model without search steering | +7.4, +10.4 | about **+0.6 ± 1.1**: B +1.8 ± 2.0, C +1.8 ± 1.7, confirmatory −3.4 ± 2.5 | off (opt-in) |
| Kiting + rollout depth 0 | +11.3 | −0.6 ± 2.0 | rejected |
| Every other parameter change | within ±3 | — | defaults kept |

**Lesson for the report.** Picking the best of 14 candidates on one set of games always produces
an impressive number (+7 to +11 here). Only validation on unseen opponents and maps, followed by
replication on fresh dice, separates a real improvement from luck. The two candidates that looked
best both failed it. The only change that survived is the one with a clear mechanism behind it.

## 12.4 Why the opponent model looked like it helped (hypothesis, not confirmed)

- **On the tuning set, Stage A attributed the gain to the *risk model*.**
  - adaptive settings alone: +0.3;
  - plus opponent strikes in rollouts (I2) and the opponent-specific strike threshold in the evaluation (I3): +7 to +10.
- **The static bot is over-cautious against some opponents.** Since v3 it assumed *every* opponent strikes first at ≥ 30% odds (the lesson from RaceMCTS). Against opponents that only take good odds (Apex, Grabber, deathball styles), it stayed out of contact and passed up conversions near enemy groups.
- **It under-modelled gamblers:** its rollouts never simulated a gambler's strike.
- **The style HMM measures what this opponent does** (P(long-shot attack)) within about 8 turns:
  - non-gamblers: threats are counted only at ≥ 50% odds;
  - gamblers: rollouts include their strikes.
- **Steering which replies are searched (I1) is what hurt,** because it under-explored the strong opponents' dangerous replies. It stays off.
- **On fresh dice the risk-model gain did not replicate.** The mechanism is plausible, but on our panel the effect is too small to measure. It remains an opt-in switch for opponents unlike our teammates' bots.
