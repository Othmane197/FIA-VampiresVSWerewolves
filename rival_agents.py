"""
Rival AI Agents for Vampires VS Werewolves
Implements multiple distinct AI paradigms coded completely from scratch:
1. RandomAgent - baseline random legal actions
2. GreedyReflexAgent - pure reactive heuristic (the reflex agent archetype)
3. PotentialFieldAgent - physics-inspired attractive/repulsive potential fields
4. ShallowMinimaxAgent - textbook minimax with depth-2 limit and standard material evaluation
5. MonteCarloAgent - pure Monte Carlo rollout tree search
"""

import math
import random
from typing import List, Tuple, Optional, Dict
from game_state import Species
from game_engine import BoardState, DIRECTIONS, chebyshev_dist, manhattan_dist

class BaseAgent:
    def __init__(self, name: str):
        self.name = name

    def compute_moves(self, state: BoardState, species: Species) -> List[Tuple[int, int, int, int, int]]:
        raise NotImplementedError

# -------------------------------------------------------------
# 1. Random Agent
# -------------------------------------------------------------
class RandomAgent(BaseAgent):
    """
    Selects valid legal moves uniformly at random, strictly respecting Rules 1 to 6.
    """
    def __init__(self, name: str = "RandomAI"):
        super().__init__(name)

    def compute_moves(self, state: BoardState, species: Species) -> List[Tuple[int, int, int, int, int]]:
        groups = state.get_species_groups(species)
        if not groups:
            return []

        moves = []
        sources = set(pos for pos, _ in groups)
        chosen_targets = set()

        for (src_x, src_y), count in groups:
            src = (src_x, src_y)
            neighbors = state.get_neighbors(src)
            # Rule 5: target cannot be source
            valid_targets = [n for n in neighbors if n not in sources and n not in chosen_targets]
            if not valid_targets:
                valid_targets = [n for n in neighbors if n not in sources]
                if not valid_targets:
                    valid_targets = neighbors

            dst = random.choice(valid_targets)
            chosen_targets.add(dst)
            moves.append((src_x, src_y, count, dst[0], dst[1]))

        return moves

