"""
Game Engine for Vampires VS Werewolves
Faithfully implements the rules specified in Projectv10.pdf:
- n x m grid (0-indexed, (0,0) top-left)
- 8-directional movement (Chebyshev / King's move)
- Rules 1 to 6
- Deterministic combat:
  * Humans: E1 >= E2 -> win and convert (all humans converted, no losses)
  * Enemies: E1 >= 1.5 * E2 -> win, enemies wiped out, attackers survive
             E2 >= 1.5 * E1 -> loss, attackers wiped out
- Probabilistic combat (when neither 1.5x holds):
  * E1 == E2: P = 0.5
  * E1 < E2:  P = E1 / (2 * E2)
  * E1 > E2:  P = E1 / E2 - 0.5
  * If attackers win: each attacker has prob P to survive. Humans have prob P to convert.
  * If attackers lose: each defender has prob 1-P to survive.
- Turn limit and victory conditions
"""

import math
import random
from copy import deepcopy
from typing import Dict, List, Tuple, Optional, Set
from game_state import Species, Cell

# Directions (8 adjacent neighbors)
DIRECTIONS = [(-1, -1), (-1, 0), (-1, 1),
              (0, -1),           (0, 1),
              (1, -1),  (1, 0),  (1, 1)]

def chebyshev_dist(p1: Tuple[int, int], p2: Tuple[int, int]) -> int:
    return max(abs(p1[0] - p2[0]), abs(p1[1] - p2[1]))

def manhattan_dist(p1: Tuple[int, int], p2: Tuple[int, int]) -> int:
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

def combat_win_probability(e1: int, e2: int) -> float:
    """
    Computes battle win probability P for attacker E1 against defender E2
    according to Projectv10.pdf page 4.
    """
    if e1 <= 0:
        return 0.0
    if e2 <= 0:
        return 1.0
    if e1 == e2:
        return 0.5
    if e1 < e2:
        return float(e1) / (2.0 * e2)
    else:
        # e1 > e2
        return (float(e1) / float(e2)) - 0.5

