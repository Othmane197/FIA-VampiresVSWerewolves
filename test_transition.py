"""Run with:  python3 test_transition.py   (from the repo folder)"""
import random

from game_engine import BoardState
from game_state import Species
from map_loader import load_map
from move_generator import generate_turns
from transition import count_random_battles, turn_outcomes

V, W = Species.VAMPIRE, Species.WEREWOLF


def board_from(rows, cols, cells):
    b = BoardState(rows, cols)
    for pos, (h, v, w) in cells.items():
        b.set_cell(pos, h, v, w)
    return b


def total(outs):
    return sum(p for p, _ in outs)


# 1) A certain battle gives exactly one board, probability 1 (6 vampires vs 4 werewolves: 6 >= 1.5*4).
b = board_from(1, 4, {(0, 0): (0, 6, 0), (1, 0): (0, 0, 4)})
outs = turn_outcomes(b, [(0, 0, 6, 1, 0)], V)
assert len(outs) == 1 and outs[0][0] == 1.0
assert outs[0][1].grid == {(1, 0): (0, 6, 0)}
assert outs[0][1].turn_count == 1 and b.turn_count == 0          # turn counted; original untouched
assert b.grid == {(0, 0): (0, 6, 0), (1, 0): (0, 0, 4)}
print("OK  certain battle: one board, probability 1, original untouched")

# 2) The example from the chat: 5 vampires attack 4 werewolves (p = 0.75): win 4 left, lose 1 werewolf left.
b = board_from(1, 4, {(0, 0): (0, 5, 0), (1, 0): (0, 0, 4)})
outs = sorted(turn_outcomes(b, [(0, 0, 5, 1, 0)], V), key=lambda o: -o[0])
assert len(outs) == 2
assert abs(outs[0][0] - 0.75) < 1e-12 and outs[0][1].grid == {(1, 0): (0, 4, 0)}
assert abs(outs[1][0] - 0.25) < 1e-12 and outs[1][1].grid == {(1, 0): (0, 0, 1)}
print("OK  5 v 4 monsters: 75% -> 4 vampires left, 25% -> 1 werewolf left")

# 3) 3 vampires attack 4 humans (p = 0.375): win 3 (round(0.375*7)=round(2.625)), lose 2 humans left
#    (round(0.625*4)=round(2.5)=3 with half-up rounding).
b = board_from(1, 4, {(0, 0): (0, 3, 0), (1, 0): (4, 0, 0)})
outs = sorted(turn_outcomes(b, [(0, 0, 3, 1, 0)], V), key=lambda o: -o[0])
assert abs(outs[0][0] - 0.625) < 1e-12 and outs[0][1].grid == {(1, 0): (3, 0, 0)}
assert abs(outs[1][0] - 0.375) < 1e-12 and outs[1][1].grid == {(1, 0): (0, 3, 0)}
print("OK  3 v 4 humans: 62.5% humans keep the cell, 37.5% we win with 3")

# 4) Same battle seen from the werewolves' side puts the numbers in the right slots.
b = board_from(1, 4, {(0, 0): (0, 0, 5), (1, 0): (0, 4, 0)})
outs = sorted(turn_outcomes(b, [(0, 0, 5, 1, 0)], W), key=lambda o: -o[0])
assert outs[0][1].grid == {(1, 0): (0, 0, 4)} and outs[1][1].grid == {(1, 0): (0, 1, 0)}
print("OK  werewolves attacking: slots are right")

# 5) Two groups arriving on the same cell fight as ONE group; moves into friendly cells merge.
b = board_from(3, 3, {(0, 0): (0, 3, 0), (2, 0): (0, 3, 0), (1, 0): (4, 0, 0), (1, 2): (0, 2, 0)})
outs = turn_outcomes(b, [(0, 0, 3, 1, 0), (2, 0, 3, 1, 0)], V)       # 6 attack 4 humans: certain
assert len(outs) == 1 and outs[0][1].get_cell((1, 0)) == (0, 10, 0)
outs = turn_outcomes(b, [(0, 0, 3, 1, 1)], V)                        # step onto empty cell
assert outs[0][1].get_cell((1, 1)) == (0, 3, 0)
b2 = board_from(1, 3, {(0, 0): (0, 3, 0), (1, 0): (0, 2, 0)})
assert turn_outcomes(b2, [(0, 0, 3, 1, 0)], V)[0][1].get_cell((1, 0)) == (0, 5, 0)   # merge with friends
print("OK  merging: same destination, empty cell, friendly cell")

# 6) Partial move leaves the rest behind.
b = board_from(1, 3, {(0, 0): (0, 5, 0)})
out = turn_outcomes(b, [(0, 0, 2, 1, 0)], V)[0][1]
assert out.get_cell((0, 0)) == (0, 3, 0) and out.get_cell((1, 0)) == (0, 2, 0)
print("OK  partial move")

# 7) Several gambles in one turn: probabilities always sum to 1; at most 2^max boards from 'two' battles.
b = board_from(5, 5, {(0, 0): (0, 5, 0), (1, 0): (0, 0, 4),            # 5 v 4: gamble
                      (0, 2): (0, 5, 0), (1, 2): (0, 0, 4),            # another gamble
                      (0, 4): (0, 5, 0), (1, 4): (0, 0, 4)})           # a third gamble
turn = [(0, 0, 5, 1, 0), (0, 2, 5, 1, 2), (0, 4, 5, 1, 4)]
assert count_random_battles(b, turn, V) == 3
outs = turn_outcomes(b, turn, V, max_chance_battles=2)
assert len(outs) <= 4 and abs(total(outs) - 1.0) < 1e-9
outs3 = turn_outcomes(b, turn, V, max_chance_battles=3)
assert len(outs3) <= 8 and abs(total(outs3) - 1.0) < 1e-9 and len(outs3) > len(outs)
print(f"OK  three gambles: {len(outs)} boards with max 2 chance battles, {len(outs3)} with max 3")

# 8) Fuzz on real positions: probabilities sum to 1; when no battle is random the result is exactly
#    what the engine computes (the engine is deterministic there); the input board is never modified.
rng = random.Random(11)
checked_certain = checked_random = 0
for path in ("thetrap.xml", "testmap.xml"):
    for game in range(12):
        random.seed(game)
        board = load_map(path)
        sp = V
        while not board.is_game_over()[0]:
            turns = generate_turns(board, sp)
            before = dict(board.grid)
            for turn in turns[:25]:
                outs = turn_outcomes(board, turn, sp)
                assert abs(total(outs) - 1.0) < 1e-9
                assert board.grid == before
                if count_random_battles(board, turn, sp) == 0:
                    assert len(outs) == 1
                    engine = board.apply_moves(turn, sp, deterministic=False)
                    assert outs[0][1].grid == engine.grid, (turn, outs[0][1].grid, engine.grid)
                    assert outs[0][1].turn_count == engine.turn_count
                    checked_certain += 1
                else:
                    checked_random += 1
            board = board.apply_moves(rng.choice(turns), sp, deterministic=False)
            sp = W if sp == V else V
print(f"OK  fuzz: {checked_certain} certain turns identical to the engine, {checked_random} random turns sum to 1")
print("\nAll tests passed.")
