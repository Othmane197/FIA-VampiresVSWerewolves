"""
Apex Alpha-Beta Minimax Agent (CentraleSupélec FIA Project)
Author: Pair programming with Google Antigravity

Architecture:
- Iterative Deepening Alpha-Beta Search (IDS) with strict time budgeting (<1.7s per ply)
- Custom Transposition Table with fast 64-bit state hashing
- Strategic Move Ordering (Transposition best move -> 1.5x enemy kills -> safe human conversions -> Voronoi territory steps)
- Deep Tactical Evaluation Function:
  * Material Differential with 1.5x Domination Threshold
  * Smooth Potential Field Gradient to Highest-Value Human Settlements
  * 1-Step Lethal Danger Zone & Ambush Avoidance
  * Anti-Suicide & Risk-Averse Stochastic Combat Pruning
  * Concentrated Deathball Principle (No premature splintering)
  * Endgame Predator Pursuit (Relentless Hunt when Domination Achieved)
- Strict compliance with Tournament Rules 1 to 6
- 100% self-contained: No prohibited AI/graph/tree external libraries
"""

import time
import math
import random
import gc
from collections import deque
from typing import List, Tuple, Optional, Dict, Set
from game_state import Species
from game_engine import BoardState, DIRECTIONS, chebyshev_dist, manhattan_dist, combat_win_probability

# Evaluation Constants
W_MATERIAL = 2000.0
W_DOMINATION_BONUS = 60000.0   # Triggered when our total >= 1.5 * enemy total
W_HUMAN_PULL = 3000.0          # Potential gradient pulling towards safe humans
W_DANGER_LETHAL = -150000.0    # Stepping into enemy 1.5x strike radius
W_THREAT_KILL = 120000.0       # Direct 1.5x kill on enemy group
W_RANDOM_BATTLE_RISK = -25000.0# Gambling army on coin-flip battle
W_PURSUIT = 400.0              # Relentless hunting when dominant

class TranspositionEntry:
    __slots__ = ('depth', 'score', 'flag', 'best_move')
    def __init__(self, depth: int, score: float, flag: int, best_move: Optional[List[Tuple[int, int, int, int, int]]]):
        self.depth = depth
        self.score = score
        self.flag = flag
        self.best_move = best_move

