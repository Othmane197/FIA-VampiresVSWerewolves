# connects the MCTS agent (mcts_agent.py) to main.py
# if something breaks we send a simple legal move so we never miss a turn

import time
from typing import List, Tuple
from game_state import GameState
from game_engine import BoardState
from mcts_agent import MCTSAgent

MAX_PLIES = 200          # MaxPlays in the server config


class AIAgent:
    def __init__(self, name: str = "RaceMCTS", max_time_seconds: float = 1.6):
        self.name = name
        self.brain = MCTSAgent(name=name, max_time_seconds=max_time_seconds)
        self.turns_played = 0

    def _to_board(self, state: GameState) -> BoardState:
        # GameState (live board) -> BoardState (fast copy for the search)
        board = BoardState(state.rows, state.cols, max_turns=MAX_PLIES)
        board.turn_count = min(MAX_PLIES - 1, 2 * self.turns_played)  # 2 plies per turn
        for pos, cell in state.board.items():
            board.set_cell(pos, cell.humans, cell.vampires, cell.werewolves)
        return board

    def compute_moves(self, state: GameState) -> List[Tuple[int, int, int, int, int]]:
        if not state.get_our_groups():
            return []
        board = self._to_board(state)
        try:
            moves = self.brain.compute_moves(board, state.our_species)
            valid, reason = board.validate_moves(moves, state.our_species)
            if not valid:
                print(f"[AIAgent] Invalid MCTS move ({reason}), using fallback.")
                moves = self._fallback(state)
        except Exception as e:
            print(f"[AIAgent] MCTS error: {e}, using fallback.")
            moves = self._fallback(state)
        self.turns_played += 1
        print(f"[AIAgent] {self.brain.last_iterations} imaginary games this turn")
        return moves

    def _fallback(self, state: GameState) -> List[Tuple[int, int, int, int, int]]:
        # move the biggest group to any free neighbour
        groups = state.get_our_groups()
        sources = {p for p, _ in groups}
        (x, y), count = max(groups, key=lambda g: g[1])
        for n in state.get_legal_adjacent_cells((x, y)):
            if n not in sources:
                return [(x, y, count, n[0], n[1])]
        n = state.get_legal_adjacent_cells((x, y))[0]
        return [(x, y, count, n[0], n[1])]

    def reset(self):
        self.turns_played = 0
