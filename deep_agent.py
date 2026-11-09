"""
deep_agent.py  (our own file; it does not modify any shared repo file)

DeepAgent = iterative-deepening ALPHA-BETA (negamax form) with a transposition table,
a narrow goal-directed turn generator (controlled splitting), chance nodes only for the
rare random battles, and a risk-aware evaluation. It replaces the fixed-depth-2
expectiminimax of search_agent.py; everything else (server_rules.py gate, SafeAgent,
self-play harness, benchmark) is reused unchanged.

Course concepts used (Chapter 2): minimax / negamax, alpha-beta pruning, move ordering,
iterative deepening under a time limit, transposition table, expectiminimax CHANCE nodes.
Our own design: the turn generator, the evaluation terms, the risk-aware squashing,
Star1-style pruning inside chance nodes, game-clock-aware time budget.

------------------------------------------------------------------------------------------
1. STATE  (fast, immutable, hashable)
   S = (groups[0], groups[1], humans, ply)
     groups[0] = vampires, groups[1] = werewolves, each a sorted tuple of ((x, y), count)
     humans    = sorted tuple of ((x, y), count)
     ply       = number of plies already played (the game ends after MAX_PLY = 200
MAX_COUNT = 255                 # the protocol sends counts as ONE byte: a move of 256+ is illegal (forfeit))
   Being a tuple, S can be a dictionary key directly (transposition table) and copying is free.
   `side` is 0 (vampires) or 1 (werewolves).

2. TRANSITION  apply_turn(S, side, turn) -> [(probability, S'), ...]
   Exactly the official server's rules (see server_rules.py): creatures leave their sources,
   arrivals on the same cell are pooled, then each target is resolved. Certain results give ONE
   child. A random battle gives TWO children (win / lose) holding the rounded expected survivors,
   so the node becomes a CHANCE node (expectiminimax).

3. TURN GENERATOR  gen_turns(...)
   All legal turns are astronomically many, so per group we propose a few GOAL-DIRECTED options
   (one step toward a convertible human group, toward a killable enemy, away from a threat,
   toward a friendly group to merge, a split that sends exactly enough creatures to a human group
   and the rest elsewhere, an adjacent gamble only when allowed, or stay). Joint turns are built
   best-first from the per-group options and filtered by Rule 5. The list is short (branching
   factor ~ 5-20) and ordered best-first, which is what alpha-beta needs to prune.

4. EVALUATION  evaluate(S, side)  in [-1, 1] (terminal positions are +-WIN, |WIN| > 1)
   raw = material lead + w_h * human race (discounted by distance) + kill threats
   value = tanh(raw / (squash * total creatures))
   The tanh makes the score behave like a winning chance: it is CONCAVE when we are ahead (a 50/50
   gamble lowers the average, so the search refuses it) and CONVEX when we are behind (a gamble can
   raise it). So "random battles only when losing" (professor's advice) is not a hard-coded rule:
   it falls out of the expected value.

5. SEARCH  iterative deepening: depth 1, 2, 3, ... until the time budget is used. Each iteration
   is a full alpha-beta search; the transposition table (kept between iterations and between turns)
   returns the best turn of the previous iteration first, which makes the next one prune more.
   If time runs out in the middle of an iteration, we keep the best turn of the last COMPLETED
   iteration (or a better root turn already fully searched in the aborted one).
------------------------------------------------------------------------------------------
"""
import gc
import heapq
import math
import time
from typing import Dict, List, Optional, Tuple

from game_state import GameState, Species

Pos = Tuple[int, int]
Move = Tuple[int, int, int, int, int]
Turn = Tuple[Move, ...]

MAX_PLY = 200
MAX_COUNT = 255                 # the protocol sends counts as ONE byte: a move of 256+ is illegal (forfeit)
WIN = 1.2                       # terminal score: just above the best non-terminal score (1 + confidence).
                                # (It was 2.0: then a 21% shot at an instant win, 0.21 x 2 = 0.42, looked
                                # better than a solid lead, and the bot threw a winning game on a gamble.)
INF = float("inf")


# ===================================================================== rules helpers

def cheb(a: Pos, b: Pos) -> int:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    if dx < 0:
        dx = -dx
    if dy < 0:
        dy = -dy
    return dx if dx > dy else dy


