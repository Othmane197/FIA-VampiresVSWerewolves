"""Run with:  python3 test_evaluation.py   (from the repo folder)"""
import random
import time

from evaluation import WIN_SCORE, evaluate, race_term
from game_engine import BoardState
from game_state import Species
from map_loader import load_map

V, W = Species.VAMPIRE, Species.WEREWOLF


def board_from(rows, cols, cells, max_turns=200, turn=0):
    b = BoardState(rows, cols, max_turns)
    b.turn_count = turn
    for pos, (h, v, w) in cells.items():
        b.set_cell(pos, h, v, w)
    return b


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


# 1) The thetrap numbers from the chat (material is 0 in all three cases: 4 vs 4).
trap = load_map("thetrap.xml")
assert close(evaluate(trap, V), 0.0) and close(evaluate(trap, W), 0.0)      # symmetric start

def vampires_at(pos):
    b = trap.clone()
    b.set_cell((4, 3), 0, 0, 0)
    b.set_cell(pos, 0, 4, 0)
    return b

assert close(evaluate(vampires_at((3, 2)), V), -0.5)    # step toward the 4 humans
assert close(evaluate(vampires_at((5, 3)), V), +0.5)    # step toward the right side
assert close(evaluate(vampires_at((3, 2)), W), +0.5)    # the same position seen by the werewolves
print("OK  thetrap: start 0, step to (3,2) = -0.5, step to (5,3) = +0.5")

# 2) Material only (no humans): 6 vampires vs 4 werewolves.
b = board_from(1, 10, {(0, 0): (0, 6, 0), (9, 0): (0, 0, 4)})
assert evaluate(b, V) == 2 and evaluate(b, W) == -2
print("OK  material: 6 v 4 = +2 / -2")

# 3) A group too small cannot race: 3 vampires, 4 humans, 5 werewolves, in a row.
#    Vampires (3 < 4) cannot convert them. Werewolves (5 >= 4) can: -4 * 0.5 = -2. Material 3-5 = -2.
b = board_from(1, 10, {(0, 0): (0, 3, 0), (5, 0): (4, 0, 0), (9, 0): (0, 0, 5)})
assert race_term(b, V) == -4
assert close(evaluate(b, V), -4.0)
print("OK  a group smaller than the humans does not count in the race")

# 4) Nobody can convert a group (both too small): no race term.
b = board_from(1, 10, {(0, 0): (0, 3, 0), (5, 0): (9, 0, 0), (9, 0): (0, 0, 3)})
assert race_term(b, V) == 0 and close(evaluate(b, V), 0.0)
print("OK  humans nobody can convert are ignored")

# 5) Only we can reach a group: full +H even if far away. Equal distance: 0.
b = board_from(1, 10, {(0, 0): (0, 5, 0), (9, 0): (0, 0, 2), (4, 0): (5, 0, 0)})
assert race_term(b, V) == 5 and race_term(b, W) == -5         # wolves (2 < 5) cannot race
b = board_from(1, 11, {(0, 0): (0, 5, 0), (10, 0): (0, 0, 5), (5, 0): (5, 0, 0)})
assert race_term(b, V) == 0 and race_term(b, W) == 0          # distance 5 for both
print("OK  only-we-can-reach = +H, same distance = 0")

# 6) Several human groups add up, and race_weight scales the race term only.
b = board_from(1, 12, {(0, 0): (0, 5, 0), (11, 0): (0, 0, 5),
                       (2, 0): (3, 0, 0), (3, 0): (2, 0, 0), (9, 0): (4, 0, 0)})
assert race_term(b, V) == 3 + 2 - 4
assert close(evaluate(b, V, race_weight=0.0), 0.0)             # material 5 - 5
assert close(evaluate(b, V, race_weight=2.0), 2.0)
print("OK  several groups add up, race_weight works")

# 7) Game over.
assert evaluate(board_from(2, 2, {(0, 0): (0, 3, 0)}), V) == WIN_SCORE          # werewolves eliminated
assert evaluate(board_from(2, 2, {(0, 0): (0, 3, 0)}), W) == -WIN_SCORE
assert evaluate(board_from(2, 2, {}), V) == 0.0                                  # everyone gone
end = board_from(1, 5, {(0, 0): (0, 5, 0), (4, 0): (0, 0, 4)}, max_turns=10, turn=10)
assert evaluate(end, V) == WIN_SCORE and evaluate(end, W) == -WIN_SCORE         # ply limit, V ahead
tie = board_from(1, 5, {(0, 0): (0, 4, 0), (4, 0): (0, 0, 4)}, max_turns=10, turn=10)
assert evaluate(tie, V) == 0.0                                                    # ply limit, equal
for b in (end, tie, board_from(2, 2, {(0, 0): (0, 3, 0)})):                        # agrees with the engine
    over, winner = b.is_game_over()
    assert over
    exp = 0.0 if winner is None else (WIN_SCORE if winner == V else -WIN_SCORE)
    assert evaluate(b, V) == exp
