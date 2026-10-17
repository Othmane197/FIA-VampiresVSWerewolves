"""Run with:  python3 test_move_generator.py   (from the repo folder)"""
import random
import time

from game_engine import BoardState
from game_state import Species
from map_loader import load_map
from move_generator import generate_turns, needed_force

V, W = Species.VAMPIRE, Species.WEREWOLF


def board_from(rows, cols, cells):
    b = BoardState(rows, cols)
    for pos, (h, v, w) in cells.items():
        b.set_cell(pos, h, v, w)
    return b


def all_moves(turns):
    return {m for t in turns for m in t}


# 1) "Just enough" force: integers match the spec thresholds.
assert needed_force(4, True) == 4          # humans: at least as many
assert needed_force(4, False) == 6         # monsters: 1.5 * 4
assert needed_force(3, False) == 5         # ceil(4.5)
assert needed_force(1, False) == 2         # ceil(1.5)
print("OK  needed_force")

# 2) Whole group AND 'just enough' are offered against humans (10 vampires next to 4 humans).
b = board_from(1, 6, {(2, 0): (0, 10, 0), (3, 0): (4, 0, 0), (5, 0): (0, 0, 3)})
moves = all_moves(generate_turns(b, V))
assert (2, 0, 10, 3, 0) in moves and (2, 0, 4, 3, 0) in moves
print("OK  humans: whole group (10) and just-enough (4)")

# 3) Against monsters: 4 werewolves need 6; with only 5 vampires only the whole group is offered.
b = board_from(1, 6, {(2, 0): (0, 10, 0), (3, 0): (0, 0, 4)})
moves = all_moves(generate_turns(b, V))
assert (2, 0, 10, 3, 0) in moves and (2, 0, 6, 3, 0) in moves
b = board_from(1, 6, {(2, 0): (0, 5, 0), (3, 0): (0, 0, 4)})
moves = all_moves(generate_turns(b, V))
assert (2, 0, 5, 3, 0) in moves and not any(m[2] == 6 for m in moves)
print("OK  monsters: 1.5x just-enough, only whole group when too weak")

# 4) Safety rule: two groups never attack the same occupied cell together.
b = board_from(1, 3, {(0, 0): (0, 5, 0), (2, 0): (0, 5, 0), (1, 0): (3, 0, 0)})
turns = generate_turns(b, V)
assert turns and all(sum(1 for m in t if (m[3], m[4]) == (1, 0)) <= 1 for t in turns)
assert any((0, 0, 5, 1, 0) in t for t in turns) and any((2, 0, 5, 1, 0) in t for t in turns)
print("OK  no double attack on one target")

# 5) A guaranteed conversion is among the first turns, even with many groups (candidate cap too).
cells = {(0, 0): (0, 6, 0), (1, 0): (3, 0, 0)}                  # 6 vampires next to 3 humans
for i in range(4):
    cells[(5, 2 * i)] = (0, 4, 0)                               # four other groups
cells[(9, 9)] = (0, 0, 8)
b = board_from(10, 10, cells)
turns = generate_turns(b, V, max_candidates=40)
assert len(turns) <= 40
assert any((0, 0, 6, 1, 0) in t or (0, 0, 3, 1, 0) in t for t in turns[:3])
print("OK  conversion ranked first, candidate cap respected")

# 6) The board is never modified.
trap = load_map("thetrap.xml")
before = dict(trap.grid)
generate_turns(trap, V); generate_turns(trap, W)
assert trap.grid == before
print("OK  board untouched")

# 7) Fuzz: every candidate must be LEGAL according to the engine, on many random boards.
rng = random.Random(2024)
count = lengths = longest = 0
t_total = 0.0
for _ in range(3000):
    rows, cols = rng.randint(3, 8), rng.randint(3, 10)
    cells = {}
    spots = [(x, y) for x in range(cols) for y in range(rows)]
    rng.shuffle(spots)
    kinds = ["V", "W"] + [rng.choice("VWH") for _ in range(rng.randint(2, 9))]
    for pos, kind in zip(spots, kinds):
        n = rng.randint(1, 12)
        cells[pos] = (n, 0, 0) if kind == "H" else ((0, n, 0) if kind == "V" else (0, 0, n))
    b = board_from(rows, cols, cells)
    for sp in (V, W):
        t0 = time.perf_counter()
        turns = generate_turns(b, sp)
        t_total += time.perf_counter() - t0
        assert turns, "must always return at least one turn"
        assert len({tuple(t) for t in turns}) == len(turns), "duplicate turns"
        for t in turns:
            ok, msg = b.validate_moves(t, sp)
            assert ok, (msg, t, cells)
        count += 1; lengths += len(turns); longest = max(longest, len(turns))
print(f"OK  fuzz on {count} random positions: all turns legal; "
      f"avg {lengths / count:.1f} turns, max {longest}, {1000 * t_total / count:.2f} ms per call")

# 8) Fuzz on real games: play random candidate turns on the maps and check every position.
positions = 0
for path in ("thetrap.xml", "testmap.xml"):
    for game in range(15):
        rng = random.Random(game)
        random.seed(game)
        b = load_map(path)
        sp = V
        while not b.is_game_over()[0]:
            turns = generate_turns(b, sp)
            assert turns
            for t in turns:
                assert b.validate_moves(t, sp)[0], (t, path, game)
            positions += 1
            b = b.apply_moves(rng.choice(turns), sp, deterministic=False)
            sp = W if sp == V else V
print(f"OK  {positions} positions from played games: every candidate turn legal")
print("\nAll tests passed.")
