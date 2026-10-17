"""
state_converter.py  (our own file; it does not modify any shared repo file)

Two small translators between the two board types of the repo:

  GameState  (game_state.py)  = the bot's "notebook", updated from server messages
  BoardState (game_engine.py) = a light copy used by search to imagine moves

  board_from_state : GameState  -> BoardState   (used by the AI every turn)
  state_from_board : BoardState -> GameState    (used by the local self-play harness,
                                                 because agents receive a GameState)
Both functions COPY the data: changing one board never changes the other.
"""
from typing import Optional, Tuple

from game_engine import BoardState
from game_state import Cell, GameState, Species


def board_from_state(state: GameState, max_turns: int = 200) -> BoardState:
    """Copy the current GameState into a fresh BoardState."""
    board = BoardState(state.rows, state.cols, max_turns)
    for pos, cell in state.board.items():
        # BoardState stores cells as immutable (humans, vampires, werewolves) tuples.
        board.set_cell(pos, cell.humans, cell.vampires, cell.werewolves)
    return board


def state_from_board(board: BoardState, our_species: Species,
                     home: Optional[Tuple[int, int]] = None) -> GameState:
    """Build a GameState that looks like what the bot would hold during a real game."""
    state = GameState()
    state.set_grid(board.rows, board.cols)
    state.our_species = our_species
    state.enemy_species = (Species.WEREWOLF if our_species == Species.VAMPIRE
                           else Species.VAMPIRE)
    if home is not None:
        state.set_home(home)
    for pos, (humans, vampires, werewolves) in board.grid.items():
        state.board[pos] = Cell(humans, vampires, werewolves)
    return state
