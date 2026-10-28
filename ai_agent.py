"""
Harsha's AI Agent — rebuilt around the pattern that beat it in testing (Ronita's
approach): generate a handful of *sensible whole-turn plans* (not random single-group
steps), evaluate them with a house-race projection, and search with MCTS.
Root-parallelized: each CPU core runs an independent tree from the same position,
and the final move is chosen by summed visit count across all trees.
"""

import os
import sys
import time
import math
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from typing import Dict, List, Optional, Tuple

from game_state import GameState, Species
from game_engine import BoardState, chebyshev_dist

NUM_CORES     = max(1, (os.cpu_count() or 2) - 1)
TIME_LIMIT    = 1.4     # seconds of search per turn (server allows 2.0)
UCT_C         = 0.9     # UCB1 exploration constant; rewards are in [0, 1]
ROLLOUT_PLIES = 8       # imaginary plies played out after a candidate plan
MAX_PLANS     = 12      # candidate whole-turn plans considered per position
DEBUG         = os.environ.get("HARSHA_DEBUG") == "1"

Pos  = Tuple[int, int]
Move = Tuple[int, int, int, int, int]


def _opp(species: Species) -> Species:
    return Species.WEREWOLF if species == Species.VAMPIRE else Species.VAMPIRE


def _move_key(moves: List[Move]) -> str:
    return str(sorted(moves)) if moves else ""


# ═══════════════════════════════════════════════════════════════
#  STATE SNAPSHOT  — picklable for subprocess transfer
# ═══════════════════════════════════════════════════════════════
class StateSnapshot:
    __slots__ = ('rows', 'cols', 'grid', 'our_species', 'turn_count', 'max_turns')

    def __init__(self, rows, cols, grid, our_species, turn_count=0, max_turns=200):
        self.rows, self.cols = rows, cols
        self.grid = grid                # {(x,y): (humans, vampires, werewolves)}
        self.our_species = our_species
        self.turn_count = turn_count
        self.max_turns = max_turns

    def to_board_state(self) -> BoardState:
        bs = BoardState(self.rows, self.cols, self.max_turns)
        bs.grid = dict(self.grid)
        bs.turn_count = self.turn_count
        return bs


def game_state_to_snapshot(state: GameState) -> StateSnapshot:
    grid = {pos: (c.humans, c.vampires, c.werewolves) for pos, c in state.board.items()}
    return StateSnapshot(state.rows, state.cols, grid, state.our_species)


# ═══════════════════════════════════════════════════════════════
#  BOARD SPLIT + HOUSE-RACE EVALUATION
# ═══════════════════════════════════════════════════════════════
def split_board(board: BoardState, species: Species):
    """One pass over the grid -> (our groups, enemy groups, human groups)."""
    is_vamp = species == Species.VAMPIRE
    ours, theirs, humans = [], [], []
    for pos, (h, v, w) in board.grid.items():
        if h:
            humans.append((pos, h))
        mine, enemy = (v, w) if is_vamp else (w, v)
        if mine:
            ours.append((pos, mine))
        if enemy:
            theirs.append((pos, enemy))
    return ours, theirs, humans


def race_projection(board: BoardState, us: Species, to_move: Species, discount=0.95):
    """
    Predicts both final army sizes by letting each side race for the houses it
    reaches first, and killing any group a 1.5x-bigger adjacent enemy can hit on
    the mover's turn.
    """
    them = _opp(us)
    ours, theirs, humans = split_board(board, us)

    victims, hunters = (theirs, ours) if to_move == us else (ours, theirs)
    survivors = [(vp, vc) for vp, vc in victims
                 if not any(hc >= 1.5 * vc and chebyshev_dist(vp, hp) == 1
                            for hp, hc in hunters)]
    if to_move == us:
        theirs = survivors
    else:
        ours = survivors

    # runner = [pos, count, clock, is_ours]; side to move gets a head start
    runners = [[p, c, 0.0 if to_move == us else 0.5, True] for p, c in ours]
    runners += [[p, c, 0.0 if to_move == them else 0.5, False] for p, c in theirs]
    remaining_plies = max(1, board.max_turns - board.turn_count)
    horizon = remaining_plies / 2.0

    proj_us, proj_them = float(sum(c for _, c in ours)), float(sum(c for _, c in theirs))
    pool = dict(humans)

    while pool and runners:
        best = None                      # (arrival, runner, house_pos)
        for r in runners:
            rpos, rcnt, rclock = r[0], r[1], r[2]
            for hpos, hcnt in pool.items():
                if rcnt < hcnt:
                    continue
                arrival = rclock + chebyshev_dist(rpos, hpos)
                if best is None or arrival < best[0]:
                    best = (arrival, r, hpos)
        if best is None or best[0] > horizon:
            break
        arrival, r, hpos = best
        gain = pool.pop(hpos)
        r[0], r[1], r[2] = hpos, r[1] + gain, arrival
        weighted = gain * (discount ** arrival)
        if r[3]:
            proj_us += weighted
        else:
            proj_them += weighted

    return proj_us, proj_them