print("OK  game over: win / loss / draw, same conditions as the engine")

# 8) Fuzz: zero-sum (evaluate(b, V) == -evaluate(b, W)), no crash, board untouched.
rng = random.Random(7)
for _ in range(5000):
    rows, cols = rng.randint(2, 9), rng.randint(2, 12)
    spots = [(x, y) for x in range(cols) for y in range(rows)]
    rng.shuffle(spots)
    cells = {}
    for pos, kind in zip(spots, rng.choices("VWH", k=rng.randint(0, 8))):
        n = rng.randint(1, 15)
        cells[pos] = (n, 0, 0) if kind == "H" else ((0, n, 0) if kind == "V" else (0, 0, n))
    b = board_from(rows, cols, cells, max_turns=rng.choice([5, 200]), turn=rng.choice([0, 5]))
    before = dict(b.grid)
    assert close(evaluate(b, V), -evaluate(b, W)), (cells,)
    assert b.grid == before
print("OK  zero-sum on 5000 random boards, boards untouched")

# 8b) New terms: threat / kill potential and tempo.
from evaluation import kill_potential, threat_term, tempo_term
# 6 vampires next to 4 werewolves: 6 >= 1.5 * 4, so 4 enemies can be killed for sure; they cannot kill us (4 < 9)
b = board_from(1, 6, {(1, 0): (0, 6, 0), (2, 0): (0, 0, 4)})
assert kill_potential(b, V) == 4 and kill_potential(b, W) == 0
assert threat_term(b, V) == 4 and threat_term(b, W) == -4
# 5 vampires against 4: 5 < 6, not certain
b = board_from(1, 6, {(1, 0): (0, 5, 0), (2, 0): (0, 0, 4)})
assert kill_potential(b, V) == 0
# pooled: two vampire groups of 3 both next to 4 werewolves (3 + 3 = 6 >= 6)
b = board_from(1, 3, {(0, 0): (0, 3, 0), (2, 0): (0, 3, 0), (1, 0): (0, 0, 4)})
assert kill_potential(b, V) == 4
# a group serving one target cannot serve a second one
b = board_from(1, 5, {(0, 0): (0, 6, 0), (1, 0): (0, 0, 4)})
b.set_cell((0, 0), 0, 6, 0)
print("OK  kill_potential: certain kills, pooling, thresholds")

# tempo: equal distance to a human group goes to the side to move
b = board_from(1, 7, {(0, 0): (0, 3, 0), (6, 0): (0, 0, 3), (3, 0): (2, 0, 0)})
assert tempo_term(b, V, V) == 2 and tempo_term(b, V, W) == -2 and tempo_term(b, W, V) == -2
assert evaluate(b, V, tempo_weight=1.0, to_move=V) == -evaluate(b, W, tempo_weight=1.0, to_move=V)
assert evaluate(b, V, tempo_weight=1.0) == evaluate(b, V)             # unknown mover: no tempo term
print("OK  tempo term: ties go to the side to move, zero-sum")

rng = random.Random(5)
for _ in range(300):                                                    # zero-sum with every term on
    cells = {}
    for _ in range(rng.randint(3, 8)):
        pos = (rng.randrange(8), rng.randrange(5))
        k = rng.randint(1, 12)
        cells[pos] = rng.choice([(k, 0, 0), (0, k, 0), (0, 0, k)])
    cells[(0, 0)] = (0, 4, 0)
    cells[(7, 4)] = (0, 0, 4)
    b = board_from(5, 8, cells)
    for mover in (V, W):
        kw = dict(race_weight=0.5, progress_weight=0.3, threat_weight=0.7, tempo_weight=0.4, to_move=mover)
        assert close(evaluate(b, V, **kw), -evaluate(b, W, **kw))
print("OK  evaluate stays zero-sum with every term switched on (300 random boards)")

# 9) Speed on the biggest map with 6 groups per side and several human groups.
b = BoardState(15, 29)
for x, y in [(3, 3), (6, 7), (9, 2), (12, 9), (5, 12), (15, 5)]:
    b.set_cell((x, y), 0, 5, 0)
for x, y in [(20, 3), (23, 7), (26, 2), (18, 9), (25, 12), (14, 11)]:
    b.set_cell((x, y), 0, 0, 5)
for x, y, n in [(14, 7, 20), (10, 3, 4), (18, 11, 4), (8, 8, 6), (22, 6, 3)]:
    b.set_cell((x, y), n, 0, 0)
t0 = time.perf_counter()
N = 20000
for _ in range(N):
    evaluate(b, V)
print(f"OK  speed: {1e6 * (time.perf_counter() - t0) / N:.1f} microseconds per call (6+6 groups, 5 human groups)")
print("\nAll tests passed.")
