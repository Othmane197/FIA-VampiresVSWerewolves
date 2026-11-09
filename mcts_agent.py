# MCTS agent with a "race to the humans" heuristic
# usage: MCTSAgent().compute_moves(board, species) -> list of (x1, y1, n, x2, y2)
# test locally with: python mcts_arena.py --rival AlphaBeta --time 0.3
# attack mode (divide and conquer) is off unless RONITA_ATTACK=1

import math
import os
import random
import time
from typing import Dict, List, Optional, Tuple

from game_state import Species
from game_engine import BoardState, chebyshev_dist

Pos = Tuple[int, int]
Group = Tuple[Pos, int]                        # (cell, creatures)
Move = Tuple[int, int, int, int, int]          # (src_x, src_y, count, dst_x, dst_y)

ATTACK_MODE = os.environ.get("RONITA_ATTACK", "0") == "1"
KILL_WEIGHT = 2.4 if ATTACK_MODE else 1.2      # how strongly sure kills are hunted
STRIKE_RATIO = 1.1                             # attack mode strikes at 1.1x or more (wins 60%+)
MAX_DETACHMENTS = 3                            # attack mode: houses one group can raid at once
MAX_PLANS = 12                                 # plans the tree compares each turn


def other_species(species: Species) -> Species:
    return Species.WEREWOLF if species == Species.VAMPIRE else Species.VAMPIRE


def split_board(state: BoardState, species: Species):
    # one pass over the board -> our groups, enemy groups, humans
    ours, theirs, humans = [], [], []
    is_vamp = species == Species.VAMPIRE
    for pos, (h, v, w) in state.grid.items():
        if h:
            humans.append((pos, h))
        mine, enemy = (v, w) if is_vamp else (w, v)
        if mine:
            ours.append((pos, mine))
        if enemy:
            theirs.append((pos, enemy))
    return ours, theirs, humans


# ---------------- heuristic ----------------

def race_projection(state: BoardState, us: Species, to_move: Species,
                    discount: float = 0.95) -> Tuple[float, float]:
    # predicts both army sizes after the humans are shared out
    them = other_species(us)
    ours, theirs, humans = split_board(state, us)

    # groups next to an enemy 1.5x bigger are dead if it's the enemy's turn
    if to_move == us:
        victims, hunters = theirs, ours
    else:
        victims, hunters = ours, theirs
    survivors = []
    for vpos, vcnt in victims:
        eaten = any(hcnt >= 1.5 * vcnt and chebyshev_dist(vpos, hpos) == 1
                    for hpos, hcnt in hunters)
        if not eaten:
            survivors.append((vpos, vcnt))
    if to_move == us:
        theirs = survivors
    else:
        ours = survivors

    # runner = [pos, count, clock, is_ours], side to move gets a head start
    runners = [[p, c, 0.0 if to_move == us else 0.5, True] for p, c in ours]
    runners += [[p, c, 0.0 if to_move == them else 0.5, False] for p, c in theirs]
    remaining_plies = max(1, state.max_turns - state.turn_count)
    horizon = remaining_plies / 2.0             # each side plays half the plies

    proj_us = float(sum(c for _, c in ours))
    proj_them = float(sum(c for _, c in theirs))
    houses = dict(humans)

    while houses and runners:
        # find the earliest capture of any house by any group
        best = None                              # (arrival, runner, house_pos)
        for r in runners:
            rpos, rcnt, rclock = r[0], r[1], r[2]
            for hpos, hcnt in houses.items():
                if rcnt < hcnt:
                    continue                     # too small to convert alone
                arrival = rclock + chebyshev_dist(rpos, hpos)
                if best is None or arrival < best[0]:
                    best = (arrival, r, hpos)
        if best is None or best[0] > horizon:
            break                                # nothing reachable before the end
        arrival, r, hpos = best
        gain = houses.pop(hpos)
        r[0], r[1], r[2] = hpos, r[1] + gain, arrival    # group moves there and grows
        weighted = gain * (discount ** arrival)  # far houses count a bit less
        if r[3]:
            proj_us += weighted
        else:
            proj_them += weighted

    return proj_us, proj_them


