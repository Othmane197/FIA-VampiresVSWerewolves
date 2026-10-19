"""
Opponent modelling with Hidden Markov Models (plain Python, no AI library).

1. StyleHMM: WHO is the opponent? Hidden mode z in MODES, observed through the four turn
   features of observe.py with a factored (naive-Bayes) emission P(o|z) = prod_f P(o_f|z).
   Transitions are sticky and depend on the game phase (humans left or not): a small
   input-output HMM. Online: forward filtering gives a belief b_t(z) every turn; the emission
   tables adapt to the current opponent (Dirichlet counts with forgetting); a TRUST score
   measures how well the model actually predicts this opponent. Offline: baum_welch() trains
   the starting parameters on arena games (tools/train_opponent_model.py).

2. GoalRecognizer: WHERE is each enemy group going? Bayesian inverse planning: the hidden state
   of a group is its target (a house it can convert, one of our groups, one of its own groups to
   merge with, or "flee"); a group heading for target g takes a step with probability
   proportional to exp(beta * (distance reduction towards g)). Sticky transitions let it change
   its mind. It predicts each group's next cell.

3. OpponentModel ties both to observe.OpponentTracker and produces Predictions for the planner,
   the search and the evaluation.
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .observe import FEATURES, OpponentTracker, TurnObservation
from .rules import Pos, cheb
from .state import State

MODES = ("EXPAND", "HUNT", "GAMBLE", "DEFEND", "SPLITFARM")
K = len(MODES)
N_PHASES = 2                       # 0: humans are left on the board, 1: no humans left
ObsVec = Tuple[int, int, int, int]


def phase_of(state: State) -> int:
    """Game phase used by the transitions: 0 while humans remain, 1 after."""
    return 0 if state.humans else 1


# ---------------------------------------------------------------------------- parameters

def default_params() -> dict:
    """Hand-set starting parameters, from the behaviour measured in arena logs (chapter 11)."""
    B = [
        # split: [no, yes]
        [[0.98, 0.02], [0.98, 0.02], [0.97, 0.03], [0.98, 0.02], [0.65, 0.35]],
        # attack: [none, sure, coin, long shot]
        [[0.90, 0.08, 0.015, 0.005], [0.70, 0.20, 0.07, 0.03], [0.60, 0.10, 0.15, 0.15],
         [0.95, 0.04, 0.007, 0.003], [0.90, 0.07, 0.02, 0.01]],
        # heading: [toward us, toward house, away, merge, idle]
        [[0.15, 0.65, 0.05, 0.05, 0.10], [0.70, 0.10, 0.05, 0.05, 0.10], [0.60, 0.15, 0.05, 0.05, 0.15],
         [0.10, 0.20, 0.50, 0.10, 0.10], [0.15, 0.55, 0.10, 0.10, 0.10]],
        # converted: [no, yes]
        [[0.70, 0.30], [0.90, 0.10], [0.90, 0.10], [0.90, 0.10], [0.65, 0.35]],
    ]
    stay = 0.9
    A = [[[stay if i == j else (1 - stay) / (K - 1) for j in range(K)] for i in range(K)]
         for _ in range(N_PHASES)]
    marginal = [[sum(B[f][z][v] for z in range(K)) / K for v in range(card)]
                for f, (_, card) in enumerate(FEATURES)]
    return {"pi": [1.0 / K] * K, "A": A, "B": B, "marginal": marginal}


def load_params() -> dict:
    """Trained parameters if tools/train_opponent_model.py produced them, else the defaults."""
    try:
        from .opponent_params import PARAMS  # generated file, plain constants
        return PARAMS
    except ImportError:
        return default_params()


def _normalize(v: List[float]) -> List[float]:
    s = sum(v)
    if s <= 0:
        return [1.0 / len(v)] * len(v)
    return [x / s for x in v]


# ---------------------------------------------------------------------------- style HMM

class StyleHMM:
    """Online opponent-style HMM: forward filtering + adaptive emissions + trust."""

    def __init__(self, params: Optional[dict] = None, prior_strength: float = 30.0, forget: float = 0.97):
        """`prior_strength` = how many turns of evidence the starting emissions are worth."""
        p = params or load_params()
        self.pi = list(p["pi"])
        self.A = [[list(r) for r in ph] for ph in p["A"]]
        self.B0 = [[list(r) for r in bf] for bf in p["B"]]
        self.marginal = [list(m) for m in p.get("marginal", default_params()["marginal"])]
        self.prior_strength = prior_strength
        self.forget = forget
        self.reset()

    def reset(self):
        """New game: uniform-prior belief, emissions back to the starting tables."""
        self.belief = list(self.pi)
        self.evidence = [[[0.0] * len(r) for r in bf] for bf in self.B0]   # learned counts
        self.B = [[list(r) for r in bf] for bf in self.B0]
        self.turns = 0
        self.llr_ema = 0.0              # log-likelihood ratio of our predictions vs the marginal

    def emission(self, obs: ObsVec) -> List[float]:
        """P(obs | z) for every mode z."""
        out = [1.0] * K
        for f, v in enumerate(obs):
            bf = self.B[f]
            for z in range(K):
                out[z] *= bf[z][v]
        return out

    def predicted_belief(self, phase: int) -> List[float]:
        """Belief over the opponent's mode for its NEXT turn."""
        A = self.A[phase]
        return [sum(self.belief[i] * A[i][j] for i in range(K)) for j in range(K)]

    def predict_features(self, phase: int) -> List[List[float]]:
        """For each feature, the predicted distribution of its value on the opponent's next turn."""
        b = self.predicted_belief(phase)
        return [[sum(b[z] * self.B[f][z][v] for z in range(K)) for v in range(card)]
                for f, (_, card) in enumerate(FEATURES)]

    def update(self, obs: ObsVec, phase: int) -> List[float]:
        """Forward step with a new observation; returns the new belief."""
        pred = self.predict_features(phase)
        p_model = 1.0
        p_base = 1.0
        for f, v in enumerate(obs):
            p_model *= max(pred[f][v], 1e-9)
            p_base *= max(self.marginal[f][v], 1e-9)
        llr = math.log(p_model / p_base)
        self.llr_ema = llr if self.turns == 0 else 0.8 * self.llr_ema + 0.2 * llr
        prior = self.predicted_belief(phase)
        e = self.emission(obs)
        self.belief = _normalize([prior[z] * e[z] for z in range(K)])
        # online adaptation of the emissions to THIS opponent (Dirichlet counts with forgetting)
        for f, v in enumerate(obs):
            ev = self.evidence[f]
            for z in range(K):
                row = ev[z]
                for i in range(len(row)):
                    row[i] *= self.forget
                row[v] += self.belief[z]
                total = sum(row)
                base = self.B0[f][z]
                denom = self.prior_strength + total
                self.B[f][z] = [(self.prior_strength * base[i] + row[i]) / denom for i in range(len(row))]
        self.turns += 1
        return self.belief

    @property
    def trust(self) -> float:
        """How much to rely on the model: 0 (ignore) .. 0.8, from its recent predictive gain."""
        ramp = min(1.0, self.turns / 6.0)
        gain = max(0.0, min(1.0, self.llr_ema / 1.0))
        return 0.8 * ramp * gain

    def mode_probs(self) -> Dict[str, float]:
        """The current belief as {mode name: probability}."""
        return {MODES[z]: self.belief[z] for z in range(K)}


