"""
AI Agent for Vampires VS Werewolves
Powered by Apex Alpha-Beta Minimax Engine with Iterative Deepening.
Adheres strictly to the tournament rules specified in Projectv10.pdf.
"""

from typing import List, Tuple, Optional
from game_state import GameState, Species
from game_engine import BoardState
from apex_agent import ApexAlphaBetaAgent

class AIAgent:
    def __init__(self, name: str = "CentraleBot"):
        self.name = name
        # Budget 1.65 seconds to guarantee responding well within the 2.0 second limit
        # Configured with Apex v2: Voronoi dominance + Quiescence leaf stabilization + Optimal foraging
        self.engine = ApexAlphaBetaAgent(
            name=name,
            max_time_seconds=1.65,
            enable_foraging_yield=True,
            enable_voronoi=True,
            enable_quiescence=True
        )

    def _convert_game_state(self, state: GameState) -> BoardState:
        bs = BoardState(state.rows, state.cols)
        for pos, cell in state.board.items():
            bs.set_cell(pos, cell.humans, cell.vampires, cell.werewolves)
        return bs

    def compute_moves(self, state: GameState) -> List[Tuple[int, int, int, int, int]]:
        """
        Computes the optimal list of moves: (x_src, y_src, count, x_dst, y_dst)
        using Alpha-Beta Minimax with Iterative Deepening and Voronoi territory evaluation.
        """
        if state.our_species is None:
            # Fallback if species not yet identified
            our_groups = state.get_our_groups()
            if not our_groups:
                return []
            # Default to vampire or werewolf based on board
            state.our_species = Species.VAMPIRE

        bs = self._convert_game_state(state)
        moves = self.engine.compute_moves(bs, state.our_species)
        return moves
