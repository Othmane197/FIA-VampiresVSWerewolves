"""
Heuristic evaluation of a position for the Splitter, as a win probability in [0, 1].

    evaluate(state, side, to_move) = P(side wins)

1. TACTICS: the player to move can immediately kill groups it beats 1.5x and convert adjacent
   houses it is big enough for; we apply those certain gains first (resolve_immediate).
2. RACE PROJECTION (project_race): every group is a "runner" with a clock. Repeatedly the
   earliest (runner, house) pair with runner >= house is resolved: the runner walks there and
   grows. Many runners collect houses in parallel, so this naturally rewards safe splitting,
   and it understands snowballing (a group that converts can then take bigger houses).
   Gains are discounted with distance and cut at the end of the game (clock-aware).
3. VULNERABILITY: groups that an enemy can attack with good odds soon lose their expected
   value (exposure). This is what punishes splits that are too thin.
4. The projected material difference is squashed into [0, 1]; a 1.5x domination is a big
   bonus (the dominant side can hunt the other down without dice).
"""
import math
from typing import Dict, List, Optional, Tuple

from .rules import Pos, cheb, win_probability
from .state import State

DISCOUNT = 0.93


def resolve_immediate(state: State, to_move: int) -> Tuple[Dict[Pos, int], Dict[Pos, int], Dict[Pos, int]]:
    """Groups after the player to move takes its certain gains (kills >= 1.5x, conversions)."""
    movers = dict(state.groups[to_move])
    victims = dict(state.groups[1 - to_move])
    humans = dict(state.humans)
    for pos, cnt in sorted(movers.items(), key=lambda g: -g[1]):
        best, best_gain, kind = None, 0, None
        for vp, v in victims.items():
            if cheb(pos, vp) == 1 and cnt >= 1.5 * v and v > best_gain:
                best, best_gain, kind = vp, v, "kill"
        for hp, h in humans.items():
            if cheb(pos, hp) == 1 and cnt >= h > best_gain:
                best, best_gain, kind = hp, h, "house"
        if best is None:
            continue
        if kind == "kill":
            del victims[best]
            movers[pos] = cnt            # position change does not matter for the projection
        else:
            del humans[best]
            movers[pos] = cnt + best_gain
    return movers, victims, humans


def project_race(ours: Dict[Pos, int], theirs: Dict[Pos, int], humans: Dict[Pos, int],
                 our_head_start: float, horizon: float) -> Tuple[float, float]:
    """
    Projected sizes after both sides collect the houses they reach first (see module doc).
    MERGE-AWARE: a house too big for every single runner of a side can be taken by two runners
    of that side that meet first (meeting takes half their distance) - this is what tells the
    search that a split army must regroup before a big prize.
    """
    runners: List[list] = [[p, c, our_head_start, 0] for p, c in ours.items()]
    runners += [[p, c, 0.5 - our_head_start, 1] for p, c in theirs.items()]
    proj = [float(sum(ours.values())), float(sum(theirs.values()))]
    houses = dict(humans)
    while houses and runners:
        best = None
        for r in runners:
            rp, rc, rt = r[0], r[1], r[2]
            for hp, h in houses.items():
                if rc >= h:
                    t = rt + cheb(rp, hp)
                    if best is None or t < best[0]:
                        f = _contest(runners, r, hp, rc + h, t)
                        if f > 0.0:
                            best = (t, r, hp, None, f)
        # merges: two runners of one side join (at the bigger one) for a house neither takes alone
        n = len(runners)
        for i in range(n):
            r1 = runners[i]
            for j in range(i + 1, n):
                r2 = runners[j]
                if r1[3] != r2[3]:
                    continue
                c = r1[1] + r2[1]
                big, small = (r1, r2) if r1[1] >= r2[1] else (r2, r1)
                meet = max(r1[2], r2[2]) + (cheb(r1[0], r2[0]) + 1) // 2
                for hp, h in houses.items():
                    if r1[1] < h and r2[1] < h <= c:
                        t = meet + cheb(big[0], hp)
                        if best is None or t < best[0]:
                            f = _contest(runners, big, hp, c + h, t)
                            if f > 0.0:
                                best = (t, big, hp, small, f)
        if best is None or best[0] > horizon:
            break
        t, r, hp, absorbed, f = best
        if absorbed is not None:
            r[1] += absorbed[1]
            runners.remove(absorbed)
        gain = houses.pop(hp)
        r[0], r[1], r[2] = hp, r[1] + gain, t
        proj[r[3]] += f * gain * DISCOUNT ** t
    return proj[0], proj[1]


