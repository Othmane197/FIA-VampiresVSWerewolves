"""Run with:  python3 test_search_agent.py   (from the repo folder)"""
import random
import time

from agents_baseline import RandomAgent
from game_engine import BoardState
from game_state import Species
from map_loader import load_map
from search_agent import SearchAgent, choose_turn
from selfplay import play_game
from state_converter import state_from_board

V, W = Species.VAMPIRE, Species.WEREWOLF


def board_from(rows, cols, cells):
    b = BoardState(rows, cols)
    for pos, (h, v, w) in cells.items():
        b.set_cell(pos, h, v, w)
    return b


def dests(turn):
    return {(m[3], m[4]) for m in turn}


# 1) A certain kill is taken (6 vampires vs 4 werewolves: 6 >= 1.5 * 4 wipes them out = game won).
b = board_from(1, 6, {(1, 0): (0, 6, 0), (2, 0): (0, 0, 4)})
turn, info = choose_turn(b, V, depth=2)
assert turn == [(1, 0, 6, 2, 0)] and info.best_value == 10_000
print("OK  takes a certain winning kill")

# 2) A safe conversion is taken (4 vampires, 3 humans next to them, enemy far away).
b = board_from(1, 8, {(2, 0): (0, 4, 0), (3, 0): (3, 0, 0), (7, 0): (0, 0, 4)})
turn, _ = choose_turn(b, V, depth=2)
assert (3, 0) in dests(turn)
print("OK  converts adjacent humans")

# 3) It does not suicide: 3 vampires next to 5 werewolves. On the real server this is a 30% gamble (not
#    a certain loss), and a failed attack costs all 3 vampires, so the search still declines it.
b = board_from(1, 10, {(4, 0): (0, 3, 0), (5, 0): (0, 0, 5), (9, 0): (0, 0, 2)})
turn, info = choose_turn(b, V, depth=2)
assert (5, 0) not in dests(turn)
attack_value = min(v for v, t in info.values if (5, 0) in dests(t))
assert attack_value < info.best_value
print("OK  refuses a 30%% gamble that risks everything (value of the attack %.0f, best %.0f)" % (attack_value, info.best_value))

# 4) Looking one reply ahead matters.  3 vampires next to 3 humans; 10 werewolves wait right behind
#    them.  Converting needs all 3 vampires and gives 6, which looks better at depth 1 (6 v 10 = -4,
#    against -7 for retreating).  But then the werewolves attack our 6 with 10 >= 1.5*6 = 9: a certain
#    wipe-out.  Depth 2 sees that reply (value -10000) and retreats.
b = board_from(3, 4, {(0, 1): (0, 3, 0), (1, 1): (3, 0, 0), (2, 1): (0, 0, 10)})
t1, i1 = choose_turn(b, V, depth=1)
t2, i2 = choose_turn(b, V, depth=2)
assert (1, 1) in dests(t1), t1                 # depth 1 walks into the trap
assert (1, 1) not in dests(t2), t2             # depth 2 avoids it
assert min(v for v, t in i2.values if (1, 1) in dests(t)) == -10_000
print("OK  depth 2 avoids a trap that depth 1 walks into")

# 4b) The "just enough" amount lets the search convert cheaply: 4 vampires, 1 human, 8 werewolves behind.
#    It sends ONE vampire to convert and keeps three in reserve, so the reply can cost at most 2.
b = board_from(3, 4, {(0, 1): (0, 4, 0), (1, 1): (1, 0, 0), (2, 1): (0, 0, 8)})
t2, _ = choose_turn(b, V, depth=2)
assert t2 == [(0, 1, 1, 1, 1)], t2
print("OK  converts with just enough creatures and keeps a reserve")

# 5) Time control: with a tiny budget the search stops, still returns a LEGAL turn, quickly.
big = BoardState(15, 29)
for x, y in [(3, 3), (6, 7), (9, 2), (12, 9), (5, 12), (15, 5)]:
    big.set_cell((x, y), 0, 5, 0)
for x, y in [(20, 3), (23, 7), (26, 2), (18, 9), (25, 12), (14, 11)]:
    big.set_cell((x, y), 0, 0, 5)
for x, y, n in [(14, 7, 20), (10, 3, 4), (18, 11, 4), (8, 8, 6), (22, 6, 3)]:
    big.set_cell((x, y), n, 0, 0)
t0 = time.perf_counter()
turn, info = choose_turn(big, V, depth=4, time_limit=0.05)
elapsed = time.perf_counter() - t0
assert info.timed_out and elapsed < 0.25, (info.timed_out, elapsed)
assert big.validate_moves(turn, V)[0]
print(f"OK  time control: depth-4 search on a big board stopped after {1000 * elapsed:.0f} ms, legal turn")

# 6) The agent interface: GameState in, legal turn out; errors never escape.
trap = load_map("thetrap.xml")
agent = SearchAgent(depth=2)
state = state_from_board(trap, V, home=(4, 3))
moves = agent.compute_moves(state)
assert trap.validate_moves(moves, V)[0] and agent.last_info.depth == 2
assert agent.compute_moves(None) == [] and agent.last_error        # garbage in: no exception
print("OK  SearchAgent.compute_moves: legal turn; bad input returns [] without raising")

# 7) Fuzz: on random boards the chosen turn is always legal, for both species.
rng = random.Random(5)
for _ in range(400):
    rows, cols = rng.randint(3, 8), rng.randint(3, 10)
    spots = [(x, y) for x in range(cols) for y in range(rows)]
    rng.shuffle(spots)
    cells = {}
    for pos, kind in zip(spots, ["V", "W"] + [rng.choice("VWH") for _ in range(rng.randint(2, 7))]):
        n = rng.randint(1, 12)
        cells[pos] = (n, 0, 0) if kind == "H" else ((0, n, 0) if kind == "V" else (0, 0, n))
    b = board_from(rows, cols, cells)
    for sp in (V, W):
        turn, _ = choose_turn(b, sp, depth=2, time_limit=1.0)
        assert turn and b.validate_moves(turn, sp)[0], (cells, turn)
print("OK  fuzz: 800 searches on random boards, every chosen turn is legal")

# 8) Whole games against the random agent: no illegal move, no timeout, no crash.
for first_species in (V, W):
    for seed in range(3):
        agents = {first_species: SearchAgent(depth=2),
                  (W if first_species == V else V): RandomAgent()}
        r = play_game(trap, agents, seed=seed)
        st = r.stats[first_species]
        assert st.illegal == 0 and st.timeouts == 0 and st.crashes == 0, st.last_problem
print("OK  6 full games vs the random agent: 0 illegal moves, 0 timeouts, 0 crashes")
print("\nAll tests passed.")
