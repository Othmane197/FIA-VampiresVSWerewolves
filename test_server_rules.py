"""Run with:  python3 test_server_rules.py   (from the repo folder)"""
import random

from game_engine import BoardState
from game_state import Species
from move_generator import generate_turns
from server_rules import (check_moves, is_certain_win, perform_moves, random_battle, win_probability)

V, W = Species.VAMPIRE, Species.WEREWOLF


def board_from(rows, cols, cells):
    b = BoardState(rows, cols)
    for pos, (h, v, w) in cells.items():
        b.set_cell(pos, h, v, w)
    return b


class Scripted:
    """Dice that return the given numbers in order (to test one exact outcome)."""
    def __init__(self, *values):
        self.values = list(values)

    def random(self):
        return self.values.pop(0)


# 1) The probability formula, checked by hand.
assert win_probability(4, 4, False) == 0.5
assert win_probability(3, 5, False) == 3 / 10                  # NO certain loss: 3 against 5 is 30%
assert win_probability(2, 3, True) == 2 / 6                    # humans, fewer attackers
assert win_probability(3, 3, True) == 0.5                      # (never used: 3 >= 3 is a certain conversion)
assert win_probability(4, 3, False) == 4 / 3 - 0.5             # monsters, between 1x and 1.5x
assert abs(win_probability(5, 4, False) - (5 / 4 - 0.5)) < 1e-12
assert win_probability(6, 4, False) == 1.0 and win_probability(5, 4, True) == 1.0
assert is_certain_win(6, 4, False) and not is_certain_win(5, 4, False)
assert is_certain_win(3, 3, True) and not is_certain_win(2, 3, True)
print("OK  win_probability: spec formulas, and no certain loss (3 v 5 = 30%)")

# 2) Validation: each rule of Board.CheckMoves.
b = board_from(5, 5, {(1, 1): (0, 6, 0), (3, 3): (0, 0, 4), (4, 0): (2, 0, 0)})
assert check_moves(b, V, [(1, 1, 3, 2, 1)]) is None
assert check_moves(b, V, []) is not None                                  # empty = loss on the server
assert check_moves(b, V, [(1, 1, 2, 2, 1), (1, 1, 4, 1, 2)]) is None       # split one cell in two, total 6
assert check_moves(b, V, [(1, 1, 3, 2, 1), (1, 1, 4, 1, 2)]) is not None   # total 7 > 6
assert check_moves(b, V, [(1, 1, 7, 2, 1)]) is not None                    # more than the cell holds
assert check_moves(b, V, [(1, 1, 0, 2, 1)]) is not None                    # zero creatures
assert check_moves(b, V, [(1, 1, 3, 3, 1)]) is not None                    # two cells away
assert check_moves(b, V, [(1, 1, 3, 1, 1)]) is not None                    # to itself
assert check_moves(b, V, [(3, 3, 2, 3, 2)]) is not None                    # not our species
assert check_moves(b, V, [(0, 0, 1, 1, 0)]) is not None                    # nobody there
assert check_moves(b, V, [(1, 1, 1, 0, 1), (0, 1, 1, 0, 2)]) is not None   # (0,1) is source and target
assert check_moves(b, V, [(1, 1, 1, -1, 1)]) is not None                   # off the grid
assert check_moves(b, W, [(3, 3, 4, 2, 2)]) is None                        # the other species, its own cell
print("OK  check_moves: empty turn, rule 5, counts, adjacency, species, grid")