def _contest(runners, r, hp, size_after, t) -> float:
    """
    Is the capture of house hp by runner r (ending with size_after at time t) safe?
    1.0 = safe; 0.5 = an enemy runner can strike right after with >= 50% odds; 0.0 = an enemy
    runner can sure-kill it right after (then the capture is not counted at all). Lesson from
    lost games: racing a small group into the enemy's zone only feeds the enemy.
    """
    f = 1.0
    for o in runners:
        if o[3] == r[3]:
            continue
        if o[2] + cheb(o[0], hp) <= t + 1:
            if o[1] >= 1.5 * size_after:
                return 0.0
            if o[1] >= size_after:
                f = 0.5
    return f


def exposure(groups: Dict[Pos, int], enemies: Dict[Pos, int], enemy_moves_next: bool) -> float:
    """
    Expected creatures lost because enemies can attack these groups soon.
    Lesson from real losses: when two groups are adjacent, the side to move strikes first, and
    striking at only 30-45% is RATIONAL when the alternative is being struck at 55-70% next
    turn. So an adjacent enemy that moves next is a threat as soon as its odds reach ~0.3.
    """
    lost = 0.0
    for pos, cnt in groups.items():
        worst = 0.0
        for ep, e in enemies.items():
            d = cheb(ep, pos)
            if d > 2:
                continue
            p = win_probability(e, cnt, False)
            sure = e >= 1.5 * cnt
            if d == 1:
                if enemy_moves_next:
                    risk = p * cnt if p >= 0.3 else 0.0
                else:                      # we move first: we can flee or strike, unless cornered
                    risk = 0.25 * cnt if sure else 0.0
            else:                          # d == 2: they can only come adjacent (or we can)
                risk = (0.12 if enemy_moves_next else 0.05) * cnt if sure else 0.0
            worst = max(worst, risk)
        lost += worst
    return lost


def evaluate(state: State, side: int, to_move: int, remaining_plies: Optional[float] = None) -> float:
    """P(side wins) estimate in [0, 1]."""
    ours_now = state.groups[side]
    theirs_now = state.groups[1 - side]
    if not ours_now:
        return 0.0 if theirs_now else 0.5
    if not theirs_now:
        return 1.0
    if remaining_plies is None:
        remaining_plies = state.max_ply - state.ply
    if remaining_plies <= 0:
        a, b = sum(ours_now.values()), sum(theirs_now.values())
        return 1.0 if a > b else (0.0 if a < b else 0.5)

    movers, victims, humans = resolve_immediate(state, to_move)
    if to_move == side:
        ours, theirs = movers, victims
    else:
        ours, theirs = victims, movers
    if not ours:
        return 0.02
    if not theirs:
        return 0.98

    horizon = remaining_plies / 2.0
    # resolve_immediate used up to_move's turn, so the OTHER side moves next (no head start for it)
    head = 0.0 if to_move != side else 0.5
    a, b = project_race(ours, theirs, humans, head, horizon)
    # the side that just took its immediate gains is the one NOT to move next
    enemy_next = (to_move == side)
    a -= exposure(ours, theirs, enemy_next)
    b -= exposure(theirs, ours, not enemy_next)
    a = max(a, 0.1)
    b = max(b, 0.1)

    x = (a - b) / (a + b)                      # in (-1, 1)
    # the closer to the end, the more a lead is a win (a safe lead late in the game cannot be
    # erased without a gamble): steepness grows from 6 to 20
    progress = 1.0 - min(1.0, remaining_plies / max(1, state.max_ply))
    k = 6.0 + 14.0 * progress
    score = 1.0 / (1.0 + math.exp(-k * x))
    if a >= 1.5 * b:
        score = 0.5 * score + 0.5
    elif b >= 1.5 * a:
        score = 0.5 * score
    return score


def material_balance(state: State, side: int) -> float:
    """Quick (our total - their total) / everything, used to decide whether we are behind."""
    a = state.total(side)
    b = state.total(1 - side)
    return (a - b) / max(1, a + b)