# ---------------------------------------------------------------------------- Baum-Welch

def _forward_backward(params: dict, seq: Sequence[Tuple[ObsVec, int]]):
    """Scaled forward-backward: (gammas, xis per transition with its phase, log-likelihood)."""
    pi, A, B = params["pi"], params["A"], params["B"]
    T = len(seq)
    em = []
    for obs, _ in seq:
        e = [1.0] * K
        for f, v in enumerate(obs):
            for z in range(K):
                e[z] *= B[f][z][v]
        em.append(e)
    alpha = []
    scale = []
    a = [pi[z] * em[0][z] for z in range(K)]
    c = sum(a) or 1e-300
    alpha.append([x / c for x in a])
    scale.append(c)
    for t in range(1, T):
        At = A[seq[t][1]]
        prev = alpha[-1]
        a = [sum(prev[i] * At[i][j] for i in range(K)) * em[t][j] for j in range(K)]
        c = sum(a) or 1e-300
        alpha.append([x / c for x in a])
        scale.append(c)
    beta = [[1.0] * K for _ in range(T)]
    for t in range(T - 2, -1, -1):
        At = A[seq[t + 1][1]]
        nxt = beta[t + 1]
        beta[t] = [sum(At[i][j] * em[t + 1][j] * nxt[j] for j in range(K)) / scale[t + 1] for i in range(K)]
    gammas = [_normalize([alpha[t][z] * beta[t][z] for z in range(K)]) for t in range(T)]
    xis = []
    for t in range(T - 1):
        At = A[seq[t + 1][1]]
        x = [[alpha[t][i] * At[i][j] * em[t + 1][j] * beta[t + 1][j] / scale[t + 1] for j in range(K)]
             for i in range(K)]
        s = sum(sum(r) for r in x) or 1e-300
        xis.append((seq[t + 1][1], [[v / s for v in r] for r in x]))
    loglik = sum(math.log(c) for c in scale)
    return gammas, xis, loglik