class ApexAlphaBetaAgent:
    def __init__(self, name: str = "ApexAlphaBeta", max_time_seconds: float = 1.65,
                 enable_foraging_yield: bool = False,
                 enable_voronoi: bool = False,
                 enable_quiescence: bool = False):
        self.name = name
        self.max_time = max_time_seconds
        self.enable_foraging_yield = enable_foraging_yield
        self.enable_voronoi = enable_voronoi
        self.enable_quiescence = enable_quiescence
        self.transposition_table: Dict[int, TranspositionEntry] = {}
        self.nodes_searched = 0
        self.start_time = 0.0
        self.time_limit_exceeded = False

        # 64-bit Zobrist keys
        random.seed(42)
        self.zobrist_hum = {}
        self.zobrist_vmp = {}
        self.zobrist_wrw = {}

    def _get_zobrist_keys(self, pos: Tuple[int, int]) -> Tuple[int, int, int]:
        if pos not in self.zobrist_hum:
            self.zobrist_hum[pos] = random.getrandbits(64)
            self.zobrist_vmp[pos] = random.getrandbits(64)
            self.zobrist_wrw[pos] = random.getrandbits(64)
        return self.zobrist_hum[pos], self.zobrist_vmp[pos], self.zobrist_wrw[pos]

    @staticmethod
    def _straight_path(src: Tuple[int, int], dst: Tuple[int, int]) -> List[Tuple[int, int]]:
        """A legal king path, diagonal first, used only for conservative split safety."""
        x, y = src
        path = []
        while (x, y) != dst:
            x += (dst[0] > x) - (dst[0] < x)
            y += (dst[1] > y) - (dst[1] < y)
            path.append((x, y))
        return path

    def _shortest_safe_path(self, state, src, target, units, friendly_sources, enemy_groups):
        """Find a shortest route that the detachment can traverse without an unsafe fight."""
        if self.start_time and time.time() - self.start_time >= self.max_time * 0.9:
            return None
        enemy_at = dict(enemy_groups)
        parent = {src: None}
        queue = deque([src])
        while queue:
            if self.start_time and time.time() - self.start_time >= self.max_time * 0.9:
                return None
            pos = queue.popleft()
            if pos == target:
                break
            for nxt in state.get_neighbors(pos):
                if nxt in parent or (nxt in friendly_sources and nxt != src):
                    continue
                if enemy_at.get(nxt, 0):
                    continue
                humans, _, _ = state.get_cell(nxt)
                if humans > units:
                    continue
                parent[nxt] = pos
                queue.append(nxt)
        if target not in parent:
            return None
        path = []
        pos = target
        while pos != src:
            path.append(pos)
            pos = parent[pos]
        path.reverse()
        return path

    def _split_is_safe(self, path, detachment, target, human_count, enemies) -> bool:
        """Check the target race, route exposure, and post-conversion survival margin."""
        distance = len(path)
        if detachment < human_count or distance == 0:
            return False
        converted = detachment + human_count
        for enemy_pos, enemy_count in enemies:
            enemy_distance = chebyshev_dist(enemy_pos, target)
            if enemy_count >= human_count and enemy_distance < distance:
                return False
            if enemy_count >= detachment:
                for step, cell in enumerate(path[:-1], start=1):
                    if chebyshev_dist(enemy_pos, cell) <= step:
                        return False
                if enemy_distance <= distance and enemy_count >= converted:
                    return False
                if enemy_distance <= distance + 1 and enemy_count >= 1.5 * converted:
                    return False
        return True

    def _split_options_for_group(self, state, src, count, groups, enemies, human_groups):
        """Bounded candidate plans for one group's safe human detachments."""
        if count < 3 or not human_groups:
            return []
        enemy_groups = enemies
        friendly_sources = {pos for pos, _ in groups}
        reserve = max((enemy_count + 1 for enemy_pos, enemy_count in enemy_groups
                       if chebyshev_dist(src, enemy_pos) <= 6), default=0)
        available = count - reserve
        if available < 2:
            return []

        # Consider a small, geometry-independent set of promising targets to cap BFS work.
        ranked_targets = sorted(
            ((h / (chebyshev_dist(src, pos) + 1.0), pos, h)
             for pos, h in human_groups if h > 0 and h <= 255),
            reverse=True)
        target_options = []
        for _, target, humans in ranked_targets[:6]:
            if self.start_time and time.time() - self.start_time >= self.max_time * 0.9:
                break
            # Try the smallest guaranteed detachment first; add at most two safety units.
            for units in range(humans, min(humans + 2, available) + 1):
                if units + humans > 255:
                    continue
                path = self._shortest_safe_path(state, src, target, units, friendly_sources, enemy_groups)
                if not path or not self._split_is_safe(path, units, target, humans, enemy_groups):
                    continue
                first = path[0]
                if any(chebyshev_dist(ep, first) == 1 and ec >= units for ep, ec in enemy_groups):
                    continue
                # Diminishing distance value favors efficient harvest without map-size constants.
                value = humans / ((len(path) + 1.0) * units)
                target_options.append((value, target, units, first))
                break
        target_options.sort(key=lambda item: (-item[0], item[1]))
        target_options = target_options[:4]
        plans = []

        def add_combo(combo):
            moved = sum(option[2] for option in combo)
            if moved >= count or count - moved < reserve:
                return
            targets = {option[1] for option in combo}
            first_steps = [option[3] for option in combo]
            if len(targets) != len(combo) or len(set(first_steps)) != len(first_steps):
                return
            moves = [(src[0], src[1], option[2], option[3][0], option[3][1])
                     for option in combo]
            plans.append((sum(option[0] for option in combo), moves))

        for option in target_options:
            add_combo([option])
        pairs = []
        for i, first in enumerate(target_options):
            for second in target_options[i + 1:]:
                pairs.append((first[0] + second[0], first, second))
        pairs.sort(key=lambda item: -item[0])
        for _, first, second in pairs[:3]:
            add_combo([first, second])
        plans.sort(key=lambda item: -item[0])
        return plans[:5]

    @staticmethod
    def _encode_group_move(option):
        src, count, dst = option
        return (src[0], src[1], count, dst[0], dst[1])

    def _append_split_plans(self, state, species, groups, enemies, human_groups,
                            group_options, candidates, limit=10):
        """Add bounded split plans for multiple groups, including coordinated detachments."""
        if not human_groups or not groups:
            return
        split_options = []
        for src, count in sorted(groups, key=lambda item: -item[1])[:4]:
            plans = self._split_options_for_group(state, src, count, groups, enemies, human_groups)
            if plans:
                split_options.append((src, plans))
        if not split_options:
            return

        baseline = {src: self._encode_group_move(options[0])
                    for (src, _), options in zip(groups, group_options) if options}

        def append_plan(replacements):
            moves = []
            replaced_sources = set(replacements)
            for src, split_moves in replacements.items():
                moves.extend(split_moves)
            for src, move in baseline.items():
                if src not in replaced_sources:
                    moves.append(move)
            ok, _ = state.validate_moves(moves, species)
            if ok and moves not in candidates:
                candidates.append(moves)

        added_before = len(candidates)
        # Give each eligible group a chance to split while the other groups follow their
        # normal best-ranked step. This continues to work after earlier groups have split.
        for src, plans in split_options:
            for _, moves in plans[:3]:
                if len(candidates) - added_before >= limit:
                    return
                append_plan({src: moves})

        # Also consider two groups detaching in the same turn, but tightly bound the branch.
        for i, (src_a, plans_a) in enumerate(split_options[:3]):
            for src_b, plans_b in split_options[i + 1:3]:
                if len(candidates) - added_before >= limit:
                    return
                if plans_a and plans_b:
                    append_plan({src_a: plans_a[0][1], src_b: plans_b[0][1]})

    def _append_regroup_plan(self, state, species, groups, enemies, human_groups,
                             candidates):
        """Offer a legal move that pulls separated groups together when threats close in."""
        if len(groups) < 2:
            return
        enemy_distance = min((chebyshev_dist(pos, ep) for pos, _ in groups
                              for ep, _ in enemies), default=10**6)
        if enemy_distance > 4 and human_groups:
            return
        ordered = sorted(groups, key=lambda item: -item[1])
        rally, rally_count = ordered[0]
        sources = {pos for pos, _ in groups}
        enemy_at = dict(enemies)
        moves = []
        for src, count in ordered[1:]:
            old_distance = chebyshev_dist(src, rally)
            options = []
            for dst in state.get_neighbors(src):
                if dst in sources or chebyshev_dist(dst, rally) >= old_distance:
                    continue
                humans, _, _ = state.get_cell(dst)
                if humans > count or enemy_at.get(dst, 0):
                    continue
                if any(chebyshev_dist(ep, dst) == 1 and ec >= count
                       for ep, ec in enemies):
                    continue
                options.append((chebyshev_dist(dst, rally), dst))
            if options:
                _, dst = min(options)
                moves.append((src[0], src[1], count, dst[0], dst[1]))
        # When two groups can safely meet on one empty cell, merge them this turn.
        if not moves and len(ordered) == 2:
            other, other_count = ordered[1]
            common = set(state.get_neighbors(rally)).intersection(state.get_neighbors(other))
            common = [dst for dst in common if dst not in sources and not enemy_at.get(dst, 0)
                      and state.get_cell(dst)[0] <= rally_count + other_count]
            if common:
                dst = min(common, key=lambda cell: (chebyshev_dist(cell, rally), cell))
                moves = [(rally[0], rally[1], rally_count, dst[0], dst[1]),
                         (other[0], other[1], other_count, dst[0], dst[1])]
        if moves:
            ok, _ = state.validate_moves(moves, species)
            if ok and moves not in candidates:
                candidates.append(moves)

    def compute_hash(self, state: BoardState, active_species: Species) -> int:
        h = 0x84222325CBBF484F
        if active_species == Species.VAMPIRE:
            h ^= 0x1B873593
        for pos, (hum, vmp, wrw) in state.grid.items():
            k_h, k_v, k_w = self._get_zobrist_keys(pos)
            if hum > 0:
                h ^= (k_h * hum) & 0xFFFFFFFFFFFFFFFF
            if vmp > 0:
                h ^= (k_v * vmp) & 0xFFFFFFFFFFFFFFFF
            if wrw > 0:
                h ^= (k_w * wrw) & 0xFFFFFFFFFFFFFFFF
        return h

    # ---------------------------------------------------------
    # Move Generation (Deathball Concentration Principle)
    # ---------------------------------------------------------
    def generate_moves(self, state: BoardState, species: Species) -> List[List[Tuple[int, int, int, int, int]]]:
        """
        Generates tactical moves adhering strictly to Rules 1 to 6.
        Keeps armies unified to maximize Lanchester combat power,
        merging groups when separated.
        """
        groups = state.get_species_groups(species)
        if not groups:
            return []

        enemy_species = Species.WEREWOLF if species == Species.VAMPIRE else Species.VAMPIRE
        enemy_groups = state.get_species_groups(enemy_species)
        human_groups = state.get_humans()
        sources = set(pos for pos, _ in groups)

        candidate_list: List[List[Tuple[int, int, int, int, int]]] = []

        # CASE 1: Single group: ordinary whole-group moves plus safe split-foraging plans.
        if len(groups) == 1:
            (src_x, src_y), count = groups[0]
            src = (src_x, src_y)
            neighbors = state.get_neighbors(src)
            valid_destinations = [n for n in neighbors if n not in sources] or neighbors

            for dst in valid_destinations:
                candidate_list.append([(src_x, src_y, count, dst[0], dst[1])])
            single_group_options = [[(src, count, dst) for dst in valid_destinations]]
            self._append_split_plans(state, species, groups, enemy_groups, human_groups,
                                     single_group_options, candidate_list)
            return candidate_list

        # CASE 2: Multiple Groups (Merging & Coordinated Movement)
        # Groups try to converge on each other or on tactical objectives
        group_options: List[List[Tuple[Tuple[int, int], int, Tuple[int, int]]]] = []
        for (src_x, src_y), count in groups:
            src = (src_x, src_y)
            neighbors = state.get_neighbors(src)
            valid_dsts = [n for n in neighbors if n not in sources] or neighbors

            # Prioritize destinations that merge with other friendly groups or take humans
            def merge_priority(dst):
                val = 0.0
                th, tv, tw = state.get_cell(dst)
                ene_cnt = tw if species == Species.VAMPIRE else tv
                if ene_cnt > 0 and count >= 1.5 * ene_cnt:
                    val += 1000.0  # 1.5x enemy kill
                elif th > 0 and count >= th:
                    val += 500.0   # Safe human capture
                # Proximity to other friendly groups (strong incentive to merge)
                for other_pos, _ in groups:
                    if other_pos != src:
                        val -= chebyshev_dist(dst, other_pos) * 50.0
                return val

            sorted_dsts = sorted(valid_dsts, key=merge_priority, reverse=True)[:4]
            group_options.append([((src_x, src_y), count, d) for d in sorted_dsts])

        if len(group_options) == 2:
            for opt1 in group_options[0]:
                for opt2 in group_options[1]:
                    candidate_list.append([
                        (opt1[0][0], opt1[0][1], opt1[1], opt1[2][0], opt1[2][1]),
                        (opt2[0][0], opt2[0][1], opt2[1], opt2[2][0], opt2[2][1])
                    ])
        else:
            combined = []
            for opts in group_options:
                best = opts[0]
                combined.append((best[0][0], best[0][1], best[1], best[2][0], best[2][1]))
            candidate_list.append(combined)

        self._append_split_plans(state, species, groups, enemy_groups, human_groups,
                                 group_options, candidate_list)
        self._append_regroup_plan(state, species, groups, enemy_groups, human_groups,
                                  candidate_list)

        return candidate_list

    # ---------------------------------------------------------
    # Evaluation Function
    # ---------------------------------------------------------
    def evaluate(self, state: BoardState, our_species: Species) -> float:
        enemy_species = Species.WEREWOLF if our_species == Species.VAMPIRE else Species.VAMPIRE

        our_total = state.get_species_total(our_species)
        ene_total = state.get_species_total(enemy_species)

        # Terminal conditions
        if ene_total == 0 and our_total > 0:
            return 1000000.0 + our_total * 1000.0
        if our_total == 0:
            return -1000000.0 - ene_total * 1000.0

        score = 0.0

        # 1. Material Advantage & 1.5x Domination Threshold
        mat_diff = our_total - ene_total
        score += mat_diff * W_MATERIAL

        if our_total >= 1.5 * ene_total:
            score += W_DOMINATION_BONUS + (our_total - 1.5 * ene_total) * 1000.0
        elif ene_total >= 1.5 * our_total:
            score -= W_DOMINATION_BONUS + (ene_total - 1.5 * our_total) * 1000.0

        our_groups = state.get_species_groups(our_species)
        enemy_groups = state.get_species_groups(enemy_species)
        human_groups = state.get_humans()

        # 2. Human Feeding Potential Gradient
        # Strategic territorial pull towards all reachable human settlements
        if human_groups:
            for (my_pos, my_cnt) in our_groups:
                safe_humans = [(h_pos, h_cnt) for (h_pos, h_cnt) in human_groups if my_cnt >= h_cnt]
                if safe_humans:
                    pulls = []
                    for h_pos, h_cnt in safe_humans:
                        d = chebyshev_dist(my_pos, h_pos)

                        # Ghost Defender Correction (General & Anti-Overfitting):
                        # An enemy is only a genuine competitor if it has enough units to convert safely (e_cnt >= h_cnt)
                        competitors = [e_pos for e_pos, e_cnt in enemy_groups if e_cnt >= h_cnt]
                        min_ene_d = min(chebyshev_dist(e_pos, h_pos) for e_pos in competitors) if competitors else max(state.rows, state.cols)

                        # Seamless Voronoi Proximity Factor (No binary cliff, eliminates oscillation):
                        if self.enable_voronoi:
                            # Smooth, bounded distance advantage avoids cliffs and scales to 50x50.
                            margin = max(-1.0, min(1.0, (min_ene_d - d) / 4.0))
                            ratio = 1.0 + 0.4 * margin
                        else:
                            ratio = 1.3 if d <= min_ene_d else 0.7

                        # --- FEATURE 1: OPTIMAL FORAGING YIELD ---
                        if self.enable_foraging_yield:
                            pull = (W_HUMAN_PULL * h_cnt * ratio) / ((d + 0.5) ** 1.6)
                            if d == 1:
                                pull += 8000.0  # Immediate tactical capture bonus
                        else:
                            pull = (W_HUMAN_PULL * (h_cnt ** 1.1) * ratio) / (d + 1.0)

                        pulls.append((pull, h_pos))
                    # Reward several distinct opportunities, with diminishing returns so a
                    # crowded map does not overwhelm material and tactical terms.
                    pulls.sort(reverse=True)
                    for rank, (pull, _) in enumerate(pulls[:3]):
                        score += pull / (rank + 1)

        # 3. Threat Matrix & Danger Avoidance
        for (my_pos, my_cnt) in our_groups:
            for (e_pos, e_cnt) in enemy_groups:
                dist = chebyshev_dist(my_pos, e_pos)

                if dist == 1:
                    # In direct strike range
                    if my_cnt >= 1.5 * e_cnt:
                        score += W_THREAT_KILL + (e_cnt * 3000.0)
                    elif e_cnt >= 1.5 * my_cnt:
                        score += W_DANGER_LETHAL - (my_cnt * 3000.0)
                    else:
                        # Random battle risk: heavily penalize gambling on dice rolls
                        score -= 50000.0

                elif dist == 2:
                    # 1 step away from danger/ambush
                    if e_cnt >= 1.5 * my_cnt:
                        # Danger: enemy could step into contact with 1.5x advantage
                        score -= 25000.0
                    elif my_cnt >= 1.5 * e_cnt:
                        score += 15000.0

        # 4. Merging Incentive (if split)
        if len(our_groups) > 1:
            # Penalize fragmentation proportionally to the whole force, independent of group order.
            pair_distances = [chebyshev_dist(our_groups[i][0], our_groups[j][0])
                              for i in range(len(our_groups))
                              for j in range(i + 1, len(our_groups))]
            score -= (sum(pair_distances) / len(pair_distances)) * 300.0

        # 5. Endgame Pursuit (King-Hunt mode)
        # If we dominate (1.5x) or all humans are gone, relentlessly chase down enemies
        if (our_total >= 1.5 * ene_total or not human_groups) and enemy_groups:
            closest_enemy_dist = min(
                chebyshev_dist(g_pos, e_pos)
                for g_pos, _ in our_groups
                for e_pos, _ in enemy_groups
            )
            score -= closest_enemy_dist * W_PURSUIT

        return score

    # ---------------------------------------------------------
    # Alpha-Beta Search Core
    # ---------------------------------------------------------
    def alpha_beta(self, state: BoardState, depth: int, alpha: float, beta: float,
                   maximizing_player: bool, root_species: Species) -> float:
        self.nodes_searched += 1

        if time.time() - self.start_time > self.max_time:
            self.time_limit_exceeded = True
            return 0.0

        over, winner = state.is_game_over()
        if over:
            if winner == root_species:
                return 1000000.0 + depth * 1000.0
            elif winner is not None:
                return -1000000.0 - depth * 1000.0
            return 0.0

        if depth == 0:
            if not self.enable_quiescence:
                return self.evaluate(state, root_species)
            return self.quiescence_search(state, alpha, beta, maximizing_player, root_species, qdepth=1)

        current_species = root_species if maximizing_player else (
            Species.WEREWOLF if root_species == Species.VAMPIRE else Species.VAMPIRE
        )

        state_hash = self.compute_hash(state, current_species)
        tt_entry = self.transposition_table.get(state_hash)
        tt_best_move = None
        if tt_entry is not None and tt_entry.depth >= depth:
            if tt_entry.flag == 0:
                return tt_entry.score
            elif tt_entry.flag == 1:
                alpha = max(alpha, tt_entry.score)
            elif tt_entry.flag == 2:
                beta = min(beta, tt_entry.score)
            if alpha >= beta:
                return tt_entry.score
            tt_best_move = tt_entry.best_move

        candidate_moves = self.generate_moves(state, current_species)
        if not candidate_moves:
            return self.evaluate(state, root_species)

        # Move ordering
        def move_priority(m):
            if m == tt_best_move:
                return 1000000.0
            pri = 0.0
            for x1, y1, cnt, x2, y2 in m:
                th, tv, tw = state.get_cell((x2, y2))
                ene_cnt = tw if current_species == Species.VAMPIRE else tv
                if ene_cnt > 0 and cnt >= 1.5 * ene_cnt:
                    pri += 10000.0   # 1.5x enemy kill
                elif th > 0 and cnt >= th:
                    pri += 5000.0 + th * 100.0  # Safe human conversion
                elif ene_cnt > 0 and ene_cnt >= 1.5 * cnt:
                    pri -= 50000.0  # Suicidal blunder
                elif ene_cnt > 0:
                    pri -= 20000.0  # Non-1.5x gamble avoidance!
            return pri

        candidate_moves.sort(key=move_priority, reverse=True)

        best_score = -float('inf') if maximizing_player else float('inf')
        best_move_found = None
        orig_alpha = alpha

        if maximizing_player:
            for move in candidate_moves:
                child_state = state.apply_moves(move, current_species, deterministic=True)
                score = self.alpha_beta(child_state, depth - 1, alpha, beta, False, root_species)
                if self.time_limit_exceeded:
                    return 0.0

                if score > best_score:
                    best_score = score
                    best_move_found = move
                alpha = max(alpha, best_score)
                if alpha >= beta:
                    break
        else:
            for move in candidate_moves:
                child_state = state.apply_moves(move, current_species, deterministic=True)
                score = self.alpha_beta(child_state, depth - 1, alpha, beta, True, root_species)
                if self.time_limit_exceeded:
                    return 0.0

                if score < best_score:
                    best_score = score
                    best_move_found = move
                beta = min(beta, best_score)
                if alpha >= beta:
                    break

        if not self.time_limit_exceeded:
            flag = 0
            if best_score <= orig_alpha:
                flag = 2
            elif best_score >= beta:
                flag = 1
            self.transposition_table[state_hash] = TranspositionEntry(depth, best_score, flag, best_move_found)

        return best_score

    # ---------------------------------------------------------
    # Quiescence Search (Tactical Leaf Stabilization)
    # ---------------------------------------------------------
    def quiescence_search(self, state: BoardState, alpha: float, beta: float,
                           maximizing_player: bool, root_species: Species, qdepth: int = 1) -> float:
        self.nodes_searched += 1
        if time.time() - self.start_time > self.max_time:
            self.time_limit_exceeded = True
            return 0.0

        stand_pat = self.evaluate(state, root_species)
        if qdepth <= 0:
            return stand_pat

        current_species = root_species if maximizing_player else (
            Species.WEREWOLF if root_species == Species.VAMPIRE else Species.VAMPIRE
        )
        our_groups = state.get_species_groups(current_species)
        enemy_species = Species.WEREWOLF if current_species == Species.VAMPIRE else Species.VAMPIRE
        enemy_groups = state.get_species_groups(enemy_species)

        # Stand-Pat cutoff: unconditional (Chess standard, guarantees fast beta-cutoffs)
        if maximizing_player:
            if stand_pat >= beta:
                return beta
            if stand_pat > alpha:
                alpha = stand_pat
        else:
            if stand_pat <= alpha:
                return alpha
            if stand_pat < beta:
                beta = stand_pat

        # Tactical contact check: only proceed if adjacent (d == 1) to an enemy group
        has_contact = any(
            chebyshev_dist(mp, ep) == 1
            for mp, _ in our_groups
            for ep, _ in enemy_groups
        )
        if not has_contact:
            return stand_pat

        candidate_moves = self.generate_moves(state, current_species)
        if not candidate_moves:
            return stand_pat

        # Filter strictly for deterministic tactical captures (1.5x enemy kills or direct human conversions)
        # Quiet moves are already captured by Stand-Pat and must NOT be searched in QS
        capture_moves = []
        for move in candidate_moves:
            is_capture = False
            for x1, y1, cnt, x2, y2 in move:
                th, tv, tw = state.get_cell((x2, y2))
                ene_cnt = tw if current_species == Species.VAMPIRE else tv
                if (ene_cnt > 0 and cnt >= 1.5 * ene_cnt) or (th > 0 and cnt >= th):
                    is_capture = True
                    break
            if is_capture:
                capture_moves.append(move)

        if not capture_moves:
            return stand_pat

        if maximizing_player:
            for move in capture_moves:
                child = state.apply_moves(move, current_species, deterministic=True)
                score = self.quiescence_search(child, alpha, beta, False, root_species, qdepth - 1)
                if self.time_limit_exceeded:
                    return 0.0
                if score >= beta:
                    return beta
                if score > alpha:
                    alpha = score
            return alpha
        else:
            for move in capture_moves:
                child = state.apply_moves(move, current_species, deterministic=True)
                score = self.quiescence_search(child, alpha, beta, True, root_species, qdepth - 1)
                if self.time_limit_exceeded:
                    return 0.0
                if score <= alpha:
                    return alpha
                if score < beta:
                    beta = score
            return beta

    # ---------------------------------------------------------
    # Iterative Deepening Search Root Controller
    # ---------------------------------------------------------
    def compute_moves(self, state: BoardState, species: Species) -> List[Tuple[int, int, int, int, int]]:
        self.start_time = time.time()
        self.time_limit_exceeded = False
        self.nodes_searched = 0

        candidate_moves = self.generate_moves(state, species)
        if not candidate_moves:
            return []
        if len(candidate_moves) == 1:
            return candidate_moves[0]

        root_hash = self.compute_hash(state, species)
        tt_entry = self.transposition_table.get(root_hash)
        tt_best_move = tt_entry.best_move if tt_entry else None

        best_move_overall = candidate_moves[0]
        best_score_overall = -float('inf')

        # Disable GC during search to avoid latency jitter in strict time budget
        gc_was_enabled = gc.isenabled()
        if gc_was_enabled:
            gc.disable()

        try:
            # Iterative deepening is time bound, not capped at an arbitrary shallow ply count.
            # A generous safety ceiling prevents accidental unbounded recursion on pathological states.
            max_search_depth = max(8, min(64, state.max_turns - state.turn_count))
            for depth in range(1, max_search_depth + 1):
                if time.time() - self.start_time > self.max_time:
                    break

                current_best_move = None
                current_best_score = -float('inf')
                alpha = -float('inf')
                beta = float('inf')

                def root_move_priority(m):
                    if m == tt_best_move:
                        return 1000000.0
                    pri = 0.0
                    for x1, y1, cnt, x2, y2 in m:
                        th, tv, tw = state.get_cell((x2, y2))
                        ene_cnt = tw if species == Species.VAMPIRE else tv
                        if ene_cnt > 0 and cnt >= 1.5 * ene_cnt:
                            pri += 50000.0
                        elif th > 0 and cnt >= th:
                            pri += 20000.0 + th * 100.0
                        elif ene_cnt > 0 and ene_cnt >= 1.5 * cnt:
                            pri -= 100000.0
                    return pri

                candidate_moves.sort(key=root_move_priority, reverse=True)

                for move in candidate_moves:
                    child_state = state.apply_moves(move, species, deterministic=True)
                    score = self.alpha_beta(child_state, depth - 1, alpha, beta, False, species)

                    if self.time_limit_exceeded:
                        break

                    if score > current_best_score:
                        current_best_score = score
                        current_best_move = move

                    alpha = max(alpha, score)
                    if alpha >= beta:
                        break

                if not self.time_limit_exceeded and current_best_move is not None:
                    best_move_overall = current_best_move
                    best_score_overall = current_best_score
                    tt_best_move = current_best_move
                    if current_best_score >= 900000.0:
                        break
        finally:
            if gc_was_enabled:
                gc.enable()

        return best_move_overall
