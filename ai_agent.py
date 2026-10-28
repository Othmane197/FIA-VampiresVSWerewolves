"""
Parallel MCTS AI Agent — Vampires VS Werewolves
FIA - CentraleSupélec / Centrale Casablanca

Algorithm: Root-Parallelized Monte Carlo Tree Search (MCTS)
─────────────────────────────────────────────────────────────
• Each CPU core runs an INDEPENDENT MCTS tree simultaneously.
• All trees start from the same board state (root parallelization).
• At time-up, results are aggregated by vote (summed visit counts).
• Winner = move with the most visits across all cores.

Why faster than regular MCTS?
  1 core  x 1.75s = ~8,000  simulations
  8 cores x 1.75s = ~64,000 simulations  (same clock time, 8x deeper)
─────────────────────────────────────────────────────────────
"""

import os
import sys
import time
import math
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Tuple, Optional, Dict

from game_state import GameState, Species
from game_engine import BoardState

# ═══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════
NUM_CORES         = max(1, (os.cpu_count() or 2) - 1)  # leave 1 core for OS
TIME_LIMIT        = 1.60   # seconds (0.25s safety buffer from 2.0s rule)
UCT_C             = 1.414  # exploration constant sqrt(2)
MAX_ROLLOUT_DEPTH = 20     # max playout steps per simulation
MAX_CHILDREN      = 40     # max children expanded per node

DIRECTIONS = [(-1,-1), (-1,0), (-1,1),
              ( 0,-1),          (0,1),
              ( 1,-1),  (1,0), (1,1)]


# ═══════════════════════════════════════════════════════════════
#  STATE SNAPSHOT  — picklable for subprocess transfer
# ═══════════════════════════════════════════════════════════════
class StateSnapshot:
    """
    Lightweight, fully picklable game state snapshot.
    multiprocessing uses pickle to send data to worker processes,
    so the live GameState object must be converted to this first.
    """
    __slots__ = ('rows', 'cols', 'grid', 'our_species', 'turn_count', 'max_turns')

    def __init__(self, rows, cols, grid, our_species, turn_count=0, max_turns=200):
        self.rows        = rows
        self.cols        = cols
        self.grid        = grid         # {(x,y): (humans, vampires, werewolves)}
        self.our_species = our_species
        self.turn_count  = turn_count
        self.max_turns   = max_turns

    def to_board_state(self):
        bs            = BoardState(self.rows, self.cols, self.max_turns)
        bs.grid       = dict(self.grid)
        bs.turn_count = self.turn_count
        return bs


def game_state_to_snapshot(state):
    grid = {pos: (cell.humans, cell.vampires, cell.werewolves)
            for pos, cell in state.board.items()}
    return StateSnapshot(state.rows, state.cols, grid, state.our_species)


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════
def _opposite(s):
    return Species.WEREWOLF if s == Species.VAMPIRE else Species.VAMPIRE


def _get_groups(board, species):
    is_vamp = (species == Species.VAMPIRE)
    return [(pos, (v if is_vamp else w))
            for pos, (h, v, w) in board.grid.items()
            if (v if is_vamp else w) > 0]


def _move_to_key(move):
    if not move:
        return ""
    return str(sorted(move))


# ═══════════════════════════════════════════════════════════════
#  MOVE SAMPLER  — one combined move per call
# ═══════════════════════════════════════════════════════════════
def sample_combined_move(board, species, bias_smart=False):
    """
    Returns ONE combined move set: one (sx, sy, count, dx, dy) per group.

    bias_smart=False  →  random neighbor   (variety for tree expansion)
    bias_smart=True   →  utility-AI pick   (smart rollouts)
    """
    groups = _get_groups(board, species)
    if not groups:
        return None

    is_vamp    = (species == Species.VAMPIRE)
    sources    = {pos for pos, _ in groups}
    chosen_dst = set()
    moves      = []

    if bias_smart:
        humans  = [(pos, h) for pos, (h, v, w) in board.grid.items() if h > 0]
        enemies = [(pos, (w if is_vamp else v))
                   for pos, (h, v, w) in board.grid.items()
                   if (w if is_vamp else v) > 0]
        targets = humans or enemies

    for (sx, sy), cnt in groups:
        valid = []
        for dx, dy in DIRECTIONS:
            nx, ny = sx + dx, sy + dy
            if 0 <= nx < board.cols and 0 <= ny < board.rows:
                dst = (nx, ny)
                # Rule 5: Destination cannot be a source cell in the same ply
                if dst not in sources:
                    valid.append(dst)

        if not valid:
            # Skip this group if it cannot move without violating Rule 5
            continue

        if bias_smart and targets:
            def _score(n):
                nh, nv, nw = board.grid.get(n, (0, 0, 0))
                n_enemy = nw if is_vamp else nv
                s = 0
                if nh > 0:
                    if cnt >= nh:
                        s += 1000 + nh       # Guaranteed human conversion
                    else:
                        s -= 500             # Avoid disadvantageous human battle (P < 0.5)

                if n_enemy > 0:
                    if cnt >= 1.5 * n_enemy:
                        s += 1200 + n_enemy  # Guaranteed wipeout of enemy
                    elif n_enemy >= 1.5 * cnt:
                        s -= 2000            # Suicidal: guaranteed loss
                    else:
                        p = cnt / (2.0 * n_enemy) if cnt < n_enemy else (cnt / float(n_enemy) - 0.5)
                        s += int((p - 0.5) * 600)

                s -= min(max(abs(n[0]-t[0][0]), abs(n[1]-t[0][1]))
                         for t in targets) * 3
                return s
            best = max(valid, key=_score)
        else:
            best = random.choice(valid)

        moves.append((sx, sy, cnt, best[0], best[1]))

    return moves if moves else None