def evaluate(state: BoardState, us: Species, to_move: Species) -> float:
    # score in [0, 1], 1 = we win
    over, winner = state.is_game_over()
    if over:
        if winner is None:
            return 0.5
        return 1.0 if winner == us else 0.0

    pu, pe = race_projection(state, us, to_move)
    if pu <= 0:
        return 0.0
    if pe <= 0:
        return 1.0
    score = pu / (pu + pe)
    if pu >= 1.5 * pe:
        score = (score + 1.0) / 2.0              # bonus: we can kill them for free
    elif pe >= 1.5 * pu:
        score = score / 2.0                      # they can kill us for free
    return score


# ---------------- plans ----------------

_NEIGHBOURS: Dict[Tuple[int, int], Dict[Pos, List[Pos]]] = {}


def neighbours(state: BoardState, pos: Pos) -> List[Pos]:
    # the 8 neighbours of every cell, worked out once per board size
    table = _NEIGHBOURS.get((state.cols, state.rows))
    if table is None:
        table = {}
        for x in range(state.cols):
            for y in range(state.rows):
                table[(x, y)] = [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                                 if (dx or dy) and 0 <= x + dx < state.cols and 0 <= y + dy < state.rows]
        _NEIGHBOURS[(state.cols, state.rows)] = table
    return table[pos]


def is_leading(groups: List[Group], enemies: List[Group]) -> bool:
    # the bigger side wins when time runs out, so a lead is worth protecting
    return sum(c for _, c in groups) > sum(c for _, c in enemies)


def threat_map(state: BoardState, enemies: List[Group], leading: bool = False):
    # once per turn: who stands where, and which enemy sizes touch each cell
    enemy_at = dict(enemies)
    adjacent: Dict[Pos, List[int]] = {}
    for tpos, tc in enemies:
        adjacent.setdefault(tpos, []).append(tc)
        for n in neighbours(state, tpos):
            adjacent.setdefault(n, []).append(tc)
    return enemy_at, adjacent, leading


def step_toward(state: BoardState, src: Pos, goal: Pos, count: int,
                forbidden: set, tmap) -> Optional[Pos]:
    # one step towards goal; never walks into a fight by accident:
    # no stepping onto an enemy or humans unless it wins for sure, and
    # avoids ending next to an enemy at least our size (it would strike first at 50%+)
    gx, gy = goal
    enemy_at, adjacent, leading = tmap
    grid = state.grid
    best, best_key = None, None
    risky, risky_key = None, None                # only used if every step is unsure
    for n in neighbours(state, src):
        if n in forbidden:
            continue                             # rule 5
        unsure = False
        e = enemy_at.get(n)
        if e is not None and count < 1.5 * e:
            # a dice battle: attack mode allows it only as the chosen target at good odds
            unsure = not (ATTACK_MODE and n == goal and count >= STRIKE_RATIO * e)
        cell = grid.get(n)
        if cell is not None and 0 < cell[0] and count < cell[0]:
            unsure = True                        # humans we can't convert for sure
        danger = 0
        if n != goal:
            near = adjacent.get(n)
            if near:
                # when ahead, even a small enemy is a risk: one lucky strike kills the whole group
                danger = sum(near) if leading else sum(tc for tc in near if tc >= count)
        dx, dy = abs(n[0] - gx), abs(n[1] - gy)
        # least danger first, then closest, dx + dy just to avoid zig-zags
        key = (danger, dx if dx > dy else dy, dx + dy)
        if unsure:
            if risky_key is None or key < risky_key:
                risky, risky_key = n, key
        elif best_key is None or key < best_key:
            best, best_key = n, key
    return best if best is not None else risky