def win_probability(a: int, d: int, humans: bool) -> float:
    """Official server (Board.GetProba): P that `a` attackers beat `d` defenders."""
    if a == d:
        return 0.5
    if humans:
        if a >= d:
            return 1.0
    elif 2 * a >= 3 * d:
        return 1.0
    if a < d:
        return a / (2.0 * d)
    return a / d - 0.5                      # monsters, d < a < 1.5 d


def certain(a: int, d: int, humans: bool) -> bool:
    return a >= d if humans else 2 * a >= 3 * d


def _rnd(x: float) -> int:
    return int(x + 0.5)


class Geometry:
    """Neighbour lists for one grid size (computed once)."""

    def __init__(self, cols: int, rows: int):
        self.cols, self.rows = cols, rows
        self.nbr: Dict[Pos, Tuple[Pos, ...]] = {}
        for x in range(cols):
            for y in range(rows):
                self.nbr[(x, y)] = tuple((x + dx, y + dy)
                                         for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                                         if (dx or dy) and 0 <= x + dx < cols and 0 <= y + dy < rows)


# ===================================================================== transition

def apply_turn(S, side: int, turn: Turn, max_branch: int = 2):
    """[(prob, S')] after `side` plays `turn` (legal turn assumed). See module docstring."""
    mine = dict(S[side])
    theirs = dict(S[1 - side])
    hum = dict(S[2])
    arrive: Dict[Pos, int] = {}
    for x1, y1, n, x2, y2 in turn:
        src = (x1, y1)
        left = mine[src] - n
        if left:
            mine[src] = left
        else:
            del mine[src]
        dst = (x2, y2)
        arrive[dst] = arrive.get(dst, 0) + n

    gambles = []
    for dst, a in arrive.items():
        if dst in mine:                                  # a group that did not move: merge
            mine[dst] += a
        elif dst in theirs:
            e = theirs[dst]
            if 2 * a >= 3 * e:
                del theirs[dst]
                mine[dst] = a
            else:
                gambles.append((a + e, dst, a, e, False))
        elif dst in hum:
            h = hum[dst]
            if a >= h:
                del hum[dst]
                mine[dst] = a + h
            else:
                gambles.append((a + h, dst, a, h, True))
        else:
            mine[dst] = a

    if not gambles:
        return [(1.0, _freeze(mine, theirs, hum, side, S[3] + 1))]

    gambles.sort(reverse=True)                           # biggest stakes branch first
    branches = [(1.0, mine, theirs, hum)]
    for k, (_, dst, a, d, is_h) in enumerate(gambles):
        p = win_probability(a, d, is_h)
        win_left = _rnd(p * (a + d)) if is_h else _rnd(p * a)
        lose_left = _rnd((1.0 - p) * d)
        outcomes = [(p, True, win_left), (1.0 - p, False, lose_left)]
        if k >= max_branch:                              # too many gambles: keep the likelier one
            outcomes = [max(outcomes)]
            outcomes = [(1.0,) + outcomes[0][1:]]
        new = []
        for bp, bm, bt, bh in branches:
            for op, won, left in outcomes:
                m2, t2, h2 = dict(bm), dict(bt), dict(bh)
                if is_h:
                    h2.pop(dst, None)
                    if won:
                        if left:
                            m2[dst] = left
                    elif left:
                        h2[dst] = left
                else:
                    t2.pop(dst, None)
                    if won:
                        if left:
                            m2[dst] = left
                    elif left:
                        t2[dst] = left
                new.append((bp * op, m2, t2, h2))
        branches = new
    return [(bp, _freeze(bm, bt, bh, side, S[3] + 1)) for bp, bm, bt, bh in branches]


def _freeze(mine, theirs, hum, side, ply):
    m = tuple(sorted(mine.items()))
    t = tuple(sorted(theirs.items()))
    h = tuple(sorted(hum.items()))
    return (m, t, h, ply) if side == 0 else (t, m, h, ply)


# ===================================================================== parameters

