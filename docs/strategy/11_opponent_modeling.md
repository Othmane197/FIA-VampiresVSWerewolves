# 11 · Opponent modelling with Hidden Markov Models

**Goal.** Predict the opponent's next move from its past behaviour, and use the prediction in our
decisions.

**Everything is implemented in plain Python:** the PDF forbids AI libraries. The forward
algorithm, Baum-Welch and Bayesian inverse planning are written from scratch in
[splitter/opponent_model.py](../../splitter/opponent_model.py).

**Status: built, measured, and off by default** (`SplitterAgent(opponent_model=True)` switches it
on).
- The predictions are accurate: 43–97% of enemy group steps predicted exactly, depending on the bot.
- But using them did not raise the win rate against our panel (11.8).
- The work did uncover a real search bug, worth +2.2 points; the fix is on for everyone (11.7).

## 11.1 Why: opponents are very different

Measured from arena game logs (chapter 07):

| Opponent | Splits | Attacks at < 50% odds | Moves toward us |
|---|---|---|---|
| Apex | 0% | 0% (only sure kills) | 38% |
| RaceMCTS | 11% | 15% | 50% |
| Greedy / Starter | 0% | 40–57% | about 90% |
| TacticalSplitter | 4% | 88% | 29% |

Our search modelled every opponent the same way. A model that recognizes *who* we are playing
should search the right replies and take the right risks.

## 11.2 Observing the opponent: [splitter/observe.py](../../splitter/observe.py)

The server never reports the opponent's moves. [`reconstruct_flows`](../../splitter/observe.py#L134)
rebuilds them from two boards: *mid* (right after our move) and *after* (now).

- **Enemy creatures only move on their own turn,** so the gains and losses per cell, with Rule 5 (a cell that received creatures was not a source), determine the creature flows.
- **Demands are served by certainty:** plain moves and sure results first, random battles last.
- **An exact-fit pre-pass avoids inventing splits** from crossing assignments.