def group_goals(state: BoardState, pos: Pos, count: int, friends: List[Group],
                enemies: List[Group], humans: List[Group],
                leading: bool = False) -> List[Tuple[float, Pos]]:
    # where one group could go, best first, as (value, cell)
    # when leading: no hunting, only kills already next to us, then keep away and let time win
    goals: List[Tuple[float, Pos]] = []
    px, py = pos
    for hpos, hcnt in humans:
        if count >= hcnt:                        # enough to convert
            d = max(abs(hpos[0] - px), abs(hpos[1] - py))
            goals.append((hcnt / (d + 0.5), hpos))
    for epos, ecnt in enemies:
        d = max(abs(epos[0] - px), abs(epos[1] - py))
        if count >= 1.5 * ecnt:                  # safe kill
            if d == 1 or not leading:
                goals.append((KILL_WEIGHT * ecnt / (d + 0.5), epos))
        elif ATTACK_MODE and count >= STRIKE_RATIO * ecnt:
            p = count / ecnt - 0.5               # good-odds strike, weighted by its odds
            goals.append((KILL_WEIGHT * p * ecnt / (d + 0.5), epos))
    if friends:                                  # regroup with closest friend
        fpos, fcnt = min(friends, key=lambda f: chebyshev_dist(pos, f[0]))
        d = chebyshev_dist(pos, fpos)
        # a group smaller than an enemy on the board is prey: pull it back to its friends
        hunted = any(c >= 1.5 * count for _, c in enemies)
        goals.append(((0.9 if hunted else 0.3) * fcnt / (d + 0.5), fpos))
    dangerous = [(e, c) for e, c in enemies
                 if c >= 1.5 * count and chebyshev_dist(pos, e) <= 3]
    if dangerous:                                # run away
        flee = max(neighbours(state, pos),
                   key=lambda n: min(chebyshev_dist(n, e) for e, _ in dangerous))
        goals.append((0.5 * count, flee))
    if not goals and enemies:
        if leading:                              # nothing to do -> stay out of reach
            away = max(neighbours(state, pos),
                       key=lambda n: min(chebyshev_dist(n, e) for e, _ in enemies))
            goals.append((0.01, away))
        else:                                    # nothing to do -> chase enemy
            epos, _ = min(enemies, key=lambda e: chebyshev_dist(pos, e[0]))
            goals.append((0.01, epos))
    if not goals:
        goals.append((0.0, (state.cols // 2, state.rows // 2)))
    goals.sort(key=lambda g: -g[0])
    return goals


def build_turn(state: BoardState, choices: Dict[Pos, Pos], groups: List[Group], tmap) -> List[Move]:
    # {group pos: goal} -> list of moves, one step each
    sources = {p for p, _ in groups}
    moves: List[Move] = []
    for pos, count in groups:
        goal = choices.get(pos)
        if goal is None:
            continue
        dst = step_toward(state, pos, goal, count, sources, tmap)
        if dst is not None:
            moves.append((pos[0], pos[1], count, dst[0], dst[1]))
    return moves


def other_groups_moves(state: BoardState, pos: Pos, default: Dict[Pos, Pos],
                       groups: List[Group], tmap) -> List[Move]:
    # what the other groups do while the group at pos splits
    others = {p: g for p, g in default.items() if p != pos}
    rest = build_turn(state, others, [g for g in groups if g[0] != pos], tmap)
    return [m for m in rest if (m[3], m[4]) != pos]  # can't move into the split cell


def walk_is_safe(pos: Pos, count: int, house: Pos, hcnt: int, enemies: List[Group]) -> bool:
    # idea from Mohamed's Splitter: can a small group reach this house and survive?
    # unsafe if an enemy its size or bigger can touch it on the way, or catch it on arrival
    x, y = pos
    hx, hy = house
    dist = max(abs(hx - x), abs(hy - y))
    after = count + hcnt
    for epos, ecnt in enemies:
        if ecnt >= after and chebyshev_dist(epos, house) <= dist:
            return False
        if ecnt >= count:
            cx, cy = x, y
            for t in range(1, dist):
                cx += (hx > cx) - (hx < cx)
                cy += (hy > cy) - (hy < cy)
                if max(abs(epos[0] - cx), abs(epos[1] - cy)) <= t:
                    return False
    return True


def two_house_splits(state: BoardState, pos: Pos, cnt: int, humans: List[Group],
                     enemies: List[Group], sources: set, tmap) -> List[List[Move]]:
    # e.g. 7 -> 3 to a house of 3 and 4 to a house of 4; keeps the 2 best safe ones
    options = []
    for i, (h1, c1) in enumerate(humans):
        for h2, c2 in humans[i + 1:]:
            for (ha, ca), (hb, cb) in (((h1, c1), (h2, c2)), ((h2, c2), (h1, c1))):
                if ca <= cnt - cb and cb <= cnt - ca:    # both halves big enough
                    if not (walk_is_safe(pos, ca, ha, ca, enemies)
                            and walk_is_safe(pos, cnt - ca, hb, cb, enemies)):
                        continue
                    d = chebyshev_dist(pos, ha) + chebyshev_dist(pos, hb)
                    options.append(((ca + cb) / (d + 1.0), ha, ca, hb))
    options.sort(key=lambda o: -o[0])
    splits = []
    for _, ha, ca, hb in options[:2]:
        dst_a = step_toward(state, pos, ha, ca, sources, tmap)
        dst_b = step_toward(state, pos, hb, cnt - ca, sources | {dst_a}, tmap)
        if dst_a is not None and dst_b is not None:
            splits.append([(pos[0], pos[1], ca, dst_a[0], dst_a[1]),
                           (pos[0], pos[1], cnt - ca, dst_b[0], dst_b[1])])
    return splits


def detachment_orders(state: BoardState, pos: Pos, cnt: int, goal: Pos, humans: List[Group],
                      sources: set, tmap) -> List[Move]:
    # attack mode: exact-size groups to up to 3 houses, the rest keeps walking to goal
    px, py = pos
    houses = sorted((h for h in humans if h[1] <= cnt),
                    key=lambda h: -h[1] / (max(abs(h[0][0] - px), abs(h[0][1] - py)) + 0.5))
    left, used, orders = cnt, set(), []
    for hpos, hcnt in houses:
        if len(orders) == MAX_DETACHMENTS or hcnt > left:
            continue
        dst = step_toward(state, pos, hpos, hcnt, sources | used, tmap)
        if dst is None:
            continue
        orders.append((px, py, hcnt, dst[0], dst[1]))
        used.add(dst)
        left -= hcnt
    if len(orders) < 2:
        return []
    if left:
        dst = step_toward(state, pos, goal, left, sources | used, tmap)
        if dst is not None and dst not in used:
            orders.append((px, py, left, dst[0], dst[1]))
    return orders


def generate_plans(state: BoardState, species: Species) -> List[List[Move]]:
    # short list of full turns for the tree to compare (not every possible move)
    groups, enemies, humans = split_board(state, species)
    if not groups:
        return []
    leading = is_leading(groups, enemies)
    tmap = threat_map(state, enemies, leading)
    sources = {p for p, _ in groups}

    top_goals = {}                               # top 3 goals of each group
    for pos, cnt in groups:
        friends = [g for g in groups if g[0] != pos]
        top_goals[pos] = group_goals(state, pos, cnt, friends, enemies, humans, leading)[:3]

    plans: List[List[Move]] = []
    seen = set()

    def add(moves: List[Move]):
        key = tuple(sorted(moves))
        if moves and key not in seen:            # skip empty / duplicate plans
            seen.add(key)
            plans.append(moves)

    # every group goes to its best goal
    default = {pos: goals[0][1] for pos, goals in top_goals.items()}
    add(build_turn(state, default, groups, tmap))

    # same but one group takes its 2nd or 3rd choice
    for pos, goals in top_goals.items():
        for _, alt in goals[1:]:
            add(build_turn(state, {**default, pos: alt}, groups, tmap))

    # everyone joins the biggest group
    if len(groups) > 1:
        big_pos = max(groups, key=lambda g: g[1])[0]
        add(build_turn(state, {pos: big_pos for pos, _ in groups if pos != big_pos}, groups, tmap))

    for pos, cnt in groups:
        if cnt >= 2:
            for split in two_house_splits(state, pos, cnt, humans, enemies, sources, tmap):
                add(split + other_groups_moves(state, pos, default, groups, tmap))

    if ATTACK_MODE:
        before = len(plans)
        for pos, cnt in groups:
            orders = detachment_orders(state, pos, cnt, default[pos], humans, sources, tmap)
            if orders:
                add(orders + other_groups_moves(state, pos, default, groups, tmap))
        # right after the default plan, so they stay inside the MAX_PLANS
        attack = plans[before:]
        del plans[before:]
        plans[1:1] = attack

    if not plans:                                # fallback: any legal move
        pos, cnt = groups[0]
        for n in neighbours(state, pos):
            if n not in sources:
                plans.append([(pos[0], pos[1], cnt, n[0], n[1])])
                break
    return plans[:MAX_PLANS]


def rollout_plan(state: BoardState, species: Species, epsilon: float = 0.15) -> List[Move]:
    # moves used in the imaginary games: greedy, with a bit of randomness
    groups, enemies, humans = split_board(state, species)
    if not groups:
        return []
    leading = is_leading(groups, enemies)
    choices = {}
    for pos, cnt in groups:
        friends = [g for g in groups if g[0] != pos]
        goals = group_goals(state, pos, cnt, friends, enemies, humans, leading)
        if len(goals) > 1 and random.random() < epsilon:
            choices[pos] = goals[1][1]           # sometimes take the 2nd best
        else:
            choices[pos] = goals[0][1]
    return build_turn(state, choices, groups, threat_map(state, enemies, leading))


# ---------------- tree search ----------------

class MCTSNode:
    __slots__ = ("moves", "mover", "parent", "children", "untried",
                 "visits", "value")

    def __init__(self, moves: Optional[List[Move]], mover: Optional[Species],
                 parent: Optional["MCTSNode"]):
        self.moves = moves                       # the plan played to get here
        self.mover = mover                       # who played it
        self.parent = parent
        self.children: List["MCTSNode"] = []
        self.untried: Optional[List[List[Move]]] = None   # filled on first visit
        self.visits = 0
        self.value = 0.0                         # sum of scores, from our side


class MCTSAgent:
    def __init__(self, name: str = "RaceMCTS", max_time_seconds: float = 1.6,
                 rollout_depth: int = 8, exploration: float = 0.7):
        self.name = name
        self.max_time = max_time_seconds         # server gives 2s, keep a margin
        self.rollout_depth = rollout_depth       # moves per imaginary game
        self.c = exploration                     # UCB1 constant
        self.last_iterations = 0

    def _select_child(self, node: MCTSNode, us: Species) -> MCTSNode:
        # UCB1 = avg score + c * sqrt(ln(N) / n)
        log_n = math.log(node.visits)
        best, best_ucb = None, -1.0
        for child in node.children:
            avg = child.value / child.visits
            if child.mover != us:
                avg = 1.0 - avg                  # opponent picks what's best for them
            ucb = avg + self.c * math.sqrt(log_n / child.visits)
            if ucb > best_ucb:
                best, best_ucb = child, ucb
        return best

    def _rollout(self, state: BoardState, to_move: Species, us: Species) -> float:
        # short imaginary game with real dice, then score it
        for _ in range(self.rollout_depth):
            if state.is_game_over()[0]:
                break
            moves = rollout_plan(state, to_move)
            if not moves:
                break
            state = state.apply_moves(moves, to_move, deterministic=False)
            to_move = other_species(to_move)
        return evaluate(state, us, to_move)

    def _run_iteration(self, root: MCTSNode, root_state: BoardState, us: Species):
        node, state, to_move = root, root_state, us

        # 1. selection
        while node.untried is not None and not node.untried and node.children:
            child = self._select_child(node, us)
            # boards aren't stored, moves are replayed with new dice each time,
            # so a stored plan can become illegal (group smaller or dead)
            valid, _ = state.validate_moves(child.moves, to_move)
            if not valid:
                break
            state = state.apply_moves(child.moves, to_move, deterministic=False)
            node, to_move = child, other_species(to_move)

        # 2. expansion
        if not state.is_game_over()[0]:
            if node.untried is None:
                node.untried = generate_plans(state, to_move)
                random.shuffle(node.untried)
            while node.untried:
                moves = node.untried.pop()
                if state.validate_moves(moves, to_move)[0]:
                    child = MCTSNode(moves, to_move, node)
                    node.children.append(child)
                    state = state.apply_moves(moves, to_move, deterministic=False)
                    node, to_move = child, other_species(to_move)
                    break

        # 3. simulation
        score = self._rollout(state, to_move, us)

        # 4. backpropagation
        while node is not None:
            node.visits += 1
            node.value += score
            node = node.parent

    def compute_moves(self, state: BoardState, species: Species) -> List[Move]:
        start = time.time()
        self.last_iterations = 0
        plans = generate_plans(state, species)
        if not plans:
            return []
        if len(plans) == 1:
            return plans[0]                      # no choice, don't waste time

        root = MCTSNode(None, None, None)
        root.untried = list(plans)
        random.shuffle(root.untried)

        iterations = 0
        while time.time() - start < self.max_time:
            self._run_iteration(root, state, species)
            iterations += 1
        self.last_iterations = iterations

        if not root.children:
            return plans[0]
        return max(root.children, key=lambda ch: ch.visits).moves  # most visited plan
