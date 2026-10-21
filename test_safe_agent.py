"""Run with:  python3 test_safe_agent.py   (from the repo folder)"""
import random
import time

from agents_baseline import RandomAgent
from game_engine import BoardState
from game_state import Species
from map_loader import load_map
from safe_agent import SafeAgent, any_legal_turn
from selfplay import play_game
from server_rules import check_moves
from state_converter import state_from_board

V, W = Species.VAMPIRE, Species.WEREWOLF


def board_from(rows, cols, cells):
    b = BoardState(rows, cols)
    for pos, (h, v, w) in cells.items():
        b.set_cell(pos, h, v, w)
    return b


class Fixed:
    """Inner agent that answers with a fixed turn (or raises)."""
    def __init__(self, answer=None, error=None):
        self.answer, self.error = answer, error

    def compute_moves(self, state):
        if self.error:
            raise self.error
        return self.answer


class Garbage:
    """Inner agent that returns random (mostly illegal) moves."""
    def __init__(self, seed):
        self.rng = random.Random(seed)

    def compute_moves(self, state):
        return [(self.rng.randint(-1, 9), self.rng.randint(-1, 9), self.rng.randint(0, 20),
                 self.rng.randint(-1, 9), self.rng.randint(-1, 9)) for _ in range(self.rng.randint(0, 4))]


trap = load_map("thetrap.xml")

# 1) Normal case: the search agent's turn is used and passes the gate (both species).
for sp, home in ((V, (4, 3)), (W, (4, 1))):
    agent = SafeAgent(depth=2)
    state = state_from_board(trap, sp, home=home)
    moves = agent.compute_moves(state)
    assert agent.last_source == "search" and check_moves(trap, sp, moves) is None, agent.last_problem
print("OK  normal turn comes from the search agent and passes the server check")

# 2) The search agent fails in different ways: we still send a legal turn.
state = state_from_board(trap, V, home=(4, 3))
bad_answers = {
    "empty list": [],
    "not adjacent": [(4, 3, 4, 4, 1)],
    "too many creatures": [(4, 3, 9, 4, 4)],
    "zero creatures": [(4, 3, 0, 4, 4)],
    "not our cell": [(4, 1, 4, 4, 2)],
    "rule 5": [(4, 3, 2, 4, 4), (4, 4, 1, 4, 5)],
    "split beyond the cell": [(4, 3, 3, 4, 4), (4, 3, 3, 3, 3)],
    "off grid": [(4, 3, 4, 4, 5)],
}
for label, answer in bad_answers.items():
    agent = SafeAgent(inner=Fixed(answer))
    moves = agent.compute_moves(state)
    assert agent.last_source in ("candidate", "fallback") and moves and check_moves(trap, V, moves) is None, label
    assert agent.last_problem
agent = SafeAgent(inner=Fixed(error=RuntimeError("boom")))
moves = agent.compute_moves(state)
assert agent.last_source == "candidate" and check_moves(trap, V, moves) is None and "boom" in agent.last_problem
print(f"OK  {len(bad_answers)} kinds of bad answers and an exception: replaced by a legal turn")

# 3) Garbage in, legal out: 4000 random boards x both species, with an inner agent that sends nonsense.
rng = random.Random(3)
tiers = {"search": 0, "candidate": 0, "fallback": 0}
for i in range(2000):
    rows, cols = rng.randint(1, 8), rng.randint(2, 10)
    spots = [(x, y) for x in range(cols) for y in range(rows)]
    rng.shuffle(spots)
    cells = {}
    kinds = ["V", "W"] + [rng.choice("VWH") for _ in range(rng.randint(0, 7))]
    for pos, kind in zip(spots, kinds):
        k = rng.randint(1, 15)
        cells[pos] = (k, 0, 0) if kind == "H" else ((0, k, 0) if kind == "V" else (0, 0, k))
    b = board_from(rows, cols, cells)
    for sp in (V, W):
        home = next(p for p, c in cells.items() if c[1 if sp == V else 2] > 0)
        agent = SafeAgent(inner=Garbage(i))
        moves = agent.compute_moves(state_from_board(b, sp, home=home))
        assert moves and check_moves(b, sp, moves) is None, (cells, sp, moves, agent.last_problem)
        tiers[agent.last_source] += 1
print(f"OK  4000 random positions with garbage input: always a legal, non-empty turn  {tiers}")

