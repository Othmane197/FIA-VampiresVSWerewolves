"""
Observing the opponent: what did it just do?

The server never tells us the opponent's moves; we only see the board after them. But enemy
creatures only move during their own turn (on ours they can only die), so comparing
    mid   = the board right after OUR move (before theirs)
    after = the board now
tells us everything (reconstruct_flows). Each opponent turn is then summarised by four discrete
features (features_from_flows), the observations of the opponent HMM (opponent_model.py):

    split      0 no | 1 yes          (one cell sent creatures to 2+ cells, or part moved, part stayed)
    attack     0 none | 1 sure kill | 2 coin flip (P >= 0.5) | 3 long shot (P < 0.5)
    heading    0 toward our groups | 1 toward a house it can convert | 2 away from us
               3 toward its own groups (merge) | 4 idle          (vote weighted by creature count)
    converted  0 no | 1 yes          (it converted a house this turn)

The same feature function scores hypothetical moves (plan_features), so the HMM's predictions
can be compared with the opponent plans generated inside the search.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .rules import Move, Pos, cheb, win_probability
from .state import State

ATTACK_NONE, ATTACK_SURE, ATTACK_COIN, ATTACK_LONG = 0, 1, 2, 3
HEAD_US, HEAD_HOUSE, HEAD_AWAY, HEAD_MERGE, HEAD_IDLE = 0, 1, 2, 3, 4
FEATURES: Tuple[Tuple[str, int], ...] = (("split", 2), ("attack", 4), ("heading", 5), ("converted", 2))
INF = 10 ** 6

Flow = Tuple[Pos, Pos, int]            # (source cell, destination cell, creatures)


@dataclass
class TurnObservation:
    """One opponent turn as the HMM sees it (see module docstring), plus the flows behind it."""

    split: int
    attack: int
    heading: int
    converted: int
    flows: Tuple[Flow, ...] = ()

    def vector(self) -> Tuple[int, int, int, int]:
        """The four feature values, in FEATURES order."""
        return (self.split, self.attack, self.heading, self.converted)


def _nearest(p: Pos, cells) -> int:
    """Distance from p to the closest of `cells` (INF if there is none)."""
    best = INF
    for c in cells:
        d = cheb(p, c)
        best = min(best, d)
    return best


def features_from_flows(mid: State, mover: int, flows: Sequence[Flow]) -> TurnObservation:
    """Classify a turn of `mover`, given the board before it (`mid`) and its creature flows."""
    mine = mid.groups[mover]
    them = mid.groups[1 - mover]
    humans = mid.humans
    dests: Dict[Pos, set] = {}
    moved: Dict[Pos, int] = {}
    arrivals: Dict[Pos, int] = {}
    for s, d, n in flows:
        dests.setdefault(s, set()).add(d)
        moved[s] = moved.get(s, 0) + n
        arrivals[d] = arrivals.get(d, 0) + n
    split = int(any(len(ds) > 1 or mine.get(s, 0) > moved[s] for s, ds in dests.items()))

    attack = ATTACK_NONE
    converted = 0
    for d, a in arrivals.items():
        if them.get(d):
            p = win_probability(a, them[d], False)
            cls = ATTACK_SURE if p >= 1.0 else (ATTACK_COIN if p >= 0.5 else ATTACK_LONG)
            attack = max(attack, cls)
        elif humans.get(d) and a >= humans[d]:
            converted = 1

    votes = [0.0] * 5
    for s, d, n in flows:
        if them.get(d):
            votes[HEAD_US] += n
            continue
        if humans.get(d):
            votes[HEAD_HOUSE] += n
            continue
        size = mine.get(s, n)
        houses = [hp for hp, h in humans.items() if h <= size]
        friends = [c for c in mine if c != s]
        du0, du1 = _nearest(s, them), _nearest(d, them)
        dh0, dh1 = _nearest(s, houses), _nearest(d, houses)
        dm0, dm1 = _nearest(s, friends), _nearest(d, friends)
        to_us, to_house, to_merge = du0 - du1, dh0 - dh1, dm0 - dm1
        if to_house > 0 and to_house >= to_us:
            votes[HEAD_HOUSE] += n
        elif to_us > 0:
            votes[HEAD_US] += n
        elif to_merge > 0:
            votes[HEAD_MERGE] += n
        elif du1 > du0:
            votes[HEAD_AWAY] += n
        else:
            votes[HEAD_IDLE] += n
    heading = HEAD_IDLE if not flows else max(range(5), key=lambda i: votes[i])
    return TurnObservation(split, attack, heading, converted, tuple(flows))


def plan_features(state: State, mover: int, moves: Sequence[Move]) -> TurnObservation:
    """Features of a HYPOTHETICAL turn (used to score opponent plans with the HMM's prediction)."""
    flows = [((m[0], m[1]), (m[3], m[4]), m[2]) for m in moves]
    return features_from_flows(state, mover, flows)


def reconstruct_flows(mid: State, after: State, mover: int) -> List[Flow]:
    """
    Rebuild the creature flows of `mover`'s turn from the boards before (`mid`) and after it.
    Rule 5 helps: a cell that received creatures was not a source. Demands are served in order
    of certainty (plain moves and sure results first, random battles last), each from adjacent
    sources, the most constrained destination first.
    """
    e0, e1 = mid.groups[mover], after.groups[mover]
    o0, o1 = mid.groups[1 - mover], after.groups[1 - mover]
    h0, h1 = mid.humans, after.humans
    supply = {s: e0[s] - e1.get(s, 0) for s in e0 if e1.get(s, 0) < e0[s]}
    if not supply:
        return []
    exact: Dict[Pos, int] = {}       # destinations whose arrivals are known exactly
    lower: Dict[Pos, int] = {}       # random battles they won: at least the survivors arrived
    unknown: List[Pos] = []          # random battles they lost: some arrived, all died
    for d, n in e1.items():
        gain = n - e0.get(d, 0)
        if gain <= 0 or d in supply:
            continue
        if h0.get(d):
            h = h0[d]
            if n - h >= h:
                exact[d] = n - h                       # sure conversion: arrivals + humans
            else:
                lower[d] = n
        elif o0.get(d):
            if n >= 1.5 * o0[d]:
                exact[d] = n                           # sure kill: no losses
            else:
                lower[d] = n
        else:
            exact[d] = gain                            # plain move or merge
    for d, n in o0.items():
        if d not in e1 and o1.get(d, 0) < n:
            unknown.append(d)                          # attacked us and lost
    for d, n in h0.items():
        if d not in e1 and h1.get(d, 0) < n:
            unknown.append(d)                          # attacked humans and lost

    left = dict(supply)
    flows: Dict[Tuple[Pos, Pos], int] = {}

    def serve(d: Pos, need: int) -> int:
        # best fit first: a source that covers the need alone (and is not much bigger) avoids
        # inventing a split that never happened (crossing assignments)
        srcs = sorted((s for s in left if left[s] > 0 and cheb(s, d) == 1),
                      key=lambda s: (left[s] < need, abs(left[s] - need),
                                     sum(1 for x in exact if cheb(s, x) == 1)))
        got = 0
        for s in srcs:
            if got >= need:
                break
            take = min(left[s], need - got)
            left[s] -= take
            flows[(s, d)] = flows.get((s, d), 0) + take
            got += take
        return got

    def n_sources(d: Pos) -> int:
        return sum(1 for s in left if left[s] > 0 and cheb(s, d) == 1)

    # pre-pass: exact one-to-one matches (source supply == destination demand), most constrained first
    changed = True
    while changed:
        changed = False
        for d in sorted(exact, key=n_sources):
            if exact[d] <= 0:
                continue
            fits = [s for s in left if left[s] == exact[d] and cheb(s, d) == 1]
            if len(fits) == 1 or (fits and n_sources(d) == 1):
                s = fits[0]
                flows[(s, d)] = flows.get((s, d), 0) + left[s]
                exact[d] = 0
                left[s] = 0
                changed = True
    for d in sorted(exact, key=n_sources):
        if exact[d] > 0:
            serve(d, exact[d])
    for d in sorted(lower, key=n_sources):
        serve(d, lower[d])
    # whatever is left went into battles they lost, or was a random win with casualties
    sinks = unknown + list(lower)
    for s in list(left):
        while left[s] > 0:
            adj = [d for d in sinks if cheb(s, d) == 1]
            if not adj:
                break
            share = max(1, left[s] // len(adj))
            for d in adj:
                take = min(share, left[s])
                if take <= 0:
                    break
                left[s] -= take
                flows[(s, d)] = flows.get((s, d), 0) + take
    return [(s, d, n) for (s, d), n in flows.items() if n > 0]


class OpponentTracker:
    """Remembers the board at our last decision and our moves, to observe the opponent's reply."""

    def __init__(self):
        """Empty tracker (nothing observed yet)."""
        self.reset()

    def reset(self):
        """Forget everything (new game)."""
        self.prev: Optional[State] = None
        self.prev_moves: List[Move] = []
        self.side = 0
        self.last: Optional[TurnObservation] = None
        self.last_mid: Optional[State] = None

    def note_our_move(self, state: State, side: int, moves: Sequence[Move]):
        """Call right after choosing our moves for `state`."""
        self.prev = state.copy()
        self.prev_moves = list(moves)
        self.side = side

    def observe(self, state: State) -> Optional[TurnObservation]:
        """The opponent's last turn, reconstructed from our previous decision and this board."""
        if self.prev is None:
            return None
        mid = self.prev.apply(self.side, self.prev_moves, mode="mean") if self.prev_moves else self.prev
        flows = reconstruct_flows(mid, state, 1 - self.side)
        self.last_mid = mid
        self.last = features_from_flows(mid, 1 - self.side, flows)
        return self.last