def sequence_loglik(params: dict, seq: Sequence[Tuple[ObsVec, int]]) -> float:
    """log P(sequence | params): the held-out validation score."""
    if not seq:
        return 0.0
    return _forward_backward(params, seq)[2]


def baum_welch(sequences: Sequence[Sequence[Tuple[ObsVec, int]]], params: Optional[dict] = None,
               iters: int = 40, tol: float = 1e-4, smoothing: float = 0.5):
    """
    EM training of the style HMM on many observation sequences (one per opponent per game).
    Returns (params, log-likelihood history). The likelihood never decreases (up to smoothing).
    """
    params = params or default_params()
    params = {"pi": list(params["pi"]), "A": [[list(r) for r in ph] for ph in params["A"]],
              "B": [[list(r) for r in bf] for bf in params["B"]]}
    seqs = [s for s in sequences if s]
    history = []
    for _ in range(iters):
        pi_acc = [smoothing] * K
        A_acc = [[[smoothing] * K for _ in range(K)] for _ in range(N_PHASES)]
        B_acc = [[[smoothing] * card for _ in range(K)] for _, card in FEATURES]
        total = 0.0
        for seq in seqs:
            gammas, xis, ll = _forward_backward(params, seq)
            total += ll
            for z in range(K):
                pi_acc[z] += gammas[0][z]
            for ph, x in xis:
                for i in range(K):
                    for j in range(K):
                        A_acc[ph][i][j] += x[i][j]
            for t, (obs, _) in enumerate(seq):
                g = gammas[t]
                for f, v in enumerate(obs):
                    for z in range(K):
                        B_acc[f][z][v] += g[z]
        history.append(total)
        params["pi"] = _normalize(pi_acc)
        params["A"] = [[_normalize(r) for r in ph] for ph in A_acc]
        params["B"] = [[_normalize(r) for r in bf] for bf in B_acc]
        if len(history) > 1 and abs(history[-1] - history[-2]) < tol * abs(history[-2]):
            break
    marg = [[0.0] * card for _, card in FEATURES]
    n = 0
    for seq in seqs:
        for obs, _ in seq:
            n += 1
            for f, v in enumerate(obs):
                marg[f][v] += 1
    params["marginal"] = [_normalize([m + 0.5 for m in row]) for row in marg] if n else default_params()["marginal"]
    return params, history


# ---------------------------------------------------------------------------- goal recognition

Target = Tuple[str, Optional[Pos]]      # ("H", house) | ("U", our group) | ("M", own group) | ("F", None)


@dataclass
class GroupPrediction:
    """What one enemy group is expected to do next."""

    pos: Pos
    size: int
    targets: List[Tuple[Target, float]]          # most likely first
    step_probs: Dict[Pos, float]                 # next cell (including staying) -> probability

    def next_cell(self) -> Pos:
        """The most likely next cell."""
        return max(self.step_probs, key=lambda c: self.step_probs[c])