# 4) Boards where a species is cornered: one creature in the corner of a 1x2 board, and a
#    board where every neighbour is an enemy cell. Still a legal move.
b = board_from(1, 2, {(0, 0): (0, 1, 0), (1, 0): (0, 0, 1)})
agent = SafeAgent(inner=Fixed([]))
m = agent.compute_moves(state_from_board(b, V, home=(0, 0)))
assert m == [(0, 0, 1, 1, 0)] and check_moves(b, V, m) is None
b = board_from(3, 3, {(1, 1): (0, 2, 0), **{(x, y): (0, 0, 5) for x in range(3) for y in range(3) if (x, y) != (1, 1)}})
m = SafeAgent(inner=Fixed([])).compute_moves(state_from_board(b, V, home=(1, 1)))
assert m and check_moves(b, V, m) is None
print("OK  cornered positions still get a legal move")

# 5) any_legal_turn prefers a certain win, then a quiet cell, then a likelier battle.
b = board_from(1, 5, {(2, 0): (0, 4, 0), (1, 0): (3, 0, 0), (3, 0): (0, 0, 20)})
assert any_legal_turn(b, V) == [(2, 0, 4, 1, 0)]                    # 4 >= 3 humans: certain conversion
b = board_from(1, 5, {(2, 0): (0, 4, 0), (3, 0): (0, 0, 20)})
assert any_legal_turn(b, V) == [(2, 0, 4, 1, 0)]                    # quiet cell beats a hopeless attack
assert any_legal_turn(BoardState(3, 3), V) == []                    # no creatures: nothing to send
print("OK  any_legal_turn: certain win > quiet cell > likelier battle")

# 6) Missing information and nonsense never raise.
state = state_from_board(trap, V, home=(4, 3))
state.our_species = None
agent = SafeAgent()
assert agent.compute_moves(state) == [] and agent.last_source == "none"
assert agent.compute_moves(None) == [] and agent.last_source == "none"          # even None
print("OK  unknown species / None state: returns [] without raising")

# 7) Speed: the budget is respected on a big board.
big = BoardState(15, 29)
for x, y in [(3, 3), (6, 7), (9, 2), (12, 9), (5, 12), (15, 5)]:
    big.set_cell((x, y), 0, 5, 0)
for x, y in [(20, 3), (23, 7), (26, 2), (18, 9), (25, 12), (14, 11)]:
    big.set_cell((x, y), 0, 0, 5)
for x, y, n in [(14, 7, 20), (10, 3, 4), (18, 11, 4), (8, 8, 6), (22, 6, 3)]:
    big.set_cell((x, y), n, 0, 0)
agent = SafeAgent(depth=4, time_limit=0.3)
t0 = time.perf_counter()
moves = agent.compute_moves(state_from_board(big, V, home=(3, 3)))
elapsed = time.perf_counter() - t0
assert check_moves(big, V, moves) is None and elapsed < 0.8, elapsed
print(f"OK  depth-4 search on a big board with a 0.3 s budget answered in {1000 * elapsed:.0f} ms")

# 8) Whole games vs the random agent with the repo-style checks: nothing illegal, nothing late.
for first in (V, W):
    for seed in range(3):
        mine = SafeAgent(depth=2)
        agents = {first: mine, (W if first == V else V): RandomAgent()}
        r = play_game(trap, agents, first=first, seed=seed)
        st = r.stats[first]
        assert st.illegal == 0 and st.timeouts == 0 and st.crashes == 0, st.last_problem
print("OK  6 full games with SafeAgent: 0 illegal moves, 0 timeouts, 0 crashes")

# 9) Last line of defence: search AND generator both broken -> the brute-force tier still answers.
import safe_agent as sa
original = sa.generate_turns
sa.generate_turns = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("generator broken"))
try:
    agent = SafeAgent(inner=Fixed(error=RuntimeError("search broken")))
    state = state_from_board(trap, V, home=(4, 3))
    moves = agent.compute_moves(state)
    assert agent.last_source == "fallback" and moves and check_moves(trap, V, moves) is None
    assert "search broken" in agent.last_problem and "generator broken" in agent.last_problem
    assert agent.counts == {"search": 0, "candidate": 0, "fallback": 1, "none": 0}
finally:
    sa.generate_turns = original
print("OK  search and generator both broken: the brute-force tier still sends a legal move")
print("\nAll tests passed.")