# 3) Execution, certain cases.
b = board_from(5, 5, {(1, 1): (0, 4, 0), (2, 1): (3, 0, 0)})
r = perform_moves(b, V, [(1, 1, 4, 2, 1)])
assert r.get_cell((2, 1)) == (0, 7, 0) and r.get_cell((1, 1)) == (0, 0, 0) and r.turn_count == 1
assert b.get_cell((1, 1)) == (0, 4, 0)                                      # input untouched
b = board_from(5, 5, {(0, 0): (0, 6, 0), (0, 2): (0, 3, 0)})                # merge into our own group
assert perform_moves(b, V, [(0, 0, 2, 0, 1), (0, 2, 3, 0, 1)]).get_cell((0, 1)) == (0, 5, 0)
b = board_from(5, 5, {(1, 1): (0, 6, 0)})                                   # split one cell into two targets
r = perform_moves(b, V, [(1, 1, 2, 2, 1), (1, 1, 4, 1, 2)])
assert r.get_cell((2, 1)) == (0, 2, 0) and r.get_cell((1, 2)) == (0, 4, 0) and r.get_cell((1, 1)) == (0, 0, 0)
b = board_from(5, 5, {(0, 0): (0, 3, 0), (0, 2): (0, 3, 0), (1, 1): (0, 0, 4)})   # POOLED attack: 3+3 >= 1.5*4
r = perform_moves(b, V, [(0, 0, 3, 1, 1), (0, 2, 3, 1, 1)])
assert r.get_cell((1, 1)) == (0, 6, 0)
print("OK  convert, merge, split one cell, pooled attack = one fight")

# 4) Execution, random battles with scripted dice (3 v 5 monsters: P = 0.3).
b = board_from(5, 5, {(1, 1): (0, 3, 0), (2, 1): (0, 0, 5)})
# dice 0.2 < 0.3: attackers win; then 3 attacker rolls (0.1 live, 0.5 die, 0.29 live) -> 2 survivors
r = perform_moves(b, V, [(1, 1, 3, 2, 1)], Scripted(0.2, 0.1, 0.5, 0.29))
assert r.get_cell((2, 1)) == (0, 2, 0)
# dice 0.9 >= 0.3: attackers lose; 5 defender rolls vs 0.7: live, live, die, live, die -> 3 werewolves, 0 vampires
r = perform_moves(b, V, [(1, 1, 3, 2, 1)], Scripted(0.9, 0.1, 0.6, 0.8, 0.69, 0.95))
assert r.get_cell((2, 1)) == (0, 0, 3) and r.get_cell((1, 1)) == (0, 0, 0)
# a win with NO survivor is possible (the repo engine would force 1): cell ends up empty
r = perform_moves(b, V, [(1, 1, 3, 2, 1)], Scripted(0.0, 0.9, 0.9, 0.9))
assert r.get_cell((2, 1)) == (0, 0, 0)
# humans: 2 v 3 (P = 1/3). A win converts survivors among humans (3 rolls) THEN attackers (2 rolls)
b = board_from(5, 5, {(1, 1): (0, 2, 0), (2, 1): (3, 0, 0)})
r = perform_moves(b, V, [(1, 1, 2, 2, 1)], Scripted(0.1, 0.2, 0.9, 0.2, 0.9, 0.2))
assert r.get_cell((2, 1)) == (0, 3, 0)                                      # humans: live,die,live (2) ; attackers: die,live (1)
# humans: attackers lose, humans keep being humans, each survives with 2/3
r = perform_moves(b, V, [(1, 1, 2, 2, 1)], Scripted(0.9, 0.5, 0.5, 0.9))
assert r.get_cell((2, 1)) == (2, 0, 0)
# werewolves attacking vampires work the same way
b = board_from(5, 5, {(1, 1): (0, 0, 6), (2, 1): (0, 4, 0)})
assert perform_moves(b, W, [(1, 1, 6, 2, 1)]).get_cell((2, 1)) == (0, 0, 6)
print("OK  random battles: exact survivors with scripted dice, losers all die, no minimum survivor")

# 5) Statistics: 3 v 5 wins 30% of the time; mean survivors match the formulas.
rng = random.Random(1)
wins = 0
surv_win = surv_loss = n_loss = 0
N = 40000
for _ in range(N):
    won, s = random_battle(3, 5, False, rng)
    if won:
        wins += 1
        surv_win += s
    else:
        n_loss += 1
        surv_loss += s