# ═══════════════════════════════════════════════════════════════
#  HEURISTIC EVALUATION
# ═══════════════════════════════════════════════════════════════
def evaluate(board, our_species):
    """Score in [-10000, +10000]. Positive = good for us."""
    is_vamp = (our_species == Species.VAMPIRE)
    our_total = enemy_total = 0
    our_pos = []
    enemy_pos = []
    human_pos = []

    for pos, (h, v, w) in board.grid.items():
        oc = v if is_vamp else w
        ec = w if is_vamp else v
        if oc > 0: our_total += oc;    our_pos.append((pos, oc))
        if ec > 0: enemy_total += ec;  enemy_pos.append((pos, ec))
        if h  > 0: human_pos.append((pos, h))

    if our_total   == 0: return -10000.0
    if enemy_total == 0: return  10000.0

    score = float(our_total - enemy_total) * 10.0

    # Human proximity bonus
    for (ox, oy), _ in our_pos:
        for (hx, hy), hc in human_pos:
            dist = max(abs(ox - hx), abs(oy - hy))
            score += hc * (4.0 / (dist + 1))

    # Danger penalty
    for (ox, oy), oc in our_pos:
        for (ex, ey), ec in enemy_pos:
            dist = max(abs(ox - ex), abs(oy - ey))
            if dist <= 2 and ec >= 1.5 * oc:
                score -= 60.0

    return score


# ═══════════════════════════════════════════════════════════════
#  MCTS NODE
# ═══════════════════════════════════════════════════════════════
class MCTSNode:
    __slots__ = ('parent', 'move', 'children', 'wins', 'visits',
                 'board', 'turn_species', 'num_expanded')

    def __init__(self, board, turn_species, parent=None, move=None):
        self.parent       = parent
        self.move         = move
        self.children     = []
        self.wins         = 0.0
        self.visits       = 0
        self.board        = board
        self.turn_species = turn_species
        self.num_expanded = 0

    def uct_score(self):
        if self.visits == 0:
            return float('inf')
        return (self.wins / self.visits +
                UCT_C * math.sqrt(math.log(self.parent.visits) / self.visits))

    def best_uct_child(self):
        return max(self.children, key=lambda c: c.uct_score())

    def most_visited_child(self):
        return max(self.children, key=lambda c: c.visits)

    def can_expand(self):
        over, _ = self.board.is_game_over()
        return (not over) and (self.num_expanded < MAX_CHILDREN)


# ═══════════════════════════════════════════════════════════════
#  MCTS PHASES
# ═══════════════════════════════════════════════════════════════
def _select(root):
    node = root
    while node.children and not node.can_expand():
        over, _ = node.board.is_game_over()
        if over:
            break
        node = node.best_uct_child()
    return node


def _expand(node):
    over, _ = node.board.is_game_over()
    if over:
        return node
    move = sample_combined_move(node.board, node.turn_species, bias_smart=False)
    if not move:
        return node
    try:
        new_board = node.board.apply_moves(move, node.turn_species, deterministic=True)
    except Exception:
        return node
    child = MCTSNode(new_board, _opposite(node.turn_species), parent=node, move=move)
    node.children.append(child)
    node.num_expanded += 1
    return child


def _rollout(node, our_species):
    board   = node.board
    species = node.turn_species

    for _ in range(MAX_ROLLOUT_DEPTH):
        over, winner = board.is_game_over()
        if over:
            if winner == our_species: return 1.0
            if winner is None:        return 0.5
            return 0.0
        move = sample_combined_move(board, species, bias_smart=True)
        if not move:
            break
        try:
            board = board.apply_moves(move, species, deterministic=False)
        except Exception:
            break
        species = _opposite(species)

    score = evaluate(board, our_species)
    if   score >  100: return 1.0
    elif score < -100: return 0.0
    else:              return 0.5


def _backpropagate(node, result, our_species):
    while node is not None:
        node.visits += 1
        node.wins   += result if node.turn_species == our_species else (1.0 - result)
        node = node.parent