class BoardState:
    """
    Lightweight, fast board state representation for game search and simulation.
    """
    __slots__ = ('rows', 'cols', 'grid', 'turn_count', 'max_turns')

    def __init__(self, rows: int, cols: int, max_turns: int = 200):
        self.rows = rows
        self.cols = cols
        self.turn_count = 0
        self.max_turns = max_turns
        # dict: (x, y) -> (humans, vampires, werewolves)
        self.grid: Dict[Tuple[int, int], Tuple[int, int, int]] = {}

    def clone(self) -> 'BoardState':
        b = BoardState(self.rows, self.cols, self.max_turns)
        b.turn_count = self.turn_count
        b.grid = dict(self.grid)
        return b

    def get_cell(self, pos: Tuple[int, int]) -> Tuple[int, int, int]:
        return self.grid.get(pos, (0, 0, 0))

    def set_cell(self, pos: Tuple[int, int], hum: int, vmp: int, wrw: int):
        if hum == 0 and vmp == 0 and wrw == 0:
            self.grid.pop(pos, None)
        else:
            self.grid[pos] = (hum, vmp, wrw)

    def get_species_groups(self, species: Species) -> List[Tuple[Tuple[int, int], int]]:
        groups = []
        is_vampire = (species == Species.VAMPIRE)
        for pos, (h, v, w) in self.grid.items():
            cnt = v if is_vampire else w
            if cnt > 0:
                groups.append((pos, cnt))
        return groups

    def get_species_total(self, species: Species) -> int:
        is_vampire = (species == Species.VAMPIRE)
        tot = 0
        for (h, v, w) in self.grid.values():
            tot += (v if is_vampire else w)
        return tot

    def get_humans(self) -> List[Tuple[Tuple[int, int], int]]:
        humans = []
        for pos, (h, v, w) in self.grid.items():
            if h > 0:
                humans.append((pos, h))
        return humans

    def get_neighbors(self, pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        x, y = pos
        res = []
        for dx, dy in DIRECTIONS:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.cols and 0 <= ny < self.rows:
                res.append((nx, ny))
        return res

    def is_game_over(self) -> Tuple[bool, Optional[Species]]:
        """
        Returns (is_over, winner).
        Winner is None if draw or ongoing.
        """
        v_total = self.get_species_total(Species.VAMPIRE)
        w_total = self.get_species_total(Species.WEREWOLF)

        if v_total == 0 and w_total == 0:
            return True, None
        if v_total == 0:
            return True, Species.WEREWOLF
        if w_total == 0:
            return True, Species.VAMPIRE
        if self.turn_count >= self.max_turns:
            if v_total > w_total:
                return True, Species.VAMPIRE
            elif w_total > v_total:
                return True, Species.WEREWOLF
            else:
                return True, None
        return False, None

    def validate_moves(self, moves: List[Tuple[int, int, int, int, int]], species: Species) -> Tuple[bool, str]:
        """
        Validates moves according to Rules 1 to 6 in Projectv10.pdf:
        Rule 1: At least one movement by ply
        Rule 2: You can only move your species groups
        Rule 3: You need to have enough creatures on a cell to perform all the moves from this cell
        Rule 4: You can move in 8 directions (unless on borders)
        Rule 5: In the same ply, a cell cannot be target and source of moves
        Rule 6: You have to move at least one creature
        """
        if not moves:
            return False, "Rule 1 violated: At least one movement per ply required."

        is_vampire = (species == Species.VAMPIRE)
        sources: Set[Tuple[int, int]] = set()
        targets: Set[Tuple[int, int]] = set()
        outgoing_counts: Dict[Tuple[int, int], int] = {}

        for x1, y1, count, x2, y2 in moves:
            # Rule 6
            if count <= 0:
                return False, f"Rule 6 violated: Must move at least 1 creature (got {count})."

            src = (x1, y1)
            dst = (x2, y2)

            # Bounds check
            if not (0 <= x1 < self.cols and 0 <= y1 < self.rows):
                return False, f"Source out of bounds: {src}"
            if not (0 <= x2 < self.cols and 0 <= y2 < self.rows):
                return False, f"Rule 4 violated: Target out of bounds: {dst}"

            # Rule 4: 8 directions, exactly 1 step away
            if chebyshev_dist(src, dst) != 1:
                return False, f"Rule 4 violated: Move from {src} to {dst} is not an adjacent 8-dir step."

            sources.add(src)
            targets.add(dst)
            outgoing_counts[src] = outgoing_counts.get(src, 0) + count

        # Rule 5: In the same ply, a cell cannot be target and source of moves
        overlap = sources.intersection(targets)
        if overlap:
            return False, f"Rule 5 violated: Cell {overlap} is both source and target in same ply."

        # Rule 2 & Rule 3: Check creature ownership and counts
        for src, total_moved in outgoing_counts.items():
            cell = self.get_cell(src)
            available = cell[1] if is_vampire else cell[2]
            if available <= 0:
                return False, f"Rule 2 violated: No creatures of species {species.value} at {src}."
            if total_moved > available:
                return False, f"Rule 3 violated: Attempted to move {total_moved} from {src}, but only {available} present."

        return True, "Valid"

    def apply_moves(self, moves: List[Tuple[int, int, int, int, int]], species: Species, deterministic: bool = True) -> 'BoardState':
        """
        Applies a validated set of moves and resolves combats.
        If deterministic is True, resolves probabilistic combats using Expected Value (EV).
        If deterministic is False, uses random dice rolls per the PDF formula.
        """
        new_state = self.clone()
        new_state.turn_count += 1
        is_vampire = (species == Species.VAMPIRE)

        # 1. Deduct moving creatures from source cells
        # Dict dst -> arriving friendly creatures
        arriving: Dict[Tuple[int, int], int] = {}

        for x1, y1, count, x2, y2 in moves:
            src = (x1, y1)
            dst = (x2, y2)
            sh, sv, sw = new_state.get_cell(src)
            if is_vampire:
                new_state.set_cell(src, sh, sv - count, sw)
            else:
                new_state.set_cell(src, sh, sv, sw - count)
            arriving[dst] = arriving.get(dst, 0) + count

        # 2. Resolve arrivals at destinations
        for dst, attack_cnt in arriving.items():
            th, tv, tw = new_state.get_cell(dst)
            friend_cnt = tv if is_vampire else tw
            enemy_cnt = tw if is_vampire else tv

            # Case A: Friendly cell or empty cell
            if th == 0 and enemy_cnt == 0:
                tot_friend = friend_cnt + attack_cnt
                if is_vampire:
                    new_state.set_cell(dst, 0, tot_friend, 0)
                else:
                    new_state.set_cell(dst, 0, 0, tot_friend)
                continue

            # Case B: Human cell (no enemy monsters present)
            if th > 0 and enemy_cnt == 0:
                e1 = attack_cnt
                e2 = th
                if e1 >= e2:
                    # Deterministic conversion: E1 >= E2
                    survivors = e1 + e2
                    if is_vampire:
                        new_state.set_cell(dst, 0, survivors, 0)
                    else:
                        new_state.set_cell(dst, 0, 0, survivors)
                else:
                    # Random battle with humans: E1 < E2
                    p = combat_win_probability(e1, e2)
                    if deterministic:
                        # Expected value approximation
                        # If win (prob p): expected living = p * (e1 + e2)
                        # If lose (prob 1-p): expected remaining humans = (1 - p) * e2
                        # In expected minimax, we credit expected surviving units if p >= 0.5, else humans survive
                        if p >= 0.5:
                            exp_units = max(1, round(p * (e1 + e2)))
                            if is_vampire:
                                new_state.set_cell(dst, 0, exp_units, 0)
                            else:
                                new_state.set_cell(dst, 0, 0, exp_units)
                        else:
                            exp_humans = max(1, round((1.0 - p) * e2))
                            new_state.set_cell(dst, exp_humans, 0, 0)
                    else:
                        # Simulation roll
                        win = (random.random() < p)
                        if win:
                            # Each attacker and human survives with prob p
                            surv_att = sum(1 for _ in range(e1) if random.random() < p)
                            surv_hum = sum(1 for _ in range(e2) if random.random() < p)
                            total_conv = max(1, surv_att + surv_hum)
                            if is_vampire:
                                new_state.set_cell(dst, 0, total_conv, 0)
                            else:
                                new_state.set_cell(dst, 0, 0, total_conv)
                        else:
                            surv_hum = sum(1 for _ in range(e2) if random.random() < (1.0 - p))
                            new_state.set_cell(dst, max(1, surv_hum), 0, 0)
                continue

            # Case C: Enemy monster cell (enemy_cnt > 0)
            if enemy_cnt > 0:
                e1 = attack_cnt
                e2 = enemy_cnt

                # Rule: E1 >= 1.5 * E2 -> deterministic kill, attackers survive
                if e1 >= 1.5 * e2:
                    if is_vampire:
                        new_state.set_cell(dst, 0, e1, 0)
                    else:
                        new_state.set_cell(dst, 0, 0, e1)
                # Rule: E2 >= 1.5 * E1 -> deterministic defense, attackers killed
                elif e2 >= 1.5 * e1:
                    if is_vampire:
                        new_state.set_cell(dst, 0, 0, e2)
                    else:
                        new_state.set_cell(dst, 0, e2, 0)
                else:
                    # Probabilistic battle between monsters (neither has 1.5x advantage)
                    p = combat_win_probability(e1, e2)
                    if deterministic:
                        # True Expected-Value resolution for Minimax lookahead:
                        # If P >= 0.5, attacker has advantage and wins in expectation with P * E1 survivors.
                        # If P < 0.5, defender holds the cell with (1 - P) * E2 survivors.
                        if p >= 0.5:
                            exp_att = max(1, round(p * e1))
                            if is_vampire:
                                new_state.set_cell(dst, 0, exp_att, 0)
                            else:
                                new_state.set_cell(dst, 0, 0, exp_att)
                        else:
                            exp_def = max(1, round((1.0 - p) * e2))
                            if is_vampire:
                                new_state.set_cell(dst, 0, 0, exp_def)
                            else:
                                new_state.set_cell(dst, 0, exp_def, 0)
                    else:
                        win = (random.random() < p)
                        if win:
                            surv = sum(1 for _ in range(e1) if random.random() < p)
                            surv = max(1, surv)
                            if is_vampire:
                                new_state.set_cell(dst, 0, surv, 0)
                            else:
                                new_state.set_cell(dst, 0, 0, surv)
                        else:
                            surv = sum(1 for _ in range(e2) if random.random() < (1.0 - p))
                            surv = max(1, surv)
                            if is_vampire:
                                new_state.set_cell(dst, 0, 0, surv)
                            else:
                                new_state.set_cell(dst, 0, surv, 0)

        return new_state