class Params:
    """All tunable numbers in one place (defaults = the tuned configuration)."""

    def __init__(self, **kw):
        # evaluation
        self.gamma = 0.9            # discount per step of distance (a target 1 step closer is worth more)
        self.w_humans = 0.8         # weight of the (discounted) human race
        self.queue = 0.6            # a group's k-th nearest won human group is worth queue^k: one group
                                    # cannot be in several places, so parallel collectors are worth more
        self.w_kill_adj = 0.8       # side to move can kill an adjacent enemy group for sure
        self.w_threat_adj = 0.6     # an enemy group can kill one of ours next turn (we may still flee)
        self.w_hunt = 0.15          # killable enemy groups further away (they can run)
        self.w_exposure = 0.0       # an enemy group BIGGER than one of ours within 2 cells could attack it
                                    # in a random battle it is favoured to win (P > 0.5); penalty
                                    # w_exposure * (2P - 1) * size of our group (and the reverse for theirs)
        self.squash = 0.25          # tanh scale = squash * creatures + squash_h * humans left: soft while many
        self.squash_h = 0.5         # humans remain (a lead can still change), sharp when they are gone (a lead
                                    # then decides the game: the bigger side just avoids battles until ply 200)
        self.confidence = 0.1       # bonus for the ROOT player in every unfinished position: we expect
                                    # to outplay the opponent, so an even game is worth more than a coin flip
        # generator
        self.k_humans = 3           # human targets considered per group
        self.k_enemies = 2          # enemy targets considered per group
        self.max_groups = 6         # no split once a side has this many groups
        self.min_split = 2          # smallest detachment worth splitting off
        self.opts_per_group = 6     # options kept per group
        self.max_turns = 16         # joint turns per node
        self.root_turns = 30        # joint turns at the root
        self.gamble_floor = 0.25    # never consider a random battle with P below this
        # search
        self.time_budget = 1.5      # seconds per turn (hard limit of the server: 2 s)
        self.game_seconds = 300.0   # MaxGameDuration of the server config (5 min)
        self.max_depth = 40
        self.pvs = True             # principal variation search (zero-window tests after the first turn)
        self.tt_max = 1_500_000
        for k, v in kw.items():
            if not hasattr(self, k):
                raise TypeError(f"unknown parameter {k}")
            setattr(self, k, v)


# ===================================================================== evaluation

def evaluate(S, side: int, P: Params, root: int = -1) -> float:
    """Score of S for `side`, which is the side TO MOVE (negamax convention).
    `root` = the side we play for; it receives the `confidence` bonus (none if root == -1)."""
    mine, theirs, hum, ply = S[side], S[1 - side], S[2], S[3]
    m = 0
    for _, n in mine:
        m += n
    t = 0
    for _, n in theirs:
        t += n
    if t == 0 or m == 0 or ply >= MAX_PLY:
        return terminal_value(m, t, ply)

    g = P.gamma
    queue = P.queue
    race = 0.0
    # each human group is "won" by the side whose nearest strong-enough group arrives first (ties: the
    # side to move); the winning GROUP is remembered so that its targets can be queued (see Params.queue)
    my_q: Dict[Pos, List[Tuple[int, int]]] = {}
    th_q: Dict[Pos, List[Tuple[int, int]]] = {}
    for q, h in hum:
        dm, gm = 99, None
        for p, n in mine:
            if n >= h:
                d = cheb(p, q)
                if d < dm:
                    dm, gm = d, p
        dt, gt = 99, None
        for p, n in theirs:
            if n >= h:
                d = cheb(p, q)
                if d < dt:
                    dt, gt = d, p
        if gm is None and gt is None:
            continue
        if dm <= dt:                                     # ties: the side to move arrives first
            my_q.setdefault(gm, []).append((dm, h))
        else:
            th_q.setdefault(gt, []).append((dt, h))
    for sign, queues in ((1.0, my_q), (-1.0, th_q)):
        for targets in queues.values():
            if len(targets) > 1:
                targets.sort()
            f = 1.0
            for d, h in targets:
                race += sign * f * h * g ** (d - 1)
                f *= queue

    kill = 0.0
    for q, e in theirs:                                  # enemy groups we can wipe out
        best = 0.0
        for p, n in mine:
            if 2 * n >= 3 * e:
                d = cheb(p, q)
                v = P.w_kill_adj if d == 1 else P.w_hunt * g ** (d - 2)
                if v > best:
                    best = v
        kill += e * best
    for q, c in mine:                                    # our groups the enemy can wipe out
        worst = 0.0
        for p, n in theirs:
            if 2 * n >= 3 * c:
                d = cheb(p, q)
                v = P.w_threat_adj if d <= 2 else P.w_hunt * g ** (d - 3)
                if v > worst:
                    worst = v
        kill -= c * worst

    if P.w_exposure:
        expo = 0.0
        for q, c in mine:                                # our groups facing a bigger enemy group nearby
            worst = 0.0
            for p, n in theirs:
                if n > c and cheb(p, q) <= 2:
                    pr = win_probability(n, c, False)
                    if pr > worst:
                        worst = pr
            if worst > 0.5:
                expo -= (2 * worst - 1) * c
        for q, c in theirs:                              # and theirs facing ours
            worst = 0.0
            for p, n in mine:
                if n > c and cheb(p, q) <= 2:
                    pr = win_probability(n, c, False)
                    if pr > worst:
                        worst = pr
            if worst > 0.5:
                expo += (2 * worst - 1) * c
        kill += P.w_exposure * expo

    raw = (m - t) + P.w_humans * race + kill
    h_left = 0
    for _, h in hum:
        h_left += h
    value = math.tanh(raw / (P.squash * (m + t) + P.squash_h * h_left))
    if root >= 0:
        value += P.confidence if side == root else -P.confidence
    return value


