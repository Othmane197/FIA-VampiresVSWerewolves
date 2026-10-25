# 11 · Opponent modelling with Hidden Markov Models (retired)

**Goal.** Predict the opponent's behaviour from its past moves, and use the prediction in our
decisions.

**Everything was implemented in plain Python:** the PDF forbids AI libraries. The forward
algorithm and Baum-Welch were written from scratch (`splitter/opponent_model.py`, now removed).

**Status: retired (2026-10-21). This chapter is the record of the work.**
- The **style HMM** (sections 11.2–11.5) was the campaign-1 runner-up, "Splitter-HMM". It was neutral at 0.2 s per move but **worse at the tournament's 1.5 s: −14.8 ± 4.9 and −4.8 ± 7.7, pooled −11.9 ± 4.1** (chapters 08.2 and 14.3). Campaign 2 replaced it as the backup with the calibrated evaluation, and its code was removed.
- The **goal recognizer**, the **policy HMM** and the uses that steered the search or added pre-emptive plans were measured, **did not help**, and were deleted earlier (11.6–11.7).
- **Where the code is:** the cleaned style HMM in the local snapshot `arena/snapshots/splitter_v7/` (`observe.py`, `opponent_model.py`, `opponent_params.py`; playable as `"Snap:v7:opponent_model=1"`) and in `arena/snapshots/splitter_c2/`; the full version with the goal recognizer and the policy HMM in git commit `79fd09c`.
- The work uncovered a real search bug, worth +2.2 points; that fix is in the flagship (11.8).

## 11.1 Why: opponents are very different

Measured from arena game logs (chapter 07):

| Opponent | Splits | Attacks at < 50% odds | Moves toward us |
|---|---|---|---|
| Apex | 0% | 0% (only sure kills) | 38% |
| RaceMCTS | 11% | 15% | 50% |
| Greedy / Starter | 0% | 40–57% | about 90% |
| TacticalSplitter | 4% | 88% | 29% |

The flagship models every opponent the same way: an equally clever splitter that strikes first
whenever adjacent at ≥ 30% odds. A model that recognizes *how this opponent takes risks* could
take the right risks against it.

## 11.2 Observing the opponent: `splitter/observe.py`

The server never reports the opponent's moves. `reconstruct_flows`
rebuilds them from two boards: *mid* (right after our move) and *after* (now).

- **Enemy creatures only move on their own turn,** so the gains and losses per cell, with Rule 5 (a cell that received creatures was not a source), determine the creature flows.
- **Demands are served by certainty:** plain moves and sure results first, random battles last.
- **An exact-fit pre-pass avoids inventing splits** from crossing assignments; the remaining demands are served best-fit.

Each turn becomes four discrete features, computed by `features_from_flows`:

| Feature | Values |
|---|---|
| `split` | no / yes |
| `attack` | none / sure / coin flip / long shot |
| `heading` | toward us / toward a house / away / merge / idle (weighted by creature count) |
| `converted` | no / yes |

`OpponentTracker` keeps the board at our last decision and our
moves, and produces one `TurnObservation` per enemy turn.

**Accuracy:** features rebuilt from boards agree with the true moves on **≥ 99.6% of turns for
every bot** (224 recorded games, `tools/opponent_report.py`).

## 11.3 Style HMM: how does the opponent play? (`StyleHMM`)

- **Hidden modes:** EXPAND, HUNT, GAMBLE, DEFEND, SPLITFARM. Trained modes need not keep these names.
- **Emissions:** factored (naive Bayes) over the 4 features: P(o | z) = Π_f P(o_f | z).
- **Transitions:** sticky; one matrix per game phase (`phase_of`: humans left or not), a small input-output HMM.
- **Online:** a forward step each turn (`StyleHMM.update`) gives the belief. The emission tables adapt to this opponent (Dirichlet counts with forgetting 0.97, prior strength 30).
- **Prediction:** `StyleHMM.predict_features`, the feature distribution expected next turn.

**Offline training:** `baum_welch` (scaled forward-backward,
`_forward_backward`), run by
`tools/train_opponent_model.py` on recorded games.
- Trained on Apex, Grabber, Greedy, RaceMCTS, Rusher and Splitter; held out: Expecti, TacticalSplitter, Starter.
- Held-out log-likelihood per turn: **−1.67 (hand-set) → −0.94 (trained)**.
- The trained parameters are stored as plain constants in `splitter/opponent_params.py` (no file I/O on the tournament machine). `load_params` falls back to `default_params`. The trainer only writes the file if the held-out likelihood improves.

## 11.4 The risk profile: `OpponentModel`

The runner-up did not need the mode names, only three numbers derived from the predicted attack
feature:

| Quantity | Definition | Used for |
|---|---|---|
| `p_gamble` | P(coin-flip or long-shot attack \| attack) | Opponent strikes in our rollouts (chapter 05.5) |
| `p_longshot` | P(long-shot attack \| attack) | Exposure threshold 0.5 against careful opponents (chapter 04.6) |
| `tendencies` | aggression (heading toward us), split rate, long-shot rate, turns observed | Adaptive settings (chapter 06.5) |

## 11.5 How the runner-up used it