Each turn becomes four discrete features, computed by [`features_from_flows`](../../splitter/observe.py#L60):

| Feature | Values |
|---|---|
| `split` | no / yes |
| `attack` | none / sure / coin flip / long shot |
| `heading` | toward us / toward a house / away / merge / idle (weighted by creature count) |
| `converted` | no / yes |

[`plan_features`](../../splitter/observe.py#L128) applies the same function to *hypothetical*
moves. [`OpponentTracker`](../../splitter/observe.py#L222) keeps the board at our last decision and
our moves.

**Accuracy:** features rebuilt from boards agree with the true moves on **≥ 99.6% of turns for
every bot** (224 recorded games, `tools/opponent_report.py`).

## 11.3 Style HMM: who is the opponent? ([`StyleHMM`](../../splitter/opponent_model.py#L91))

- **Hidden modes:** EXPAND, HUNT, GAMBLE, DEFEND, SPLITFARM. Trained modes need not keep these names.
- **Emissions:** factored (naive Bayes) over the 4 features.
- **Transitions:** sticky; one matrix per game phase (humans left or not), a small input-output HMM.
- **Online:** a forward step each turn ([`update`](../../splitter/opponent_model.py#L131)) gives the belief. The emission tables adapt to this opponent (Dirichlet counts with forgetting).
- **Exposed through `OpponentModel`:** the predicted feature distribution, P(long shot) and the aggression.

**Offline training:** [`baum_welch`](../../splitter/opponent_model.py#L229) (scaled forward-backward,
[`_forward_backward`](../../splitter/opponent_model.py#L177)), run by
[tools/train_opponent_model.py](../../tools/train_opponent_model.py) on recorded games.
- Trained on Apex, Grabber, Greedy, RaceMCTS, Rusher and Splitter; held out: Expecti, TacticalSplitter, Starter.
- Held-out log-likelihood per turn: **−1.67 (hand-set) → −0.94 (trained)**.
- The trained parameters are stored as plain constants in `splitter/opponent_params.py`; [`load_params`](../../splitter/opponent_model.py#L64) falls back to [`default_params`](../../splitter/opponent_model.py#L44).

## 11.4 Goal recognition: where is each group going? ([`GoalRecognizer`](../../splitter/opponent_model.py#L292))

**Bayesian inverse planning.**
- **Hidden state:** each enemy group's target: a house it can convert, one of our groups, one of its own groups, or "flee".
- **Emission:** a rational-agent model. P(step | target) ∝ exp(β · distance reduction) over the 8 moves plus staying, with a small Manhattan tie-break toward the straight line ([`step_distribution`](../../splitter/opponent_model.py#L329)).
- **Transitions:** sticky; split parts inherit their parent's belief.

## 11.5 Policy HMM: which policy is it following? ([`PolicyHMM`](../../splitter/opponent_model.py#L460))

**The finding that shaped it:** different predictors win against different bots. The greedy
heuristic predicts Greedy and Starter at 90–96%, our own planner predicts RaceMCTS at 51%, and the
goal recognizer is best against Rusher.

So the hidden state is *which expert policy* the opponent follows:
- **GREEDY:** [`greedy_steps`](../../splitter/opponent_model.py#L405);
- **PLANNER:** our planner's top plan, [`planner_steps`](../../splitter/opponent_model.py#L444);
- **GOAL:** the goal recognizer;
- **AWAY:** [`away_steps`](../../splitter/opponent_model.py#L419).

The emission is the likelihood of the observed steps under each expert. Filtering is online expert
selection with switching, and the prediction is the belief-weighted mixture.

**Top-1 accuracy at predicting each enemy group's next cell:**

| Bot | Policy HMM | Best single predictor | Uniform |
|---|---|---|---|
| Apex | **43%** | 33% | 14% |
| Expecti | **53%** | 43% | 12% |
| Grabber | **57%** | 38% | 17% |
| Greedy / Starter | **92% / 97%** | 90% / 96% | 12% |
| RaceMCTS | 48% | 51% (planner) | 12% |
| TacticalSplitter | **35%** | 26% | 15% |

Top-3 accuracy is 67–99%.

## 11.6 How the predictions are used

| Use | Where | Measured effect | Default |
|---|---|---|---|
| **I1: search priors.** At opponent nodes, prior = (1−τ)·planner + τ·model ([`OpponentModel.score_plans`](../../splitter/opponent_model.py#L620)). Predicted replies are expanded first; PUCT selection | [`MCTS._plans`](../../splitter/mcts.py#L82), [`MCTS._select`](../../splitter/mcts.py#L97) | Helps against predictable bots (Greedy +5, TacticalSplitter +4), hurts against RaceMCTS (−9). So τ is now gated: the model only steers when its accuracy *this game* is above 55% ([`PolicyHMM.trust`](../../splitter/opponent_model.py#L533)) | off |
| **I2: rollouts.** A gambling opponent strikes first in rollouts ([`_strike`](../../splitter/mcts.py#L237)) | `MCTS._iterate` | Part of the model package | off |
| **I3: evaluation.** Against an opponent that never takes long shots, adjacent 30–50% threats are ignored (`exposure(strike_p=0.5)`) | [`exposure`](../../splitter/evaluate.py#L123) | Part of the model package | off |
| **I5: adaptive settings.** Passive non-gambler → `reserve_radius` − 2; aggressor or gambler → +1 and `safety_margin` + 1; splitter → hunt bonus | [`SplitterAgent._adapt_settings`](../../splitter/agent.py#L234) | +1.8 overall and +10.7 vs RaceMCTS, compared with the model without adaptation | on when the model is on |
| **I4: pre-emptive plans** (deny, ambush, shield, tempo) | [`_preempt_orders`](../../splitter/planner.py#L548) | **−3.9 pts** | off (`preempt=""`) |
| **I6: pre-game analysis** (`main.py --pregame`) | [`SplitterAgent.pregame`](../../splitter/agent.py#L215) | See chapter 08 | off |

## 11.7 Side discovery: a search bug (fixed, on by default)

While integrating the model, `last_error` revealed that the open-loop MCTS sometimes **applied a
stored plan that was illegal in the current sampled future**: a group had died in a random battle
earlier in this iteration. `State.apply` then raised, the whole search for that turn was lost, and
the safety net played the plain fallback move.

**How often:** this happened on **4.1% of v5's turns.** The fix checks the plan at expansion, as
the descent step already did ([`MCTS._iterate`](../../splitter/mcts.py#L148)).

**Effect** (paired, 504 games):
- **+2.2 points** against the panel;
- **61.6%** head-to-head against v5;
- RaceMCTS 66% → 73%, Expecti 69% → 81%.

## 11.8 Verdict

**Measured setup:** 0.2 s per move, 504 games per configuration (9 opponents including the frozen
baseline `Snap:v5fix`, 14 maps, both species, 2 games), same seeds.

| Configuration | Overall | vs RaceMCTS |
|---|---|---|
| Bug fix only (the default) | **79.3%** | **73.2%** |
| + opponent model (UCT priors) | 78.4% | 67.9% |
| + opponent model (PUCT priors) | 79.6% | 64.3% |
| + trust gating + I3 + I5 | 78.6% | 69.6% |
| same, without I5 | 76.8% | 58.9% |
| + pre-emptive plans (I4) | 74.9% | 53.6% |
| map-aware deathball (model off) | 75.4% | 67.9% |

**Why accurate predictions did not translate into wins:**
- **Our search already assumed a strong, splitting, striking opponent.** Against the strong bots that is the right model, and narrowing it to "likely" replies under-explores their dangerous ones.
- **Against the weak bots there was little left to gain.**

**The model's value for the tournament** is against *unknown* opponents whose style differs from
our panel's: it learns within about 10 turns. That cannot be measured on our panel, so it stays an
opt-in switch.

## 11.9 Reproduce

```bash
python -m arena.run --bot Splitter --maps all --games 1 --time 0.15 --save-all-logs   # record games
python tools/opponent_report.py arena/results/traces/<run>          # prediction accuracy per bot
python tools/train_opponent_model.py arena/results/traces/<run> --policy-grid   # train the style HMM
python -m arena.run --bot Splitter "Splitter:opponent_model=1" --panel fast --games 2 --time 0.2   # A/B
python -m unittest tests.test_opponent_model
```