def terminal_value(m: int, t: int, ply: int) -> float:
    """Exact score of a finished game: earlier wins and later losses are preferred."""
    if m > t:
        return WIN - ply * 1e-4
    if m < t:
        return -WIN + ply * 1e-4
    return 0.0


# ===================================================================== turn generator

def gen_turns(S, side: int, geo: Geometry, P: Params, limit: int) -> List[Turn]:
    """Short best-first list of legal turns for `side` (see module docstring, part 3)."""
    mine_t, theirs_t, hum_t = S[side], S[1 - side], S[2]
    if not mine_t:
        return []
    mine = dict(mine_t)
    theirs = dict(theirs_t)
    hum = dict(hum_t)
    nbr = geo.nbr
    g = P.gamma
    n_groups = len(mine_t)
    behind = sum(mine.values()) < sum(theirs.values())
    can_split = n_groups < P.max_groups

    def passable(n: Pos, amount: int, target: Pos) -> bool:
        """Entering n with `amount` creatures is not an unwanted random battle."""
        if n == target:
            return True
        if n in hum:
            return hum[n] <= amount
        if n in theirs:
            return 2 * amount >= 3 * theirs[n]
        return True

    adj_cache: Dict[Pos, Tuple[int, int]] = {}

    def adjacent_enemies(n: Pos) -> Tuple[int, int]:
        """(total, biggest) enemy creatures on the cells next to n (cached for this call)."""
        r = adj_cache.get(n)
        if r is None:
            tot = big = 0
            for k in nbr[n]:
                e = theirs.get(k)
                if e:
                    tot += e
                    if e > big:
                        big = e
            r = adj_cache[n] = (tot, big)
        return r

    def danger(n: Pos, amount: int) -> int:
        """Exposure of `amount` creatures standing on n to the enemy groups next to n:
        2 = they can wipe us out for sure (pooled), 1 = one of them could attack us in a random
        battle it is likely enough to win (P >= gamble_floor), 0 = safe."""
        tot, big = adjacent_enemies(n)
        if not tot:
            return 0
        if 2 * tot >= 3 * amount:
            return 2
        return 1 if win_probability(big, amount, False) >= P.gamble_floor else 0

    def steps(p: Pos, target: Pos, amount: int) -> List[Pos]:
        """Neighbours of p that bring `amount` creatures one step closer to target, best first:
        least exposed (see danger), then straightest, then through convertible humans."""
        d0 = cheb(p, target)
        ranked = []
        for n in nbr[p]:
            if cheb(n, target) != d0 - 1 or not passable(n, amount, target):
                continue
            ranked.append(((danger(n, amount) if n != target else 0,
                            abs(n[0] - target[0]) + abs(n[1] - target[1]),
                            0 if n in hum else 1, n), n))
        ranked.sort()
        return [n for _, n in ranked]

    def step(p: Pos, target: Pos, amount: int) -> Optional[Pos]:
        s = steps(p, target, amount)
        return s[0] if s else None

    per_group = []
    for p, c in mine_t:
        opts: Dict[Turn, float] = {}

        def add(moves, score):
            key = tuple(moves)
            if opts.get(key, -INF) < score:
                opts[key] = score

        # 1. human groups we can convert for sure, best value first
        conv = heapq.nlargest(P.k_humans, ((h * g ** (cheb(p, q) - 1), q, h) for q, h in hum_t if h <= c))
        for rank, (val, q, h) in enumerate(conv):
            alts = steps(p, q, c)
            if not alts:
                continue
            n = alts[0]
            add([(p[0], p[1], c, n[0], n[1])], (1000 + h) if n == q else val)
            if rank == 0 and len(alts) > 1 and n != q:     # an alternative path to the best target
                add([(p[0], p[1], c, alts[1][0], alts[1][1])], val * 0.95)
            # SPLIT: exactly h creatures to q, the rest to another convertible group
            rest = c - h
            if can_split and rest >= P.min_split and h >= P.min_split:
                n1 = step(p, q, h)
                if n1 is None:
                    continue
                for val2, q2, h2 in conv:
                    if q2 == q or h2 > rest:
                        continue
                    n2 = step(p, q2, rest)
                    if n2 is None or n2 == n1:
                        continue
                    bonus = 1000 if n1 == q else 0
                    add([(p[0], p[1], h, n1[0], n1[1]), (p[0], p[1], rest, n2[0], n2[1])],
                        bonus + val + val2 * 0.9)
                    break

        # 2. enemy groups: certain kills (alone or pooled with adjacent friends), hunting
        for q, e in sorted(theirs_t, key=lambda qe: cheb(p, qe[0]))[:P.k_enemies + 2]:
            d = cheb(p, q)
            if d == 1:
                pooled = sum(n for k, n in mine_t if cheb(k, q) == 1)
                if 2 * c >= 3 * e:
                    add([(p[0], p[1], c, q[0], q[1])], 2000 + e)
                elif 2 * pooled >= 3 * e:
                    add([(p[0], p[1], c, q[0], q[1])], 1500 + e)
            elif 2 * c >= 3 * e:
                n = step(p, q, c)
                if n is not None:
                    add([(p[0], p[1], c, n[0], n[1])], 3 * e * g ** (d - 1))

        # 3. flee from enemy groups that can kill us (or win a gamble against us) soon
        threats = [(q, e) for q, e in theirs_t if cheb(p, q) <= 2 and (2 * e >= 3 * c or e > c)]
        if threats:
            best, best_key = None, None
            for n in nbr[p]:
                if not passable(n, c, n) or (n in hum and hum[n] > c) or n in theirs:
                    continue
                key = (min(cheb(n, q) for q, _ in threats), -danger(n, c),
                       max((h * g ** cheb(n, q) for q, h in hum_t if h <= c), default=0.0))
                if best_key is None or key > best_key:
                    best, best_key = n, key
            if best is not None:
                add([(p[0], p[1], c, best[0], best[1])], 800)

        # 4. merge with the nearest friendly group (needed to reach 1.5x thresholds)
        if n_groups > 1:
            f = min((k for k, _ in mine_t if k != p), key=lambda k: (cheb(p, k), k))
            n = step(p, f, c)
            if n is not None:
                add([(p[0], p[1], c, n[0], n[1])], 5 if conv else 50)

        # 5. adjacent random battles with P >= gamble_floor, for BOTH players: our own are then judged
        #    by the evaluation (refused unless we are behind), and the opponent's must be anticipated
        #    because other bots do take long shots against us
        for n in nbr[p]:
            if n in hum and hum[n] > c:
                if win_probability(c, hum[n], True) >= P.gamble_floor:
                    add([(p[0], p[1], c, n[0], n[1])], 1.5)
            elif n in theirs and 2 * c < 3 * theirs[n]:
                # against monsters EVERY attack is considered, even a 3% lottery ticket: the defender
                # loses its whole group if it fails, so the side being attacked must see it coming
                pr = win_probability(c, theirs[n], False)
                add([(p[0], p[1], c, n[0], n[1])], 1 + pr)

        # 6. positional steps (low priority; they matter when nothing above applies, e.g. the
        #    remaining human groups are too big for anybody): toward the nearest enemy group,
        #    away from it, toward the biggest human group.
        if theirs_t:
            qe, e = min(theirs_t, key=lambda qe: (cheb(p, qe[0]), qe[0]))
            if cheb(p, qe) > 2:
                n = step(p, qe, c)
                if n is not None and danger(n, c) < 2:
                    add([(p[0], p[1], c, n[0], n[1])], 0.5)
            far, far_key = None, None
            for n in nbr[p]:
                if n in theirs or (n in hum and hum[n] > c):
                    continue
                key = (cheb(n, qe), -danger(n, c), n)
                if far_key is None or key > far_key:
                    far, far_key = n, key
            if far is not None:
                add([(p[0], p[1], c, far[0], far[1])], 0.4)
        big = [(h, q) for q, h in hum_t if h > c]
        if big:
            h, q = max(big)
            if cheb(p, q) > 1:
                n = step(p, q, c)
                if n is not None:
                    add([(p[0], p[1], c, n[0], n[1])], 0.3)

        # 7. a lone group with nothing to do still has to move: best quiet neighbour
        if not opts:
            best, best_key = None, None
            for n in nbr[p]:
                if not passable(n, c, n) or n in theirs or n in hum:
                    continue
                key = (-danger(n, c),
                       -min((cheb(n, q) for q, _ in theirs_t), default=0) if behind else
                       min((cheb(n, q) for q, _ in theirs_t), default=0), n)
                if best_key is None or key > best_key:
                    best, best_key = n, key
            if best is None:                             # completely surrounded: any neighbour
                best = nbr[p][0]
            add([(p[0], p[1], c, best[0], best[1])], 0)

        ranked = sorted(opts.items(), key=lambda kv: -kv[1])[:P.opts_per_group]
        if n_groups > 1:
            ranked.append(((), -1.0))                    # this group stays where it is
        per_group.append(ranked)

    def fits_in_a_byte(moves) -> bool:
        if all(m[2] <= MAX_COUNT for m in moves):
            return not too_big(moves)
        return False

    def cap_moves(moves):
        """At most 255 creatures leave a cell (per source, in total); the rest stays where it is."""
        out, sent = [], {}
        for x1, y1, n, x2, y2 in moves:
            k = (x1, y1)
            n = min(n, MAX_COUNT - sent.get(k, 0))
            if n > 0:
                sent[k] = sent.get(k, 0) + n
                out.append((x1, y1, n, x2, y2))
        return out

    def too_big(moves) -> bool:
        """Would this turn pile more than 255 of our creatures on one cell (merge or conversion)?"""
        arrive: Dict[Pos, int] = {}
        for m in moves:
            arrive[(m[3], m[4])] = arrive.get((m[3], m[4]), 0) + m[2]
        for d, a in arrive.items():
            if a + mine.get(d, 0) + hum.get(d, 0) > MAX_COUNT:
                return True
        return False

    oversized: List[Turn] = []

    # joint turns, best-first by the sum of option ranks (0 = each group's favourite)
    turns: List[Turn] = []
    start = (0,) * len(per_group)
    heap = [(0, start)]
    seen = {start}
    pops = 0
    while heap and len(turns) < limit and pops < 20 * limit:
        cost, idx = heapq.heappop(heap)
        pops += 1
        moves = []
        for opts, i in zip(per_group, idx):
            moves.extend(opts[i][0])
        if moves and not fits_in_a_byte(moves):
            moves = cap_moves(moves)
            if too_big(moves):
                oversized.append(tuple(moves))      # kept only if nothing else is possible
                moves = []
        if moves:
            srcs = {(m[0], m[1]) for m in moves}
            if all((m[3], m[4]) not in srcs for m in moves):          # Rule 5
                gambles = 0
                for m in moves:
                    d = (m[3], m[4])
                    if (d in hum and hum[d] > m[2]) or (d in theirs and 2 * m[2] < 3 * theirs[d]):
                        gambles += 1
                if gambles <= 1:
                    turns.append(tuple(moves))
        for j in range(len(idx)):
            if idx[j] + 1 < len(per_group[j]):
                nxt = idx[:j] + (idx[j] + 1,) + idx[j + 1:]
                if nxt not in seen:
                    seen.add(nxt)
                    heapq.heappush(heap, (cost + 1, nxt))
    if not turns and oversized:
        turns = oversized[:1]
    return turns