# -------------------------------------------------------------
# 2. Greedy Reflex Agent (Pure Reactive Heuristic)
# -------------------------------------------------------------
class GreedyReflexAgent(BaseAgent):
    """
    Zero-lookahead reactive agent.
    Greedily targets the closest convertible human group,
    or the closest killable enemy, or avoids enemies with > 1.5x size.
    """
    def __init__(self, name: str = "GreedyReflexAI"):
        super().__init__(name)

    def compute_moves(self, state: BoardState, species: Species) -> List[Tuple[int, int, int, int, int]]:
        groups = state.get_species_groups(species)
        if not groups:
            return []

        enemy_species = Species.WEREWOLF if species == Species.VAMPIRE else Species.VAMPIRE
        enemy_groups = state.get_species_groups(enemy_species)
        human_groups = state.get_humans()

        moves = []
        sources = set(pos for pos, _ in groups)
        chosen_targets = set()

        for (src_x, src_y), count in groups:
            src = (src_x, src_y)
            neighbors = state.get_neighbors(src)
            valid_targets = [n for n in neighbors if n not in sources and n not in chosen_targets]
            if not valid_targets:
                valid_targets = [n for n in neighbors if n not in sources] or neighbors

            # Determine strategic objective
            safe_humans = [h for h in human_groups if count >= h[1]]
            safe_enemies = [e for e in enemy_groups if count >= 1.5 * e[1]]

            target_pos = None
            if safe_humans:
                target_pos = min(safe_humans, key=lambda h: chebyshev_dist(src, h[0]))[0]
            elif safe_enemies:
                target_pos = min(safe_enemies, key=lambda e: chebyshev_dist(src, e[0]))[0]
            elif enemy_groups:
                target_pos = min(enemy_groups, key=lambda e: chebyshev_dist(src, e[0]))[0]
            else:
                target_pos = (state.cols // 2, state.rows // 2)

            def score_dst(dst):
                dist = chebyshev_dist(dst, target_pos)
                # Penalty for stepping directly next to dangerous enemy
                danger = 0
                for e_pos, e_cnt in enemy_groups:
                    if dst == e_pos and e_cnt >= 1.5 * count:
                        danger += 1000
                    elif chebyshev_dist(dst, e_pos) == 1 and e_cnt >= 1.5 * count:
                        danger += 50
                return dist * 10 + danger

            best_dst = min(valid_targets, key=score_dst)
            chosen_targets.add(best_dst)
            moves.append((src_x, src_y, count, best_dst[0], best_dst[1]))

        return moves

# -------------------------------------------------------------
# 3. Potential Field Agent (Physics-Inspired Vectors)
# -------------------------------------------------------------
class PotentialFieldAgent(BaseAgent):
    """
    Computes artificial potential field vectors:
    - Safe humans exert attractive gravity: +weight / dist
    - Dangerous enemies exert strong repulsive forces: -weight / dist^2
    - Weaker enemies exert strong attractive gravity: +weight / dist
    Moves along the resulting potential gradient.
    """
    def __init__(self, name: str = "PotentialFieldAI"):
        super().__init__(name)

    def compute_moves(self, state: BoardState, species: Species) -> List[Tuple[int, int, int, int, int]]:
        groups = state.get_species_groups(species)
        if not groups:
            return []

        enemy_species = Species.WEREWOLF if species == Species.VAMPIRE else Species.VAMPIRE
        enemy_groups = state.get_species_groups(enemy_species)
        human_groups = state.get_humans()

        moves = []
        sources = set(pos for pos, _ in groups)
        chosen_targets = set()

        for (src_x, src_y), count in groups:
            src = (src_x, src_y)
            neighbors = state.get_neighbors(src)
            valid_targets = [n for n in neighbors if n not in sources and n not in chosen_targets]
            if not valid_targets:
                valid_targets = [n for n in neighbors if n not in sources] or neighbors

            # Evaluate each neighbor cell's total potential
            def evaluate_cell_potential(cell_pos):
                potential = 0.0

                # 1. Human attraction
                for h_pos, h_cnt in human_groups:
                    d = max(1, chebyshev_dist(cell_pos, h_pos))
                    if count >= h_cnt:
                        # High positive reward for getting humans
                        potential += (100.0 * h_cnt) / (d ** 1.2)
                    else:
                        # Unsafe human group, minor repulsion unless we can recruit more
                        potential -= (20.0 * h_cnt) / (d ** 2)

                # 2. Enemy attraction / repulsion
                for e_pos, e_cnt in enemy_groups:
                    d = max(1, chebyshev_dist(cell_pos, e_pos))
                    if count >= 1.5 * e_cnt:
                        # We can annihilate them! Very strong attraction
                        potential += (250.0 * e_cnt) / (d ** 1.1)
                    elif e_cnt >= 1.5 * count:
                        # They can crush us! Massive repulsion
                        if d == 1:
                            potential -= 10000.0
                        else:
                            potential -= 500.0 / (d ** 2)
                    else:
                        # Ambiguous random battle
                        potential -= 50.0 / d

                # Slight central bias to avoid corners
                center_dist = chebyshev_dist(cell_pos, (state.cols // 2, state.rows // 2))
                potential -= 0.1 * center_dist

                return potential

            best_dst = max(valid_targets, key=evaluate_cell_potential)
            chosen_targets.add(best_dst)
            moves.append((src_x, src_y, count, best_dst[0], best_dst[1]))

        return moves

# -------------------------------------------------------------
# 4. Shallow Minimax Agent (Depth-2 Standard Minimax)
# -------------------------------------------------------------
class ShallowMinimaxAgent(BaseAgent):
    """
    Classic fixed-depth (depth 2) Minimax agent without advanced move ordering
    or iterative deepening. Uses standard material difference evaluation.
    """
    def __init__(self, name: str = "ShallowMinimaxAI"):
        super().__init__(name)

    def evaluate(self, state: BoardState, species: Species) -> float:
        enemy_species = Species.WEREWOLF if species == Species.VAMPIRE else Species.VAMPIRE
        my_total = state.get_species_total(species)
        ene_total = state.get_species_total(enemy_species)

        if ene_total == 0:
            return 100000.0
        if my_total == 0:
            return -100000.0

        return float(my_total - ene_total) * 100.0

    def generate_candidate_moves(self, state: BoardState, species: Species) -> List[List[Tuple[int, int, int, int, int]]]:
        groups = state.get_species_groups(species)
        if not groups:
            return []

        # For simplicity, move each group as a whole
        sources = set(pos for pos, _ in groups)
        all_group_options = []

        for (src_x, src_y), count in groups:
            src = (src_x, src_y)
            neighbors = state.get_neighbors(src)
            valid = [n for n in neighbors if n not in sources]
            if not valid:
                valid = neighbors
            all_group_options.append([((src_x, src_y), count, dst) for dst in valid])

        # If only 1 group (typical case in early/mid game):
        if len(all_group_options) == 1:
            return [[(src[0], src[1], cnt, dst[0], dst[1])] for src, cnt, dst in all_group_options[0]]

        # If 2 groups, cartesian product of top moves
        candidates = []
        for opt1 in all_group_options[0][:4]:
            for opt2 in all_group_options[1][:4]:
                if opt1[2] != opt2[2]:  # avoid collision
                    candidates.append([
                        (opt1[0][0], opt1[0][1], opt1[1], opt1[2][0], opt1[2][1]),
                        (opt2[0][0], opt2[0][1], opt2[1], opt2[2][0], opt2[2][1])
                    ])
        return candidates or [[(all_group_options[0][0][0][0], all_group_options[0][0][0][1],
                                all_group_options[0][0][1], all_group_options[0][0][2][0], all_group_options[0][0][2][1])]]

    def compute_moves(self, state: BoardState, species: Species) -> List[Tuple[int, int, int, int, int]]:
        candidates = self.generate_candidate_moves(state, species)
        if not candidates:
            return []

        enemy_species = Species.WEREWOLF if species == Species.VAMPIRE else Species.VAMPIRE
        best_score = -float('inf')
        best_move = candidates[0]

        for move in candidates:
            # Depth 1: apply our move
            s1 = state.apply_moves(move, species, deterministic=True)
            over, winner = s1.is_game_over()
            if over:
                score = 100000.0 if winner == species else -100000.0
            else:
                # Depth 2: enemy replies
                ene_candidates = self.generate_candidate_moves(s1, enemy_species)
                if not ene_candidates:
                    score = self.evaluate(s1, species)
                else:
                    min_score = float('inf')
                    for ene_move in ene_candidates[:6]:
                        s2 = s1.apply_moves(ene_move, enemy_species, deterministic=True)
                        val = self.evaluate(s2, species)
                        if val < min_score:
                            min_score = val
                    score = min_score

            if score > best_score:
                best_score = score
                best_move = move

        return best_move

# -------------------------------------------------------------
# 5. Monte Carlo Agent (Flat Rollouts)
# -------------------------------------------------------------
class MonteCarloAgent(BaseAgent):
    """
    Monte Carlo Rollout Agent:
    For each candidate move, performs N fast random/heuristic playouts to depth 8.
    Averages outcome to choose the move with highest win expectation.
    """
    def __init__(self, name: str = "MonteCarloAI", num_rollouts: int = 25, rollout_depth: int = 6):
        super().__init__(name)
        self.num_rollouts = num_rollouts
        self.rollout_depth = rollout_depth
        self.random_agent = RandomAgent("SimRandom")

    def simulate_rollout(self, initial_state: BoardState, our_species: Species) -> float:
        curr = initial_state.clone()
        enemy_species = Species.WEREWOLF if our_species == Species.VAMPIRE else Species.VAMPIRE
        active = enemy_species

        for _ in range(self.rollout_depth):
            over, winner = curr.is_game_over()
            if over:
                if winner == our_species:
                    return 1.0
                elif winner == enemy_species:
                    return -1.0
                return 0.0

            moves = self.random_agent.compute_moves(curr, active)
            if not moves:
                break
            curr = curr.apply_moves(moves, active, deterministic=False)
            active = enemy_species if active == our_species else our_species

        our_cnt = curr.get_species_total(our_species)
        ene_cnt = curr.get_species_total(enemy_species)
        if our_cnt == 0 and ene_cnt == 0:
            return 0.0
        return (our_cnt - ene_cnt) / float(max(1, our_cnt + ene_cnt))

    def compute_moves(self, state: BoardState, species: Species) -> List[Tuple[int, int, int, int, int]]:
        groups = state.get_species_groups(species)
        if not groups:
            return []

        # Generate candidate moves for our groups
        sources = set(pos for pos, _ in groups)
        candidates = []
        for (src_x, src_y), count in groups:
            src = (src_x, src_y)
            for dst in state.get_neighbors(src):
                if dst not in sources:
                    candidates.append([(src_x, src_y, count, dst[0], dst[1])])

        if not candidates:
            return RandomAgent().compute_moves(state, species)

        best_score = -float('inf')
        best_move = candidates[0]

        for move in candidates:
            next_state = state.apply_moves(move, species, deterministic=True)
            total_val = 0.0
            for _ in range(self.num_rollouts):
                total_val += self.simulate_rollout(next_state, species)
            avg_score = total_val / self.num_rollouts

            if avg_score > best_score:
                best_score = avg_score
                best_move = move

        return best_move

# -------------------------------------------------------------
# 6. Tactical Splitter Agent ("L'Hydre Tactique")
# -------------------------------------------------------------
class TacticalSplitterAgent(BaseAgent):
    """
    Expert Multi-Movement Fragmentation & Recombination Agent ("L'Hydre Tactique").
    Exploits the official multi-movement rule (MOV n [...]) to:
    1. Parallel Foraging (Division intelligente) :
       Quand l'ennemi est à distance de sécurité (Chebyshev >= 3), divise
       intelligemment l'armée pour convertir plusieurs villages humains
       en parallèle pendant le MÊME demi-tour.
    2. Garantie de sécurité de Lanchester :
       Ne fragmente jamais en dessous du seuil nécessaire pour convertir (E1 >= H),
       et refuse de fragmenter si l'ennemi peut fondre sur un sous-groupe en <= 2 tours.
    3. Recombinaison Tactique (Fusion / Convergence) :
       Dès que l'ennemi s'approche (dist <= 2) ou que les humains proches sont absorbés,
       tous les détachements convergent vers la même case pour reformer une Deathball
       écrasante et éliminer l'adversaire avec la règle 1.5x.
    """
    def __init__(self, name: str = "TacticalSplitterAI"):
        super().__init__(name)

    def compute_moves(self, state: BoardState, species: Species) -> List[Tuple[int, int, int, int, int]]:
        groups = state.get_species_groups(species)
        if not groups:
            return []

        enemy_species = Species.WEREWOLF if species == Species.VAMPIRE else Species.VAMPIRE
        enemy_groups = state.get_species_groups(enemy_species)
        human_groups = state.get_humans()
        sources = set(pos for pos, _ in groups)

        our_total = state.get_species_total(species)
        ene_total = state.get_species_total(enemy_species)

        # Distance minimale à l'ennemi
        min_ene_dist = 99
        if enemy_groups:
            for g_pos, _ in groups:
                for e_pos, _ in enemy_groups:
                    d = chebyshev_dist(g_pos, e_pos)
                    if d < min_ene_dist:
                        min_ene_dist = d

        # -----------------------------------------------------------------
        # CAS 1 : UN SEUL GROUPE ACTIF -> ÉVALUER UNE FRAGMENTATION TACTIQUE
        # -----------------------------------------------------------------
        if len(groups) == 1:
            (src_x, src_y), count = groups[0]
            src = (src_x, src_y)
            neighbors = state.get_neighbors(src)
            valid_destinations = [n for n in neighbors if n not in sources]

            # Vérifier opportunité d'attaque directe 1.5x
            for e_pos, e_cnt in enemy_groups:
                if e_pos in valid_destinations and count >= 1.5 * e_cnt:
                    return [(src_x, src_y, count, e_pos[0], e_pos[1])]

            # CONDITION DE SÉCURITÉ POUR SPLITTER :
            # 1. Ennemi à distance >= 3 (pas de menace immédiate)
            # 2. Au moins 4 unités disponibles
            # 3. Présence de plusieurs villages humains accessibles
            if min_ene_dist >= 3 and count >= 4 and len(human_groups) >= 2:
                # Chercher villages humains adjacents ou très proches
                adj_humans = [(h_pos, h_cnt) for h_pos, h_cnt in human_groups if h_pos in valid_destinations]
                other_humans = [(h_pos, h_cnt) for h_pos, h_cnt in human_groups if h_pos not in valid_destinations]

                # SCÉNARIO A : 2 villages humains adjacents immédiats
                if len(adj_humans) >= 2:
                    h1_pos, h1_cnt = adj_humans[0]
                    h2_pos, h2_cnt = adj_humans[1]
                    if count >= h1_cnt + h2_cnt:
                        alloc1 = h1_cnt
                        alloc2 = count - alloc1
                        return [
                            (src_x, src_y, alloc1, h1_pos[0], h1_pos[1]),
                            (src_x, src_y, alloc2, h2_pos[0], h2_pos[1])
                        ]

                # SCÉNARIO B : 1 village adjacent + 1 village à distance 2 ou 3
                if len(adj_humans) == 1 and other_humans:
                    h1_pos, h1_cnt = adj_humans[0]
                    target_other = min(other_humans, key=lambda h: chebyshev_dist(src, h[0]))
                    h2_pos, h2_cnt = target_other

                    # Trouver le meilleur voisin vers le 2e village
                    best_step_h2 = min(
                        [n for n in valid_destinations if n != h1_pos],
                        key=lambda n: chebyshev_dist(n, h2_pos),
                        default=None
                    )

                    if best_step_h2 and count >= h1_cnt + 2:
                        alloc1 = h1_cnt
                        alloc2 = count - alloc1
                        return [
                            (src_x, src_y, alloc1, h1_pos[0], h1_pos[1]),
                            (src_x, src_y, alloc2, best_step_h2[0], best_step_h2[1])
                        ]

            # PAS DE FRAGMENTATION : Déplacement du groupe entier
            best_dst = None
            best_score = -float('inf')

            for dst in valid_destinations:
                score = 0.0
                dh, dv, dw = state.get_cell(dst)

                # Conversion humaine
                if dh > 0 and count >= dh:
                    score += 50000.0 + dh * 1000.0
                elif dh > 0 and count < dh:
                    score -= 80000.0

                # Attaque ennemie
                enemy_on_dst = dw if species == Species.VAMPIRE else dv
                if enemy_on_dst > 0:
                    if count >= 1.5 * enemy_on_dst:
                        score += 100000.0
                    else:
                        score -= 200000.0

                # Attirance vers humains restants
                if human_groups:
                    closest_h = min(chebyshev_dist(dst, h_pos) for h_pos, _ in human_groups)
                    score -= closest_h * 50.0

                # Poursuite si dominant
                if our_total >= 1.5 * ene_total and enemy_groups:
                    closest_e = min(chebyshev_dist(dst, e_pos) for e_pos, _ in enemy_groups)
                    score -= closest_e * 80.0

                if score > best_score:
                    best_score = score
                    best_dst = dst

            if best_dst:
                return [(src_x, src_y, count, best_dst[0], best_dst[1])]
            return [(src_x, src_y, count, valid_destinations[0][0], valid_destinations[0][1])]

        # -----------------------------------------------------------------
        # CAS 2 : PLUSIEURS GROUPES ACTIFS -> CONVERGENCE OU CHASSE PARALLÈLE
        # -----------------------------------------------------------------
        moves: List[Tuple[int, int, int, int, int]] = []
        chosen_targets = set()

        # DANGER OU PAS D'HUMAINS : ORDRE DE FUSION / RECOMBINAISON
        must_merge = (min_ene_dist <= 2) or (len(human_groups) == 0) or (our_total < 1.5 * ene_total and enemy_groups)

        if must_merge:
            # Convergence vers le groupe le plus fort
            largest_group_pos = max(groups, key=lambda g: g[1])[0]

            for (src_x, src_y), count in groups:
                src = (src_x, src_y)
                neighbors = state.get_neighbors(src)
                valid = [n for n in neighbors if n not in sources]

                if not valid:
                    valid = neighbors

                if src == largest_group_pos:
                    # Le groupe principal avance vers l'ennemi ou l'humain le plus proche
                    target = enemy_groups[0][0] if enemy_groups else (0, 0)
                    best_step = min(valid, key=lambda n: chebyshev_dist(n, target))
                else:
                    # Les sous-groupes se ruent sur la case du groupe principal pour fusionner
                    best_step = min(valid, key=lambda n: chebyshev_dist(n, largest_group_pos))

                moves.append((src_x, src_y, count, best_step[0], best_step[1]))

            return moves

        # PHASE DE RÉCOLTE PARALLÈLE EN SÉCURITÉ :
        # Chaque groupe s'occupe d'un village humain distinct
        assigned_humans = set()
        for (src_x, src_y), count in groups:
            src = (src_x, src_y)
            neighbors = state.get_neighbors(src)
            valid = [n for n in neighbors if n not in sources]

            # Trouver village humain non assigné le plus proche
            available_h = [h for h in human_groups if h[0] not in assigned_humans]
            if available_h:
                best_h_pos, best_h_cnt = min(available_h, key=lambda h: chebyshev_dist(src, h[0]))
                assigned_humans.add(best_h_pos)
                best_step = min(valid, key=lambda n: chebyshev_dist(n, best_h_pos))
            else:
                best_step = valid[0]

            moves.append((src_x, src_y, count, best_step[0], best_step[1]))

        return moves
