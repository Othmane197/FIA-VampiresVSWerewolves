"""
AI Agent: Apex v2 Full Combo (Foraging + Voronoi + Quiescence)
Rank: #2 Vice-Champion (Tournament Round-Robin: 62.5%)
Architecture:
- Tri-Scale Modular Decision Engine (All 3 components active)
- Optimal Foraging Rate (OFR) Yield Formula with d=1 Conversion Bonus
- Capacity-Aware Voronoi Temporal Filter
- Quiescence Search with Stand-Pat Threat Check & Move Ordering
- Alpha-Beta Minimax with Iterative Deepening (budget < 1.65s)
- Zobrist 64-bit Transposition Table
"""

from typing import List, Tuple
from game_state import GameState, Species
from game_engine import BoardState
from apex_agent import ApexAlphaBetaAgent

class AIAgent:
    def __init__(self, name: str = "Apex_v2_All"):
        self.name = name
        # Full Combo Configuration:
        # All three architectural upgrades enabled
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
        if state.our_species is None:
            our_groups = state.get_our_groups()
            if not our_groups:
                return []
            state.our_species = Species.VAMPIRE

        bs = self._convert_game_state(state)
        return self.engine.compute_moves(bs, state.our_species)