# ===================================================================== search

class _Timeout(Exception):
    pass


EXACT, LOWER, UPPER = 0, 1, 2


class Searcher:
    def __init__(self, geo: Geometry, P: Params):
        self.geo = geo
        self.P = P
        self.tt: Dict[tuple, tuple] = {}
        self.gen_cache: Dict[tuple, List[Turn]] = {}     # (S, side) -> generated turns (reused by deeper iterations)
        self.deadline = INF
        self.nodes = 0
        self.root = -1

    def negamax(self, S, side: int, depth: int, alpha: float, beta: float) -> float:
        self.nodes += 1
        if not (self.nodes & 31) and time.perf_counter() > self.deadline:
            raise _Timeout()
        mine, theirs = S[side], S[1 - side]
        if not mine or not theirs or S[3] >= MAX_PLY:
            return terminal_value(sum(n for _, n in mine), sum(n for _, n in theirs), S[3])
        if depth <= 0:
            return evaluate(S, side, self.P, self.root)

        key = (S, side)
        entry = self.tt.get(key)
        tt_turn = None
        if entry is not None:
            e_depth, e_val, e_flag, tt_turn = entry
            if e_depth >= depth:
                if e_flag == EXACT:
                    return e_val
                if e_flag == LOWER:
                    if e_val > alpha:
                        alpha = e_val
                elif e_val < beta:
                    beta = e_val
                if alpha >= beta:
                    return e_val

        turns = self.gen_cache.get(key)
        if turns is None:
            turns = gen_turns(S, side, self.geo, self.P, self.P.max_turns)
            self.gen_cache[key] = turns
        else:
            turns = list(turns)
        if tt_turn is not None:
            if tt_turn in turns:
                turns.remove(tt_turn)
            turns.insert(0, tt_turn)

        alpha0 = alpha
        best, best_turn = -INF, None
        pvs = self.P.pvs
        for i, turn in enumerate(turns):
            if pvs and i > 0 and beta - alpha > 1e-9:
                # PVS: prove with a zero-width window that this turn is NOT better than alpha;
                # only if the test fails (v > alpha) search it again with the real window
                v = self.turn_value(S, side, turn, depth, alpha, alpha + 1e-9)
                if alpha < v < beta:
                    v = self.turn_value(S, side, turn, depth, v, beta)
            else:
                v = self.turn_value(S, side, turn, depth, alpha, beta)
            if v > best:
                best, best_turn = v, turn
                if v > alpha:
                    alpha = v
                    if alpha >= beta:
                        break
        flag = UPPER if best <= alpha0 else (LOWER if best >= beta else EXACT)
        self.tt[key] = (depth, best, flag, best_turn)
        return best

    def turn_value(self, S, side: int, turn: Turn, depth: int, alpha: float, beta: float) -> float:
        """Value for `side` of playing `turn`: a plain child, or a CHANCE node (Star1 pruning)."""
        outcomes = apply_turn(S, side, turn)
        if len(outcomes) == 1:
            return -self.negamax(outcomes[0][1], 1 - side, depth - 1, -beta, -alpha)
        lo, hi = -WIN, WIN
        acc, rest = 0.0, 1.0
        for p, child in outcomes:
            rest -= p
            a_i = (alpha - acc - rest * hi) / p
            b_i = (beta - acc - rest * lo) / p
            v = -self.negamax(child, 1 - side, depth - 1, -min(b_i, hi), -max(a_i, lo))
            if v <= a_i:
                return acc + p * v + rest * hi          # upper bound <= alpha: fail low
            if v >= b_i:
                return acc + p * v + rest * lo          # lower bound >= beta: fail high
            acc += p * v
        return acc

    def search(self, S, side: int, budget: float):
        """Iterative deepening. Returns (best turn, info dict)."""
        start = time.perf_counter()
        self.deadline = start + budget
        self.nodes = 0
        if side != self.root or len(self.tt) > self.P.tt_max:
            self.tt.clear()                          # TT values contain the root's confidence bonus
        if len(self.gen_cache) > self.P.tt_max // 3:
            self.gen_cache.clear()
        self.root = side
        root = gen_turns(S, side, self.geo, self.P, self.P.root_turns)
        info = {"depth": 0, "nodes": 0, "value": 0.0, "root_turns": len(root), "seconds": 0.0}
        if not root:
            return None, info
        best_turn = root[0]
        if len(root) == 1:
            info["seconds"] = time.perf_counter() - start
            return best_turn, info
        scores = {t: 0.0 for t in root}
        last_iter = 0.0
        for depth in range(1, self.P.max_depth + 1):
            now = time.perf_counter()
            remaining = self.deadline - now
            if depth > 2 and last_iter * 3.0 > remaining:          # next iteration would not finish
                break
            it_start = now
            order = sorted(root, key=lambda t: -scores[t])
            alpha = -INF
            it_best, it_val = None, -INF
            try:
                for i, turn in enumerate(order):
                    v = self.turn_value(S, side, turn, depth, alpha, INF)
                    scores[turn] = v                 # exact for the best, an upper bound for the others
                    if v > it_val:
                        it_best, it_val = turn, v
                        alpha = v
            except _Timeout:
                # The previous best was searched first in this iteration; any turn that finished
                # with a better value at this greater depth is the more reliable choice.
                if it_best is not None:
                    best_turn = it_best
                break
            best_turn = it_best
            info["depth"], info["value"] = depth, it_val
            last_iter = time.perf_counter() - it_start
            if abs(it_val) >= WIN - 0.1:             # forced win or loss found: deeper adds nothing
                break
        info["nodes"] = self.nodes
        info["seconds"] = time.perf_counter() - start
        return best_turn, info


