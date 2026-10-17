"""Run with:  python3 test_state_converter.py   (from the repo folder)"""
from game_state import Cell, GameState, Species
from map_loader import load_map
from state_converter import board_from_state, state_from_board


def server_like_state(board, home):
    """Fill a GameState the same way main.py does when the server sends SET, HME, MAP."""
    state = GameState()
    state.set_grid(board.rows, board.cols)            # SET
    state.set_home(home)                              # HME
    changes = [{"x": x, "y": y, "humans": h, "vampires": v, "werewolves": w}
               for (x, y), (h, v, w) in board.grid.items()]
    state.apply_updates(changes)                      # MAP
    return state


trap = load_map("thetrap.xml")

# 1) We are the vampires (home cell (4,3)): the converted board equals the loaded map.
state = server_like_state(trap, home=(4, 3))
assert state.our_species == Species.VAMPIRE
converted = board_from_state(state)
assert (converted.rows, converted.cols) == (trap.rows, trap.cols)
assert converted.grid == trap.grid
print("OK  GameState -> BoardState (we are vampires)")

# 2) Same thing as werewolves (home cell (4,1)).
state_w = server_like_state(trap, home=(4, 1))
assert state_w.our_species == Species.WEREWOLF
assert board_from_state(state_w).grid == trap.grid
print("OK  GameState -> BoardState (we are werewolves)")

# 3) The copy is independent: a later server update must not change our board.
state.apply_updates([{"x": 2, "y": 2, "humans": 0, "vampires": 4, "werewolves": 0}])
assert converted.get_cell((2, 2)) == (4, 0, 0)
print("OK  the BoardState is a real copy")

# 4) Round trip BoardState -> GameState -> BoardState gives the same board,
#    and the helper methods agents rely on see the right groups.
back = state_from_board(trap, Species.VAMPIRE, home=(4, 3))
assert back.get_our_groups() == [((4, 3), 4)]
assert back.get_enemy_groups() == [((4, 1), 4)]
assert sorted(back.get_human_groups()) == [((2, 2), 4), ((9, 0), 2), ((9, 2), 1), ((9, 4), 2)]
assert board_from_state(back).grid == trap.grid
back.board[(0, 0)] = Cell(0, 1, 0)                # change the GameState...
assert trap.get_cell((0, 0)) == (0, 0, 0)         # ...the original board is untouched
print("OK  round trip and independence")

# 5) Bigger map, both species.
big = load_map("testmap2.xml")
for species, home in ((Species.VAMPIRE, (28, 14)), (Species.WEREWOLF, (0, 0))):
    assert board_from_state(server_like_state(big, home)).grid == big.grid
print("OK  testmap2.xml")
print("\nAll tests passed.")
