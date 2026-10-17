"""Run with:  python3 test_map_loader.py   (from the repo folder)"""
from game_engine import BoardState
from game_state import Species
from map_loader import load_map, render_board


def total_humans(b: BoardState) -> int:
    return sum(count for _, count in b.get_humans())


def check(path, rows, cols, humans, vampires, werewolves):
    b = load_map(path)
    assert (b.rows, b.cols) == (rows, cols), (path, b.rows, b.cols)
    assert total_humans(b) == humans, (path, total_humans(b))
    assert b.get_species_total(Species.VAMPIRE) == vampires
    assert b.get_species_total(Species.WEREWOLF) == werewolves
    print(f"OK  {path}: {rows}x{cols}, humans={humans}, V={vampires}, W={werewolves}")
    return b


# Expected numbers come from reading the XML files by hand.
print(render_board(check("thetrap.xml", 5, 10, humans=9, vampires=4, werewolves=4)))
print()
check("testmap.xml", 15, 29, humans=32, vampires=10, werewolves=10)
check("testmap2.xml", 15, 29, humans=32, vampires=10, werewolves=10)

# Specific cells, to check that X is the column and Y the row.
trap = load_map("thetrap.xml")
assert trap.get_cell((2, 2)) == (4, 0, 0)   # 4 humans
assert trap.get_cell((4, 1)) == (0, 0, 4)   # 4 werewolves
assert trap.get_cell((4, 3)) == (0, 4, 0)   # 4 vampires
assert trap.get_cell((0, 0)) == (0, 0, 0)   # empty
print("\nAll tests passed.")