# ===================================================================== agent

def state_from_game(state: GameState, ply: int):
    v, w, h = [], [], []
    for pos, cell in state.board.items():
        if cell.vampires:
            v.append((pos, cell.vampires))
        if cell.werewolves:
            w.append((pos, cell.werewolves))
        if cell.humans:
            h.append((pos, cell.humans))
    return (tuple(sorted(v)), tuple(sorted(w)), tuple(sorted(h)), ply)


class DeepAgent:
    """Same interface as the repo's AIAgent: compute_moves(GameState) -> list of moves.
    Use it through SafeAgent (legality gate + fallbacks) on the real server."""

    def __init__(self, name: str = "DeepBot", time_limit: Optional[float] = None, **params):
        self.name = name
        self.P = Params(**params)
        if time_limit is not None:
            self.P.time_budget = time_limit
        self.searcher: Optional[Searcher] = None
        self.last_info: dict = {}
        # Python's cyclic garbage collector is switched off for the whole process: our search only
        # creates tuples and dicts freed by reference counting, and with a transposition table of
        # 10^5-10^6 entries a single automatic collection pauses the program for ~0.2 s (measured),
        # which could push a turn past the 2-second limit.
        gc.disable()
        self.new_game()

    def new_game(self):
        """Call at the start of every game (main.py does it on MAP; self-play makes fresh agents)."""
        self.calls = 0
        self.game_start: Optional[float] = None
        self.searcher = None

    def _budget(self, ply: int) -> float:
        """Per-turn budget: the fixed limit, reduced if the 5-minute game clock would run out."""
        now = time.perf_counter()
        if self.game_start is None:
            self.game_start = now
        left_time = self.P.game_seconds - (now - self.game_start) - 5.0
        left_plies = max(2, MAX_PLY - ply)
        fair = 2.0 * left_time / left_plies * 0.9     # our half of the time per remaining ply pair
        return max(0.2, min(self.P.time_budget, fair))

    def compute_moves(self, state: GameState) -> List[Move]:
        side = 0 if state.our_species == Species.VAMPIRE else 1
        ply = 2 * self.calls + side                   # vampires play the even plies
        self.calls += 1
        S = state_from_game(state, ply)
        if self.searcher is None or self.searcher.geo.cols != state.cols or self.searcher.geo.rows != state.rows:
            self.searcher = Searcher(Geometry(state.cols, state.rows), self.P)
        turn, info = self.searcher.search(S, side, self._budget(ply))
        self.last_info = info
        return list(turn) if turn else []