# ═══════════════════════════════════════════════════════════════
#  SINGLE-CORE MCTS  (runs inside each subprocess)
# ═══════════════════════════════════════════════════════════════
def mcts_search(snapshot, time_limit, seed):
    """
    TOP-LEVEL function — must be top-level for multiprocessing pickle.
    Runs one complete MCTS tree and returns visit statistics.
    """
    random.seed(seed)

    # Make sure project modules are importable inside the subprocess
    proj = os.path.dirname(os.path.abspath(__file__))
    if proj not in sys.path:
        sys.path.insert(0, proj)

    board       = snapshot.to_board_state()
    our_species = snapshot.our_species
    root        = MCTSNode(board, our_species)
    end_time    = time.time() + time_limit
    iters       = 0

    while time.time() < end_time:
        leaf   = _select(root)
        child  = _expand(leaf)
        result = _rollout(child, our_species)
        _backpropagate(child, result, our_species)
        iters += 1

    if not root.children:
        return {'best_move': None, 'move_visits': {}, 'best_key': '', 'iterations': iters}

    best_child = root.most_visited_child()
    best_move  = best_child.move
    best_key   = _move_to_key(best_move)

    move_visits = {}
    for c in root.children:
        k = _move_to_key(c.move)
        move_visits[k] = move_visits.get(k, 0) + c.visits

    return {'best_move': best_move, 'move_visits': move_visits,
            'best_key': best_key, 'iterations': iters}


# ═══════════════════════════════════════════════════════════════
#  ROOT-PARALLEL MCTS  (orchestrates all cores)
# ═══════════════════════════════════════════════════════════════
def parallel_mcts(snapshot, time_limit, num_cores):
    """
    Launches `num_cores` independent MCTS trees simultaneously.

        Core 1 → MCTS tree (seed=0) → best_move + visit_counts
        Core 2 → MCTS tree (seed=1) → best_move + visit_counts  ─→ aggregate → FINAL
        Core 3 → MCTS tree (seed=2) → best_move + visit_counts
        ...

    Aggregate = sum visit counts across all trees, pick highest.
    """
    results = []
    with ProcessPoolExecutor(max_workers=num_cores) as executor:
        futures = {executor.submit(mcts_search, snapshot, time_limit, i): i
                   for i in range(num_cores)}
        for f in as_completed(futures):
            try:
                results.append(f.result())
            except Exception as e:
                print(f"[PMCTS] Worker {futures[f]} error: {e}")

    if not results:
        return None

    combined   = {}
    move_reg   = {}

    for r in results:
        bk = r.get('best_key', '')
        bm = r.get('best_move')
        if bm and bk and bk not in move_reg:
            move_reg[bk] = bm
        for key, visits in r.get('move_visits', {}).items():
            combined[key] = combined.get(key, 0) + visits

    if not combined:
        for r in results:
            if r.get('best_move'):
                return r['best_move']
        return None

    best_key    = max(combined, key=combined.get)
    total_iters = sum(r.get('iterations', 0) for r in results)
    print(f"[PMCTS] {num_cores} cores | {total_iters:,} simulations | "
          f"Top move visits: {combined[best_key]:,}")

    return move_reg.get(best_key)


# ═══════════════════════════════════════════════════════════════
#  AI AGENT  (entry point called by main.py)
# ═══════════════════════════════════════════════════════════════
class AIAgent:
    def __init__(self, name: str = "ParallelMCTS"):
        self.name      = name
        self.num_cores = NUM_CORES
        print(f"[AIAgent] '{name}' | Cores: {self.num_cores} | Budget: {TIME_LIMIT}s/turn")

    def compute_moves(self, state: GameState) -> List[Tuple[int,int,int,int,int]]:
        """Called every turn by main.py. Must return within 2.0 seconds."""
        if not state.get_our_groups():
            return []
        if state.our_species is None:
            return self._greedy_fallback(state)

        snapshot  = game_state_to_snapshot(state)
        t0        = time.time()
        best_move = parallel_mcts(snapshot, TIME_LIMIT, self.num_cores)
        elapsed   = time.time() - t0

        if best_move:
            print(f"[AIAgent] Decision: {elapsed:.2f}s → {len(best_move)} group moves")
            return best_move

        print(f"[AIAgent] MCTS empty ({elapsed:.2f}s) → greedy fallback")
        return self._greedy_fallback(state)

    def _greedy_fallback(self, state: GameState) -> List[Tuple[int,int,int,int,int]]:
        """Simple greedy: move each group toward nearest human/enemy."""
        our_groups = state.get_our_groups()
        targets    = ([p for p, _ in state.get_human_groups()] or
                      [p for p, _ in state.get_enemy_groups()])
        sources    = {pos for pos, _ in our_groups}
        chosen_dst = set()
        moves      = []

        for (sx, sy), count in our_groups:
            neighbors = state.get_legal_adjacent_cells((sx, sy))
            # Rule 5: Destination cannot be a source cell in the same ply
            valid = [n for n in neighbors if n not in sources]
            if not valid:
                continue
            best = (min(valid, key=lambda n: min(state.chebyshev_dist(n, t) for t in targets))
                    if targets else random.choice(valid))
            moves.append((sx, sy, count, best[0], best[1]))

        return moves