| Use | Where | Measured effect |
|---|---|---|
| **Rollouts:** a gambling opponent strikes first in our rollouts | `MCTS._read_opponent_model`, `_strike` | Together with the next row: the gain on the tuning set (+7 to +10, chapter 12.4) |
| **Evaluation:** against an opponent never seen taking long shots, adjacent 30–50% threats are ignored (`exposure(strike_p=0.5)`) | [`exposure`](../../splitter/evaluate.py#L142) | (see above) |
| **Adaptive settings:** passive non-gambler → `reserve_radius` − 2; aggressor or gambler → +1 and `safety_margin` + 1; splitter → hunt bonus | `SplitterAgent._adapt_settings` | +1.8 overall and +10.7 vs RaceMCTS, compared with the model without adaptation |

## 11.6 Archive: removed predictors (deleted from the code after measurement)

**Goal recognizer (Bayesian inverse planning).**
- Hidden state: each enemy group's target (a house it can convert, one of our groups, one of its own groups, or "flee").
- Emission: a rational-agent model, P(step | target) ∝ exp(β · distance reduction) over the 8 moves plus staying, with a Manhattan tie-break toward the straight line.
- Transitions: sticky; split parts inherited their parent's belief.

**Policy HMM: which expert policy is the opponent following?**
- The finding that shaped it: different predictors win against different bots. The greedy heuristic predicted Greedy and Starter at 90–96%, our own planner predicted RaceMCTS at 51%, and the goal recognizer was best against Rusher.
- Hidden state: GREEDY, PLANNER (our planner's top plan), GOAL (the goal recognizer), AWAY. Emission = the likelihood of the observed steps under each expert; filtering = online expert selection with switching; trust τ = the model's accuracy *this game*.

**Top-1 accuracy at predicting each enemy group's next cell:**

| Bot | Policy HMM | Best single predictor | Uniform |
|---|---|---|---|
| Apex | **43%** | 33% | 14% |
| Expecti | **53%** | 43% | 12% |
| Grabber | **57%** | 38% | 17% |
| Greedy / Starter | **92% / 97%** | 90% / 96% | 12% |
| RaceMCTS | 48% | 51% (planner) | 12% |
| TacticalSplitter | **35%** | 26% | 15% |

Top-3 accuracy was 67–99%. **Accurate predictions, but no use of them won games** (11.7), so the
code was removed. It is preserved in git commit `79fd09c` ("New Patch HMM Experiment"), for
example `git show 79fd09c:splitter/opponent_model.py`.

## 11.7 Archive: removed uses of the predictions

| Use | Measured effect | Likely reason (hypothesis) |
|---|---|---|
| **I1: search priors.** At opponent nodes, prior = (1−τ)·planner + τ·model, PUCT selection, trust-gated (τ only above 55% accuracy) | Greedy +5, TacticalSplitter +4, **RaceMCTS −9** | Under-explores the strong opponents' dangerous replies |
| **I4: pre-emptive plans:** *deny* (reach a predicted target first), *ambush* (wait at 1.5·(e+h) next to the house an enemy will convert), *shield* (pull back a predicted target), *tempo* (hold distance 2 to get the first strike) | **−3.9 pts** | Acting on a wrong prediction costs a whole plan; MCTS already finds the useful cases |
| **I6: pre-game analysis** (`main.py --pregame`, a longer first-move search) | **−4.7 pts** (arena equivalent) | The first move is rarely decisive; the extra time bought nothing |
| **Map-aware deathball** (no splits on prize-dominated maps) | **−3.9 pts** | The map classifier was too coarse; the search already declines bad splits |

**Measured setup:** 0.2 s per move, 504 games per configuration (9 opponents including the frozen
baseline `Snap:v5fix`, 14 maps, both species, 2 games), same seeds.

| Configuration | Overall | vs RaceMCTS |
|---|---|---|
| Bug fix only (now the flagship) | **79.3%** | **73.2%** |
| + opponent model (UCT priors) | 78.4% | 67.9% |
| + opponent model (PUCT priors) | 79.6% | 64.3% |
| + trust gating + I3 + I5 | 78.6% | 69.6% |
| same, without I5 | 76.8% | 58.9% |
| + pre-emptive plans (I4) | 74.9% | 53.6% |
| map-aware deathball (model off) | 75.4% | 67.9% |

**Why accurate predictions did not translate into wins:**
- **Our search already assumed a strong, splitting, striking opponent.** Against the strong bots that is the right model, and narrowing it to "likely" replies under-explores their dangerous ones.
- **Against the weak bots there was little left to gain.**

The configuration that survived as the runner-up is "model **without** search steering": only the
risk hooks of 11.5. Its validation is in chapter 12.

## 11.8 Side discovery: a search bug (fixed, in the flagship)

While integrating the model, `last_error` revealed that the open-loop MCTS sometimes **applied a
stored plan that was illegal in the current sampled future**: a group had died in a random battle
earlier in this iteration. `State.apply` then raised, the whole search for that turn was lost, and
the safety net played the plain fallback move.

**How often:** this happened on **4.1% of v5's turns.** The fix checks the plan at expansion, as
the descent step already did ([`MCTS._iterate`](../../splitter/mcts.py#L157)).

**Effect** (paired, 504 games):
- **+2.2 points** against the panel;
- **61.6%** head-to-head against v5;
- RaceMCTS 66% → 73%, Expecti 69% → 81%.

## 11.9 Reproduce

The code lives in the local snapshot `arena/snapshots/splitter_v7/`:

```bash
python -m arena.run --bot Splitter "Snap:v7:opponent_model=1" --slots arena/slots/holdout.json --time 1.5 --hard 2.0 --workers 4
```

The recording and training tools (`tools/opponent_report.py`, `tools/train_opponent_model.py`)
were removed with the model; they are in git commit `79fd09c`.
