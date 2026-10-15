"""
Starter AI Agent Template for Vampires VS Werewolves
FIA - CentraleSupélec / Centrale Casablanca

Instructions for developers:
- Implement your decision-making algorithm inside `compute_moves()`.
- You can create helper methods, heuristics, tree search (Minimax, Alpha-Beta, MCTS, etc.).
- Respect the protocol constraints:
    * Respond within 2.0 seconds per turn.
    * Return a list of tuples: (src_x, src_y, count, dst_x, dst_y)
    * Destination must be Chebyshev distance 1 (adjacent 8 directions).
    * Rule 5: A cell cannot be both a source and a destination in the same turn.
"""

import random
from typing import List, Tuple, Optional
from game_state import GameState, Species

class AIAgent:
    def __init__(self, name: str = "CentraleBot"):
        self.name = name

    def compute_moves(self, state: GameState) -> List[Tuple[int, int, int, int, int]]:
        """
        Computes the list of moves for the current turn.

        Args:
            state (GameState): The current game state containing:
                - state.rows, state.cols : Dimensions of the grid
                - state.our_species      : Species.VAMPIRE or Species.WEREWOLF
                - state.enemy_species    : Species.WEREWOLF or Species.VAMPIRE
                - state.get_our_groups() : List of [((x, y), count), ...]
                - state.get_enemy_groups(): List of [((x, y), count), ...]
                - state.get_human_groups(): List of [((x, y), count), ...]
                - state.get_legal_adjacent_cells((x, y)) : 8-neighborhood cells within board bounds

        Returns:
            List[Tuple[int, int, int, int, int]]:
                A list of moves formatted as:
                [(src_x, src_y, count, dst_x, dst_y), ...]
        """
        our_groups = state.get_our_groups()
        if not our_groups:
            return []

        # =========================================================================
        # TODO: IMPLEMENT YOUR AI STRATEGY HERE!
        #
        # Suggestions:
        # 1. State evaluation heuristic (Material count, territory, distance to humans)
        # 2. Minimax with Alpha-Beta pruning
        # 3. Iterative deepening with a time limit (e.g., 1.5 - 1.8 seconds)
        # 4. Monte Carlo Tree Search (MCTS) or Potential Fields
        # =========================================================================

        # DEFAULT STARTER BEHAVIOR:
        # A simple legal move generator that moves your groups towards the closest humans or enemies.
        moves: List[Tuple[int, int, int, int, int]] = []
        sources = set(pos for pos, _ in our_groups)
        chosen_destinations = set()

        human_groups = state.get_human_groups()
        enemy_groups = state.get_enemy_groups()
        targets = [pos for pos, _ in human_groups] or [pos for pos, _ in enemy_groups]

        for (src_x, src_y), count in our_groups:
            src = (src_x, src_y)
            neighbors = state.get_legal_adjacent_cells(src)
            
            # Rule 5: Destination cannot be one of our sources or another group's target
            valid_destinations = [n for n in neighbors if n not in sources and n not in chosen_destinations]
            if not valid_destinations:
                valid_destinations = [n for n in neighbors if n not in sources] or neighbors

            # Move towards the closest target if available
            if targets:
                best_dst = min(valid_destinations, key=lambda n: min(state.chebyshev_dist(n, t) for t in targets))
            else:
                best_dst = random.choice(valid_destinations)

            chosen_destinations.add(best_dst)
            moves.append((src_x, src_y, count, best_dst[0], best_dst[1]))

        return moves
