# MCTS agent with a "race to the humans" heuristic
# usage: MCTSAgent().compute_moves(board, species) -> list of (x1, y1, n, x2, y2)
# test locally with: python mcts_arena.py --rival AlphaBeta --time 0.3

import math
import random
import time
from typing import Dict, List, Optional, Tuple

from game_state import Species
from game_engine import BoardState, chebyshev_dist

Pos = Tuple[int, int]
Move = Tuple[int, int, int, int, int]          # (src_x, src_y, count, dst_x, dst_y)


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

def step_toward(state: BoardState, src: Pos, goal: Pos, count: int,
                forbidden: set, threats: List[Tuple[Pos, int]]) -> Optional[Pos]:
    # one step towards goal, avoiding forbidden cells and dangerous enemies
    best, best_key = None, None
    for n in state.get_neighbors(src):
        if n in forbidden:
            continue                             # rule 5
        danger = 0
        for tpos, tcnt in threats:
            if tcnt >= 1.5 * count and chebyshev_dist(n, tpos) <= 1 and n != goal:
                danger += tcnt
        # least danger first, then closest, manhattan just to avoid zig-zags
        key = (danger, chebyshev_dist(n, goal),
               abs(n[0] - goal[0]) + abs(n[1] - goal[1]))
        if best_key is None or key < best_key:
            best, best_key = n, key
    return best


def group_goals(state: BoardState, pos: Pos, count: int,
                friends: List[Tuple[Pos, int]], enemies: List[Tuple[Pos, int]],
                humans: List[Tuple[Pos, int]]) -> List[Tuple[float, Pos]]:
    # where one group could go, best first, as (value, cell)
    goals: List[Tuple[float, Pos]] = []
    for hpos, hcnt in humans:
        if count >= hcnt:                        # enough to convert
            d = chebyshev_dist(pos, hpos)
            goals.append((hcnt / (d + 0.5), hpos))
    for epos, ecnt in enemies:
        if count >= 1.5 * ecnt:                  # safe kill
            d = chebyshev_dist(pos, epos)
            goals.append((1.2 * ecnt / (d + 0.5), epos))
    if friends:                                  # regroup with closest friend
        fpos, fcnt = min(friends, key=lambda f: chebyshev_dist(pos, f[0]))
        d = chebyshev_dist(pos, fpos)
        goals.append((0.3 * fcnt / (d + 0.5), fpos))
    dangerous = [(e, c) for e, c in enemies
                 if c >= 1.5 * count and chebyshev_dist(pos, e) <= 3]
    if dangerous:                                # run away
        flee = max(state.get_neighbors(pos),
                   key=lambda n: min(chebyshev_dist(n, e) for e, _ in dangerous))
        goals.append((0.5 * count, flee))
    if not goals and enemies:                    # nothing to do -> chase enemy
        epos, _ = min(enemies, key=lambda e: chebyshev_dist(pos, e[0]))
        goals.append((0.01, epos))
    if not goals:
        goals.append((0.0, (state.cols // 2, state.rows // 2)))
    goals.sort(key=lambda g: -g[0])
    return goals


def build_turn(state: BoardState, species: Species, choices: Dict[Pos, Pos],
               groups: List[Tuple[Pos, int]], enemies: List[Tuple[Pos, int]]) -> List[Move]:
    # {group pos: goal} -> list of moves, one step each
    sources = {p for p, _ in groups}
    moves: List[Move] = []
    for pos, count in groups:
        goal = choices.get(pos)
        if goal is None:
            continue
        dst = step_toward(state, pos, goal, count, sources, enemies)
        if dst is not None:
            moves.append((pos[0], pos[1], count, dst[0], dst[1]))
    return moves


def generate_plans(state: BoardState, species: Species, max_plans: int = 12) -> List[List[Move]]:
    # short list of full turns for the tree to compare (not every possible move)
    groups, enemies, humans = split_board(state, species)
    if not groups:
        return []

    per_group = {}                               # top 3 goals of each group
    for pos, cnt in groups:
        friends = [(p, c) for p, c in groups if p != pos]
        per_group[pos] = group_goals(state, pos, cnt, friends, enemies, humans)[:3]

    plans: List[List[Move]] = []
    seen = set()

    def add(moves: List[Move]):
        key = tuple(sorted(moves))
        if moves and key not in seen:            # skip empty / duplicate plans
            seen.add(key)
            plans.append(moves)

    # every group goes to its best goal
    default = {pos: goals[0][1] for pos, goals in per_group.items()}
    add(build_turn(state, species, default, groups, enemies))

    # same but one group takes its 2nd or 3rd choice
    for pos, goals in per_group.items():
        for _, alt in goals[1:]:
            choice = dict(default)
            choice[pos] = alt
            add(build_turn(state, species, choice, groups, enemies))

    # everyone joins the biggest group
    if len(groups) > 1:
        big_pos = max(groups, key=lambda g: g[1])[0]
        regroup = {pos: big_pos for pos, _ in groups if pos != big_pos}
        add(build_turn(state, species, regroup, groups, enemies))

    # splits: e.g. 7 -> 3 to a house of 3 and 4 to a house of 4
    sources = {p for p, _ in groups}
    for pos, cnt in groups:
        if cnt < 2:
            continue
        options = []
        for i, (h1, c1) in enumerate(humans):
            for h2, c2 in humans[i + 1:]:
                for (ha, ca), (hb, cb) in (((h1, c1), (h2, c2)), ((h2, c2), (h1, c1))):
                    if ca <= cnt - cb and cb <= cnt - ca:    # both halves big enough
                        d = chebyshev_dist(pos, ha) + chebyshev_dist(pos, hb)
                        options.append(((ca + cb) / (d + 1.0), ha, ca, hb))
        options.sort(key=lambda o: -o[0])
        for _, ha, ca, hb in options[:2]:        # keep the 2 best splits
            dst_a = step_toward(state, pos, ha, ca, sources, enemies)
            dst_b = step_toward(state, pos, hb, cnt - ca, sources | {dst_a}, enemies)
            if dst_a is None or dst_b is None:
                continue
            split = [(pos[0], pos[1], ca, dst_a[0], dst_a[1]),
                     (pos[0], pos[1], cnt - ca, dst_b[0], dst_b[1])]
            others = {p: g for p, g in default.items() if p != pos}
            rest = build_turn(state, species, others,
                              [(p, c) for p, c in groups if p != pos], enemies)
            rest = [m for m in rest if (m[3], m[4]) != pos]  # can't move into the split cell
            add(split + rest)

    if not plans:                                # fallback: any legal move
        pos, cnt = groups[0]
        for n in state.get_neighbors(pos):
            if n not in sources:
                plans.append([(pos[0], pos[1], cnt, n[0], n[1])])
                break
    return plans[:max_plans]


def rollout_plan(state: BoardState, species: Species, epsilon: float = 0.15) -> List[Move]:
    # moves used in the imaginary games: greedy, with a bit of randomness
    groups, enemies, humans = split_board(state, species)
    if not groups:
        return []
    choices = {}
    for pos, cnt in groups:
        friends = [(p, c) for p, c in groups if p != pos]
        goals = group_goals(state, pos, cnt, friends, enemies, humans)
        if len(goals) > 1 and random.random() < epsilon:
            choices[pos] = goals[1][1]           # sometimes take the 2nd best
        else:
            choices[pos] = goals[0][1]
    return build_turn(state, species, choices, groups, enemies)


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
        best = max(root.children, key=lambda ch: ch.visits)   # most visited plan
        return best.moves
