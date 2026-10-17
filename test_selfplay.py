"""Run with:  python3 test_selfplay.py   (from the repo folder)"""
import time

from agents_baseline import RandomAgent
from game_engine import BoardState
from game_state import Species
from map_loader import load_map
from selfplay import play_game, run_match

V, W = Species.VAMPIRE, Species.WEREWOLF


class StepTowardEnemy:
    """Scripted agent: moves its whole first group one cell toward the first enemy group (same row)."""
    def compute_moves(self, state):
        (x, y), count = state.get_our_groups()[0]
        (ex, _), _ = state.get_enemy_groups()[0]
        step = 1 if ex > x else -1
        return [(x, y, count, x + step, y)]


class DoNothing:
    def compute_moves(self, state):
        return []                                  # breaks Rule 1 (at least one move)


def line_board(v, w, max_turns=200):
    """1 row x 4 columns: vampires at (0,0), werewolves at (3,0)."""
    b = BoardState(1, 4, max_turns)
    b.set_cell((0, 0), 0, v, 0)
    b.set_cell((3, 0), 0, 0, w)
    return b


# 1) Scripted win. 6 vampires vs 4 werewolves: 6 >= 1.5*4, so the attack is a guaranteed kill.
r = play_game(line_board(6, 4), {V: StepTowardEnemy(), W: DoNothing()})
assert r.winner == V and (r.vampires, r.werewolves) == (6, 0), r
assert r.plies == 5                                 # V moves at plies 1, 3, 5; W is skipped twice
assert r.stats[W].illegal == 2 and r.stats[V].illegal == 0
print("OK  scripted attack: guaranteed kill, werewolves' empty moves counted as illegal (Rule 1)")

# 2) Timeouts are counted and the late moves are ignored.
class Slow:
    def compute_moves(self, state):
        time.sleep(0.03)
        return StepTowardEnemy().compute_moves(state)

r = play_game(line_board(5, 5, max_turns=6), {V: Slow(), W: Slow()}, time_limit=0.01)
assert r.stats[V].timeouts == 3 and r.stats[W].timeouts == 3
assert (r.vampires, r.werewolves) == (5, 5) and r.winner is None and r.plies == 6
print("OK  timeouts counted, late moves ignored, game ends at the ply limit (draw 5 v 5)")

# 3) Illegal moves (Rule 3: moving more creatures than present) and crashes are caught, not fatal.
class TooMany:
    def compute_moves(self, state):
        (x, y), count = state.get_our_groups()[0]
        return [(x, y, count + 50, x + 1, y)]

class Crashes:
    def compute_moves(self, state):
        raise RuntimeError("boom")

r = play_game(line_board(5, 5, max_turns=4), {V: TooMany(), W: Crashes()})
assert r.stats[V].illegal == 2 and "Rule 3" in r.stats[V].last_problem
assert r.stats[W].crashes == 2
print("OK  illegal moves and crashes are counted")

# 4) Same seed -> same game (needed to replay and debug a game).
trap = load_map("thetrap.xml")
def run(seed):
    r = play_game(trap, {V: RandomAgent(), W: RandomAgent()}, seed=seed)
    return (r.winner, r.plies, r.vampires, r.werewolves, r.humans_left)
assert run(7) == run(7) and run(8) == run(8)
print("OK  seeded games are reproducible")

# 5) The initial board is never modified by a game.
before = dict(trap.grid)
play_game(trap, {V: RandomAgent(), W: RandomAgent()}, seed=1)
assert trap.grid == before
print("OK  initial board untouched")

# 6) run_match: every game is counted once, and both seatings are played.
(s,) = run_match(lambda: RandomAgent(), lambda: RandomAgent(), ["thetrap.xml"], games_per_side=5, seed=3)
assert s.games == 10 and s.a_wins + s.b_wins + s.draws == 10
assert len(s.plies) == 10 and all(p > 0 for p in s.plies)
print("OK  run_match bookkeeping")
print("\nAll tests passed.")