class GoalRecognizer:
    """Per enemy group, a belief over its target, updated from its observed steps."""

    def __init__(self, beta: float = 2.0, stay: float = 0.85, radius: int = 12):
        """beta = rationality of the opponent; stay = probability it keeps its target."""
        self.beta = beta
        self.stay = stay
        self.radius = radius
        self.beliefs: Dict[Pos, Dict[Target, float]] = {}

    def reset(self):
        """New game."""
        self.beliefs = {}

    def candidates(self, state: State, mover: int, pos: Pos, size: int) -> List[Target]:
        """Targets a group of `size` at `pos` could plausibly be heading for."""
        out: List[Target] = [("F", None)]
        for hp, h in state.humans.items():
            if h <= size and cheb(pos, hp) <= self.radius:
                out.append(("H", hp))
        for up in state.groups[1 - mover]:
            if cheb(pos, up) <= self.radius:
                out.append(("U", up))
        for mp in state.groups[mover]:
            if mp != pos and cheb(pos, mp) <= self.radius:
                out.append(("M", mp))
        return out

    @staticmethod
    def _dist(cell: Pos, target: Target, state: State, mover: int) -> float:
        kind, tp = target
        if kind == "F":                       # fleeing = getting far from our groups
            them = state.groups[1 - mover]
            return -min((cheb(cell, u) for u in them), default=0)
        # king-move distance, ties broken towards the straight line (Manhattan): with Chebyshev
        # alone, the diagonal and straight steps towards a target would be equally likely
        return cheb(cell, tp) + 0.2 * (abs(cell[0] - tp[0]) + abs(cell[1] - tp[1]))

    def step_distribution(self, state: State, mover: int, pos: Pos, target: Target) -> Dict[Pos, float]:
        """P(next cell | target): a softmax of beta x (distance reduction), over 8 moves + staying."""
        d0 = self._dist(pos, target, state, mover)
        options = [pos] + list(state.nbrs[pos])
        w = [math.exp(self.beta * (d0 - self._dist(c, target, state, mover))) for c in options]
        s = sum(w)
        return {c: x / s for c, x in zip(options, w)}

    def _prior(self, old: Optional[Dict[Target, float]], cands: List[Target]) -> Dict[Target, float]:
        """Sticky transition onto the current candidates (vanished targets are dropped)."""
        n = len(cands)
        if not old:
            return {t: 1.0 / n for t in cands}
        kept = {t: old.get(t, 0.0) for t in cands}
        s = sum(kept.values())
        if s <= 0:
            return {t: 1.0 / n for t in cands}
        return {t: self.stay * kept[t] / s + (1 - self.stay) / n for t in cands}

    def _rekey(self, old: Dict[Target, float], state: State, mover: int) -> Dict[Target, float]:
        """Moving targets (groups) are matched to the nearest current group of the same side."""
        out: Dict[Target, float] = {}
        for (kind, tp), p in old.items():
            if kind in ("U", "M") and tp is not None:
                pool = state.groups[1 - mover] if kind == "U" else state.groups[mover]
                if not pool:
                    continue
                tp = min(pool, key=lambda c: cheb(c, tp))
            key = (kind, tp)
            out[key] = out.get(key, 0.0) + p
        return out

    def update(self, mid: State, after: State, mover: int, flows) -> None:
        """Bayes update of every enemy group's target from its observed step (mid -> after)."""
        new: Dict[Pos, Dict[Target, float]] = {}
        weight: Dict[Pos, float] = {}
        by_src: Dict[Pos, List[Tuple[Pos, int]]] = {}
        for s, d, n in flows:
            by_src.setdefault(s, []).append((d, n))
        for pos, size in mid.groups[mover].items():
            old = self._rekey(self.beliefs.get(pos, {}), mid, mover)
            cands = self.candidates(mid, mover, pos, size)
            prior = self._prior(old, cands)
            moves = by_src.get(pos, [])
            stayed = size - sum(n for _, n in moves)
            parts = moves + ([(pos, stayed)] if stayed > 0 else [])
            main = max(parts, key=lambda x: x[1])[0] if parts else pos
            post = {t: prior[t] * self.step_distribution(mid, mover, pos, t).get(main, 1e-9) for t in cands}
            s = sum(post.values()) or 1.0
            post = {t: v / s for t, v in post.items()}
            for d, n in parts:                       # children (split parts) inherit the posterior
                acc = new.setdefault(d, {})
                for t, v in post.items():
                    acc[t] = acc.get(t, 0.0) + n * v
                weight[d] = weight.get(d, 0.0) + n
        self.beliefs = {d: {t: v / weight[d] for t, v in acc.items()} for d, acc in new.items()
                        if d in after.groups[mover]}

    def predict(self, state: State, mover: int) -> Dict[Pos, GroupPrediction]:
        """Next-step prediction for every current enemy group."""
        out: Dict[Pos, GroupPrediction] = {}
        for pos, size in state.groups[mover].items():
            cands = self.candidates(state, mover, pos, size)
            belief = self._prior(self._rekey(self.beliefs.get(pos, {}), state, mover), cands)
            steps: Dict[Pos, float] = {}
            for t, p in belief.items():
                for c, q in self.step_distribution(state, mover, pos, t).items():
                    steps[c] = steps.get(c, 0.0) + p * q
            ranked = sorted(belief.items(), key=lambda kv: -kv[1])
            out[pos] = GroupPrediction(pos, size, ranked, steps)
        return out