assert abs(wins / N - 0.3) < 0.01, wins / N
assert abs(surv_win / wins - 3 * 0.3) < 0.03
assert abs(surv_loss / n_loss - 5 * 0.7) < 0.03
print(f"OK  3 v 5 monsters over {N} battles: wins {wins / N:.3f} (0.3), "
      f"survivors on a win {surv_win / wins:.2f} (0.9), defenders left on a loss {surv_loss / n_loss:.2f} (3.5)")

# 6) Fuzz: every candidate turn from our generator passes the server check (both species).
rng = random.Random(7)
n = 0
for _ in range(1500):
    rows, cols = rng.randint(3, 8), rng.randint(3, 10)
    spots = [(x, y) for x in range(cols) for y in range(rows)]
    rng.shuffle(spots)
    cells = {}
    for pos, kind in zip(spots, ["V", "W"] + [rng.choice("VWH") for _ in range(rng.randint(2, 8))]):
        k = rng.randint(1, 12)
        cells[pos] = (k, 0, 0) if kind == "H" else ((0, k, 0) if kind == "V" else (0, 0, k))
    b = board_from(rows, cols, cells)
    for sp in (V, W):
        for t in generate_turns(b, sp):
            reason = check_moves(b, sp, t)
            assert reason is None, (reason, t, cells)
            n += 1
print(f"OK  {n} generated turns: all accepted by the server check")

# 7) Fuzz: random move lists get the same verdict from the repo engine and from the server port.
rng = random.Random(11)
agree = disagree = 0
examples = []
for _ in range(6000):
    rows, cols = rng.randint(3, 6), rng.randint(3, 6)
    b = BoardState(rows, cols)
    for _ in range(rng.randint(2, 6)):
        pos = (rng.randrange(cols), rng.randrange(rows))
        k = rng.randint(1, 6)
        kind = rng.choice("VWH")
        b.set_cell(pos, *((k, 0, 0) if kind == "H" else ((0, k, 0) if kind == "V" else (0, 0, k))))
    moves = []
    for _ in range(rng.randint(0, 3)):
        x, y = rng.randrange(cols), rng.randrange(rows)
        moves.append((x, y, rng.randint(0, 7), x + rng.randint(-2, 2), y + rng.randint(-2, 2)))
    ok_engine = b.validate_moves(moves, V)[0]
    ok_server = check_moves(b, V, moves) is None
    if ok_engine == ok_server:
        agree += 1
    else:
        disagree += 1
        examples.append((moves, ok_engine, ok_server))
assert disagree == 0, examples[:3]
print(f"OK  validity verdicts: repo engine and server port agree on {agree} random move lists")

# 8) Fuzz: on CERTAIN turns (no random battle) the repo engine and the server port give the same board.
rng = random.Random(13)
compared = 0
for _ in range(4000):
    rows, cols = rng.randint(3, 7), rng.randint(3, 8)
    cells = {}
    spots = [(x, y) for x in range(cols) for y in range(rows)]
    rng.shuffle(spots)
    for pos, kind in zip(spots, ["V", "W"] + [rng.choice("VWH") for _ in range(rng.randint(2, 7))]):
        k = rng.randint(1, 12)
        cells[pos] = (k, 0, 0) if kind == "H" else ((0, k, 0) if kind == "V" else (0, 0, k))
    b = board_from(rows, cols, cells)
    sp = rng.choice((V, W))
    turns = generate_turns(b, sp)
    t = rng.choice(turns)
    totals = {}
    for x1, y1, c, x2, y2 in t:
        totals[(x2, y2)] = totals.get((x2, y2), 0) + c
    certain = True
    for dst, tot in totals.items():
        h, v, w = b.get_cell(dst)
        enemy = w if sp == V else v
        if h > 0 and tot < h:
            certain = False
        if enemy > 0 and not (tot >= 1.5 * enemy):
            certain = False
    if not certain:
        continue
    assert b.apply_moves(t, sp, deterministic=True).grid == perform_moves(b, sp, t).grid, (cells, t)
    compared += 1
print(f"OK  {compared} certain turns: repo engine and server port produce identical boards")
print("\nAll tests passed.")