def evaluate(board: BoardState, us: Species, to_move: Species) -> float:
    """Score in [0, 1]; 1 means we win."""
    over, winner = board.is_game_over()
    if over:
        return 0.5 if winner is None else float(winner == us)

    pu, pe = race_projection(board, us, to_move)
    if pu <= 0:
        return 0.0
    if pe <= 0:
        return 1.0
    score = pu / (pu + pe)
    if pu >= 1.5 * pe:
        score = (score + 1.0) / 2.0      # bonus: we can wipe them out for free
    elif pe >= 1.5 * pu:
        score = score / 2.0              # they can wipe us out for free
    return score


# ═══════════════════════════════════════════════════════════════
#  CANDIDATE WHOLE-TURN PLANS
# ═══════════════════════════════════════════════════════════════
def _step_toward(board: BoardState, src: Pos, goal: Pos, count: int,
                  forbidden: set, threats: List[Tuple[Pos, int]]) -> Optional[Pos]:
    """One step towards goal, avoiding forbidden cells (Rule 5) and bad fights."""
    best, best_key = None, None
    for n in board.get_neighbors(src):
        if n in forbidden:
            continue
        danger = sum(tc for tp, tc in threats
                     if tc >= 1.5 * count and chebyshev_dist(n, tp) <= 1 and n != goal)
        key = (danger, chebyshev_dist(n, goal),
               abs(n[0] - goal[0]) + abs(n[1] - goal[1]))
        if best_key is None or key < best_key:
            best, best_key = n, key
    return best