# ---------------------------------------------------------------------------- policy HMM

EXPERTS = ("GREEDY", "PLANNER", "GOAL", "AWAY")
StepDists = Dict[Pos, Dict[Pos, float]]          # enemy group cell -> {next cell: probability}


def _point(state: State, pos: Pos, cell: Pos, eps: float) -> Dict[Pos, float]:
    """(1 - eps) on `cell`, eps spread over every option (8 neighbours + staying)."""
    options = [pos] + list(state.nbrs[pos])
    d = {c: eps / len(options) for c in options}
    d[cell] = d.get(cell, 0.0) + (1 - eps)
    return d


def greedy_steps(state: State, mover: int) -> Dict[Pos, Pos]:
    """Each group walks to the nearest house it can convert, else to the nearest enemy group."""
    out = {}
    for pos, size in state.groups[mover].items():
        houses = [hp for hp, h in state.humans.items() if h <= size]
        targets = houses or list(state.groups[1 - mover])
        if not targets:
            out[pos] = pos
            continue
        t = min(targets, key=lambda c: (cheb(pos, c), c))
        out[pos] = min([pos] + list(state.nbrs[pos]), key=lambda c: (cheb(c, t), c))
    return out


def away_steps(state: State, mover: int) -> Dict[Pos, Pos]:
    """Each group steps to the neighbour farthest from the other side's groups."""
    them = state.groups[1 - mover]
    out = {}
    for pos in state.groups[mover]:
        out[pos] = max([pos] + list(state.nbrs[pos]),
                       key=lambda c: (min((cheb(c, u) for u in them), default=0), c))
    return out


def plan_steps(moves, groups: Dict[Pos, int]) -> Dict[Pos, Pos]:
    """Main destination of every group under a move list (staying if it did not move)."""
    sent: Dict[Pos, List[Tuple[Pos, int]]] = {}
    for x1, y1, n, x2, y2 in moves:
        sent.setdefault((x1, y1), []).append(((x2, y2), n))
    out = {}
    for pos, size in groups.items():
        parts = list(sent.get(pos, []))
        stayed = size - sum(n for _, n in parts)
        if stayed > 0:
            parts.append((pos, stayed))
        out[pos] = max(parts, key=lambda x: x[1])[0] if parts else pos
    return out


def planner_steps(state: State, mover: int) -> Dict[Pos, Pos]:
    """Steps of the top plan our own planner would play for `mover` (a model of a smart bot)."""
    from .planner import generate_plans  # local import: planner imports nothing from here
    plans = generate_plans(state, mover)
    return plan_steps(plans[0].moves, state.groups[mover]) if plans else {}


class PolicyHMM:
    """
    Which policy is the opponent following? Hidden state = one of EXPERTS; emission = how likely
    that expert makes the opponent's observed steps. Filtering = online expert selection that can
    switch (sticky transitions); prediction = the belief-weighted mixture of the experts.
    """

    def __init__(self, goals: GoalRecognizer, stay: float = 0.95, eps: float = 0.15):
        """Uses `goals` as the GOAL expert; eps = noise every expert allows for."""
        self.goals = goals
        self.stay = stay
        self.eps = eps
        self.reset()

    def reset(self):
        """New game: no preference between experts."""
        self.belief = [1.0 / len(EXPERTS)] * len(EXPERTS)
        self.hits = 0.0
        self.seen = 0.0

    def expert_dists(self, state: State, mover: int) -> List[StepDists]:
        """For each expert, its next-step distribution for every group of `mover` in `state`."""
        groups = state.groups[mover]
        g = greedy_steps(state, mover)
        p = planner_steps(state, mover)
        a = away_steps(state, mover)
        goal = self.goals.predict(state, mover)
        out: List[StepDists] = [{}, {}, {}, {}]
        for pos in groups:
            out[0][pos] = _point(state, pos, g.get(pos, pos), self.eps)
            out[1][pos] = _point(state, pos, p.get(pos, pos), self.eps)
            gd = goal[pos].step_probs
            out[2][pos] = {c: (1 - self.eps) * gd.get(c, 0.0) + self.eps / (1 + len(state.nbrs[pos]))
                           for c in [pos] + list(state.nbrs[pos])}
            out[3][pos] = _point(state, pos, a.get(pos, pos), self.eps)
        return out

    def mixture(self, dists: List[StepDists], belief: Optional[List[float]] = None) -> StepDists:
        """Belief-weighted prediction for every group."""
        b = belief or self.belief
        mix: StepDists = {}
        for e, de in enumerate(dists):
            for pos, d in de.items():
                acc = mix.setdefault(pos, {})
                for c, q in d.items():
                    acc[c] = acc.get(c, 0.0) + b[e] * q
        return mix

    def update(self, dists: List[StepDists], actual: Dict[Pos, Pos]) -> None:
        """Forward step: dists computed on the board before the opponent's turn, actual = its steps."""
        n = len(EXPERTS)
        prior = [self.stay * self.belief[i] + (1 - self.stay) / n for i in range(n)]
        mix = self.mixture(dists, prior)
        for pos, cell in actual.items():                 # running accuracy of our predictions
            if pos in mix:
                self.seen += 1
                self.hits += max(mix[pos], key=lambda c: mix[pos][c]) == cell
        like = []
        for e in range(n):
            ll = 0.0
            for pos, cell in actual.items():
                if pos in dists[e]:
                    ll += math.log(max(dists[e][pos].get(cell, 0.0), 1e-6))
            like.append(ll)
        top = max(like)
        self.belief = _normalize([prior[e] * math.exp(like[e] - top) for e in range(n)])

    @property
    def accuracy(self) -> float:
        """Share of enemy group steps our mixture predicted (top-1) so far this game."""
        return self.hits / self.seen if self.seen else 0.0

    @property
    def trust(self) -> float:
        """0 .. 0.8: how much the search should rely on the predicted moves (from the accuracy)."""
        if self.seen < 6:
            return 0.0
        # measured (chapter 11): steering the search by predictions helps against predictable bots
        # but hurts against strong ones (~48% accuracy), so the model only steers above 55%
        return 0.8 * max(0.0, min(1.0, (self.accuracy - 0.55) / 0.35))


# ---------------------------------------------------------------------------- facade

@dataclass
class Predictions:
    """Everything the planner / search / evaluation need to know about the opponent."""

    modes: Dict[str, float]                       # style belief
    trust: float                                  # 0 = ignore the model .. 0.8
    features: List[List[float]]                   # predicted distribution of each turn feature
    groups: Dict[Pos, GroupPrediction] = field(default_factory=dict)

    @property
    def p_gamble(self) -> float:
        """Probability that the opponent's next attack (if any) is a coin flip or long shot."""
        att = self.features[1]
        attacks = att[1] + att[2] + att[3]
        return (att[2] + att[3]) / attacks if attacks > 0 else 0.0