def _group_goals(board: BoardState, pos: Pos, count: int,
                  friends: List[Tuple[Pos, int]], enemies: List[Tuple[Pos, int]],
                  humans: List[Tuple[Pos, int]]) -> List[Tuple[float, Pos]]:
    """Where one group could go, best first, as (value, cell)."""
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
    if dangerous:                                 # run away
        flee = max(board.get_neighbors(pos),
                   key=lambda n: min(chebyshev_dist(n, e) for e, _ in dangerous))
        goals.append((0.5 * count, flee))
    if not goals and enemies:                     # nothing to do -> chase enemy
        epos, _ = min(enemies, key=lambda e: chebyshev_dist(pos, e[0]))
        goals.append((0.01, epos))
    if not goals:
        goals.append((0.0, (board.cols // 2, board.rows // 2)))
    goals.sort(key=lambda g: -g[0])
    return goals


def _build_turn(board: BoardState, choices: Dict[Pos, Pos],
                 groups: List[Tuple[Pos, int]], enemies: List[Tuple[Pos, int]]) -> List[Move]:
    """{group pos: goal} -> list of moves, one step each."""
    sources = {p for p, _ in groups}
    moves: List[Move] = []
    for pos, count in groups:
        goal = choices.get(pos)
        if goal is None:
            continue
        dst = _step_toward(board, pos, goal, count, sources, enemies)
        if dst is not None:
            moves.append((pos[0], pos[1], count, dst[0], dst[1]))
    return moves


def generate_plans(board: BoardState, species: Species, max_plans: int = MAX_PLANS) -> List[List[Move]]:
    """Short list of full turns for the tree to compare (not every possible move)."""
    groups, enemies, humans = split_board(board, species)
    if not groups:
        return []

    per_group = {}                               # top 3 goals of each group
    for pos, cnt in groups:
        friends = [(p, c) for p, c in groups if p != pos]
        per_group[pos] = _group_goals(board, pos, cnt, friends, enemies, humans)[:3]

    plans: List[List[Move]] = []
    seen = set()

    def add(moves: List[Move]):
        key = tuple(sorted(moves))
        if moves and key not in seen:             # skip empty / duplicate plans
            seen.add(key)
            plans.append(moves)

    # every group goes to its best goal
    default = {pos: goals[0][1] for pos, goals in per_group.items()}
    add(_build_turn(board, default, groups, enemies))

    # same but one group takes its 2nd or 3rd choice
    for pos, goals in per_group.items():
        for _, alt in goals[1:]:
            choice = dict(default)
            choice[pos] = alt
            add(_build_turn(board, choice, groups, enemies))

    # everyone joins the biggest group
    if len(groups) > 1:
        big_pos = max(groups, key=lambda g: g[1])[0]
        regroup = {pos: big_pos for pos, _ in groups if pos != big_pos}
        add(_build_turn(board, regroup, groups, enemies))

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
            dst_a = _step_toward(board, pos, ha, ca, sources, enemies)
            dst_b = _step_toward(board, pos, hb, cnt - ca, sources | {dst_a}, enemies)
            if dst_a is None or dst_b is None:
                continue
            split = [(pos[0], pos[1], ca, dst_a[0], dst_a[1]),
                     (pos[0], pos[1], cnt - ca, dst_b[0], dst_b[1])]
            others = {p: g for p, g in default.items() if p != pos}
            rest = _build_turn(board, others,
                               [(p, c) for p, c in groups if p != pos], enemies)
            rest = [m for m in rest if (m[3], m[4]) != pos]  # can't move into the split cell
            add(split + rest)

    if not plans:                                # fallback: any legal move
        pos, cnt = groups[0]
        for n in board.get_neighbors(pos):
            if n not in sources:
                plans.append([(pos[0], pos[1], cnt, n[0], n[1])])
                break
    return plans[:max_plans]


def rollout_plan(board: BoardState, species: Species, epsilon: float = 0.15) -> List[Move]:
    """Moves used in the imaginary games: greedy, with a bit of randomness."""
    groups, enemies, humans = split_board(board, species)
    if not groups:
        return []
    choices = {}
    for pos, cnt in groups:
        friends = [(p, c) for p, c in groups if p != pos]
        goals = _group_goals(board, pos, cnt, friends, enemies, humans)
        if len(goals) > 1 and random.random() < epsilon:
            choices[pos] = goals[1][1]           # sometimes take the 2nd best
        else:
            choices[pos] = goals[0][1]
    return _build_turn(board, choices, groups, enemies)


# ═══════════════════════════════════════════════════════════════
#  MCTS OVER WHOLE-TURN PLANS  (runs inside each subprocess)
# ═══════════════════════════════════════════════════════════════
class MCTSNode:
    __slots__ = ('moves', 'mover', 'parent', 'children', 'untried', 'visits', 'value')

    def __init__(self, moves: Optional[List[Move]], mover: Optional[Species],
                 parent: Optional['MCTSNode']):
        self.moves = moves                       # the plan played to get here
        self.mover = mover                        # who played it
        self.parent = parent
        self.children: List['MCTSNode'] = []
        self.untried: Optional[List[List[Move]]] = None   # filled on first visit
        self.visits = 0
        self.value = 0.0                          # sum of scores, from our side


def _select_child(node: MCTSNode, us: Species) -> MCTSNode:
    # UCB1 = avg score + c * sqrt(ln(N) / n)
    log_n = math.log(node.visits)
    best, best_ucb = None, -1.0
    for child in node.children:
        avg = child.value / child.visits
        if child.mover != us:
            avg = 1.0 - avg                       # opponent picks what's best for them
        ucb = avg + UCT_C * math.sqrt(log_n / child.visits)
        if ucb > best_ucb:
            best, best_ucb = child, ucb
    return best


def _rollout(board: BoardState, to_move: Species, us: Species) -> float:
    # short imaginary game with real dice, then score it
    for _ in range(ROLLOUT_PLIES):
        if board.is_game_over()[0]:
            break
        moves = rollout_plan(board, to_move)
        if not moves:
            break
        board = board.apply_moves(moves, to_move, deterministic=False)
        to_move = _opp(to_move)
    return evaluate(board, us, to_move)


def _run_iteration(root: MCTSNode, root_board: BoardState, us: Species):
    node, board, to_move = root, root_board, us

    # 1. selection
    while node.untried is not None and not node.untried and node.children:
        child = _select_child(node, us)
        # boards aren't stored, moves are replayed with new dice each time,
        # so a stored plan can become illegal (group smaller or dead)
        valid, _ = board.validate_moves(child.moves, to_move)
        if not valid:
            break
        board = board.apply_moves(child.moves, to_move, deterministic=False)
        node, to_move = child, _opp(to_move)

    # 2. expansion
    if not board.is_game_over()[0]:
        if node.untried is None:
            node.untried = generate_plans(board, to_move)
            random.shuffle(node.untried)
        while node.untried:
            moves = node.untried.pop()
            if board.validate_moves(moves, to_move)[0]:
                child = MCTSNode(moves, to_move, node)
                node.children.append(child)
                board = board.apply_moves(moves, to_move, deterministic=False)
                node, to_move = child, _opp(to_move)
                break

    # 3. simulation
    score = _rollout(board, to_move, us)

    # 4. backpropagation
    while node is not None:
        node.visits += 1
        node.value += score
        node = node.parent


def mcts_search(snapshot: StateSnapshot, time_limit: float, seed: int) -> dict:
    """TOP-LEVEL function — must be top-level for multiprocessing pickle."""
    random.seed(seed)
    proj = os.path.dirname(os.path.abspath(__file__))
    if proj not in sys.path:
        sys.path.insert(0, proj)

    board = snapshot.to_board_state()
    us = snapshot.our_species
    plans = [p for p in generate_plans(board, us) if board.validate_moves(p, us)[0]]
    if not plans:
        return {'best_move': None, 'move_visits': {}, 'moves': {}, 'iterations': 0}
    if len(plans) == 1:
        k = _move_key(plans[0])
        return {'best_move': plans[0], 'move_visits': {k: 1}, 'moves': {k: plans[0]}, 'iterations': 0}

    root = MCTSNode(None, None, None)
    root.untried = list(plans)
    random.shuffle(root.untried)

    end_time = time.time() + time_limit
    iterations = 0
    while time.time() < end_time:
        _run_iteration(root, board, us)
        iterations += 1

    if not root.children:
        return {'best_move': plans[0], 'move_visits': {}, 'moves': {}, 'iterations': iterations}

    move_visits, move_reg = {}, {}
    for c in root.children:
        k = _move_key(c.moves)
        move_visits[k] = move_visits.get(k, 0) + c.visits
        move_reg[k] = c.moves
    best_key = max(move_visits, key=move_visits.get)
    return {'best_move': move_reg[best_key], 'move_visits': move_visits,
            'moves': move_reg, 'iterations': iterations}


# ═══════════════════════════════════════════════════════════════
#  ROOT-PARALLEL MCTS  (orchestrates all cores)
# ═══════════════════════════════════════════════════════════════
def _warmup(_):
    time.sleep(0.05)
    return 0


def parallel_mcts(snapshot: StateSnapshot, time_limit: float, num_cores: int, executor):
    """Sums root-plan visit counts across independent trees, returns the top plan."""
    futures = {executor.submit(mcts_search, snapshot, time_limit, i): i
               for i in range(num_cores)}
    results = []
    for f in as_completed(futures):
        try:
            results.append(f.result())
        except BrokenProcessPool:
            raise
        except Exception as e:
            print(f"[PMCTS] Worker {futures[f]} error: {e}")

    if not results:
        return None, None

    combined, move_reg = {}, {}
    for r in results:
        move_reg.update(r.get('moves', {}))
        for k, v in r.get('move_visits', {}).items():
            combined[k] = combined.get(k, 0) + v
    total_iters = sum(r.get('iterations', 0) for r in results)

    if not combined:
        for r in results:
            if r.get('best_move'):
                return r['best_move'], {'sims': total_iters, 'top': []}
        return None, None

    ranked = sorted(combined, key=combined.get, reverse=True)[:5]
    best_key = ranked[0]
    print(f"[PMCTS] {num_cores} cores | {total_iters:,} simulations | "
          f"top plan votes: {combined[best_key]:,}")
    info = {'sims': total_iters, 'top': [(move_reg[k], combined[k]) for k in ranked]}
    return move_reg.get(best_key), info


# ═══════════════════════════════════════════════════════════════
#  AI AGENT  (entry point called by main.py)
# ═══════════════════════════════════════════════════════════════
class AIAgent:
    def __init__(self, name: str = "Harsha"):
        self.name = name
        self.num_cores = NUM_CORES
        self.last_decision = {}
        self._pool = None
        self._start_pool()
        print(f"[AIAgent] '{name}' | Cores: {self.num_cores} | Budget: {TIME_LIMIT}s/turn")

    def _start_pool(self):
        # Persistent workers: no process start-up cost during the game
        if self._pool is not None:
            self._pool.shutdown(wait=False)
        self._pool = ProcessPoolExecutor(max_workers=self.num_cores)
        list(self._pool.map(_warmup, range(self.num_cores)))

    def _search(self, snapshot: StateSnapshot):
        try:
            return parallel_mcts(snapshot, TIME_LIMIT, self.num_cores, self._pool)
        except BrokenProcessPool:
            self._start_pool()
            return None, None

    @staticmethod
    def _fallback(board: BoardState, species: Species) -> List[Move]:
        """Rule 1 needs a move even when the search comes up empty."""
        groups, enemies, humans = split_board(board, species)
        if not groups:
            return []
        pos, cnt = max(groups, key=lambda g: g[1])
        targets = [p for p, _ in humans] or [p for p, _ in enemies]
        sources = {p for p, _ in groups}
        goal = min(targets, key=lambda t: chebyshev_dist(pos, t)) if targets else pos
        dst = _step_toward(board, pos, goal, cnt, sources, enemies)
        if dst is None:
            for n in board.get_neighbors(pos):
                if n not in sources:
                    return [(pos[0], pos[1], cnt, n[0], n[1])]
            return []
        return [(pos[0], pos[1], cnt, dst[0], dst[1])]

    def compute_moves(self, state_or_board, species: Optional[Species] = None) -> List[Move]:
        """
        Dual interface:
        - From main.py: compute_moves(state: GameState)
        - From the arena: compute_moves(board: BoardState, species: Species)
        """
        if isinstance(state_or_board, BoardState):
            board, sp = state_or_board, species
        else:
            st = state_or_board
            sp = st.our_species
            if sp is None or not st.get_our_groups():
                return []
            board = BoardState(st.rows, st.cols)
            board.grid = {pos: (c.humans, c.vampires, c.werewolves) for pos, c in st.board.items()}

        if sp is None or not split_board(board, sp)[0]:
            return []

        snapshot = StateSnapshot(board.rows, board.cols, dict(board.grid), sp,
                                 board.turn_count, board.max_turns)
        t0 = time.time()
        best, info = self._search(snapshot)
        elapsed = time.time() - t0

        if not best:
            best = self._fallback(board, sp)
            self.last_decision = {'source': 'fallback', 'move': best}
            print(f"[AIAgent] MCTS empty ({elapsed:.2f}s) -> fallback")
            return best

        self.last_decision = {'source': 'mcts', 'move': best, 'info': info}
        print(f"[AIAgent] Decision: {elapsed:.2f}s -> {len(best)} group move(s)")
        if DEBUG and info:
            for mv, visits in info.get('top', []):
                tag = "  <-- chosen" if mv == best else ""
                print(f"[DEBUG] votes={visits:<6} {mv}{tag}")
        return best