class OpponentModel:
    """
    Observe the opponent every turn and predict its next move:
      style HMM  (who: gambler? hunter? ...)            -> p_gamble, adaptive settings
      policy HMM (which expert policy it follows)       -> probability of each candidate reply
      goal recognizer (where each group is heading)     -> the GOAL expert, predicted targets
    """

    def __init__(self, params: Optional[dict] = None):
        """Style HMM (trained parameters if available), goal recognizer, policy HMM, move tracker."""
        self.style = StyleHMM(params)
        self.goals = GoalRecognizer()
        self.policy = PolicyHMM(self.goals, stay=0.9)
        self.tracker = OpponentTracker()
        self.history: List[TurnObservation] = []

    def reset(self):
        """New game."""
        self.style.reset()
        self.goals.reset()
        self.policy.reset()
        self.tracker.reset()
        self.history = []

    def observe(self, state: State) -> Optional[TurnObservation]:
        """Call at the start of our turn: learn from the opponent's last move."""
        obs = self.tracker.observe(state)
        if obs is None:
            return None
        mid = self.tracker.last_mid or state
        opp = 1 - self.tracker.side
        dists = self.policy.expert_dists(mid, opp)          # predictions made BEFORE seeing the move
        moves = [(s[0], s[1], n, d[0], d[1]) for s, d, n in obs.flows]
        self.policy.update(dists, plan_steps(moves, mid.groups[opp]))
        self.style.update(obs.vector(), phase_of(mid))
        self.goals.update(mid, state, opp, obs.flows)
        self.history.append(obs)
        return obs

    def note_our_move(self, state: State, side: int, moves) -> None:
        """Call after choosing our moves."""
        self.tracker.note_our_move(state, side, moves)

    @property
    def trust(self) -> float:
        """How much the search should follow the predictions (policy HMM accuracy this game)."""
        return self.policy.trust

    @property
    def p_gamble(self) -> float:
        """Probability that an attack by this opponent is a coin flip or a long shot (style HMM)."""
        att = self.style.predict_features(0)[1]
        attacks = att[1] + att[2] + att[3]
        return (att[2] + att[3]) / attacks if attacks > 0 else 0.0

    @property
    def p_longshot(self) -> float:
        """Probability that an attack by this opponent is a long shot (P < 0.5)."""
        att = self.style.predict_features(0)[1]
        attacks = att[1] + att[2] + att[3]
        return att[3] / attacks if attacks > 0 else 0.0

    def tendencies(self, state: State) -> Dict[str, float]:
        """Measured tendencies for adaptive settings: aggression, split rate, long-shot rate."""
        f = self.style.predict_features(phase_of(state))
        return {"aggression": f[2][0], "split": f[0][1], "longshot": self.p_longshot,
                "turns": float(self.style.turns)}

    def score_plans(self, state: State, opp: int, plans) -> List[float]:
        """
        Model probability (up to a constant) of each candidate opponent plan in `state`: the
        geometric mean over its groups of the policy-HMM mixture probability of each group's step.
        The PLANNER expert is the highest-prior plan of `plans` (free: they are our planner's).
        """
        groups = state.groups[opp]
        if not plans or not groups:
            return [1.0] * len(plans)
        eps = self.policy.eps
        g = greedy_steps(state, opp)
        a = away_steps(state, opp)
        top = plan_steps(max(plans, key=lambda p: p.prior).moves, groups)
        goal = self.goals.predict(state, opp)
        b = self.policy.belief
        mix: StepDists = {}
        for pos in groups:
            options = [pos] + list(state.nbrs[pos])
            u = eps / len(options)
            gd = goal[pos].step_probs
            d = {}
            for c in options:
                d[c] = (b[0] * ((1 - eps) * (c == g.get(pos)) + u) + b[1] * ((1 - eps) * (c == top.get(pos)) + u)
                        + b[2] * ((1 - eps) * gd.get(c, 0.0) + u) + b[3] * ((1 - eps) * (c == a.get(pos)) + u))
            mix[pos] = d
        out = []
        for p in plans:
            steps = plan_steps(p.moves, groups)
            ll = sum(math.log(max(mix[pos].get(c, 1e-6), 1e-6)) for pos, c in steps.items())
            out.append(math.exp(ll / len(steps)) if steps else 1e-6)
        return out

    def predictions(self, state: State, side: int) -> Predictions:
        """Predictions for the opponent's next turn in `state` (we are `side`)."""
        ph = phase_of(state)
        return Predictions(self.style.mode_probs(), self.trust, self.style.predict_features(ph),
                           self.goals.predict(state, 1 - side))
