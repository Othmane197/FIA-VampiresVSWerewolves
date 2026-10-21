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
r = play_game(line_board(6, 4), {V: StepTowardEnemy(), W: StepTowardEnemy()})
assert r.winner == V and r.forfeit is None, r
print("OK  scripted game ends with a winner")

b2 = BoardState(1, 2)
b2.set_cell((0, 0), 0, 6, 0)
b2.set_cell((1, 0), 0, 0, 4)
r = play_game(b2, {V: StepTowardEnemy(), W: DoNothing()})
assert r.winner == V and r.plies == 1 and (r.vampires, r.werewolves) == (6, 0) and r.forfeit is None
print("OK  guaranteed kill 6 v 4 wipes the werewolves out on the first ply")

# 1b) An EMPTY turn loses the game at once (official server: the player "stayed static").
r = play_game(line_board(6, 4), {V: StepTowardEnemy(), W: DoNothing()})
assert r.winner == V and r.forfeit == W and r.plies == 1 and r.stats[W].illegal == 1, r
print("OK  empty turn = immediate loss (forfeit)")

# 2) Timeouts are counted and the late moves are ignored (the turn is skipped, the game goes on).
class Slow:
    def compute_moves(self, state):
        time.sleep(0.03)
        return StepTowardEnemy().compute_moves(state)

r = play_game(line_board(5, 5, max_turns=6), {V: Slow(), W: Slow()}, time_limit=0.01)
assert r.stats[V].timeouts == 3 and r.stats[W].timeouts == 3
assert (r.vampires, r.werewolves) == (5, 5) and r.winner is None and r.plies == 6
print("OK  timeouts counted, late moves ignored, game ends at the ply limit (draw 5 v 5)")

# 3) Illegal moves (more creatures than present) and crashes lose the game at once.
class TooMany:
    def compute_moves(self, state):
        (x, y), count = state.get_our_groups()[0]
        return [(x, y, count + 50, x + 1, y)]

class Crashes:
    def compute_moves(self, state):
        raise RuntimeError("boom")

r = play_game(line_board(5, 5, max_turns=4), {V: TooMany(), W: Crashes()})
assert r.forfeit == V and r.winner == W and r.stats[V].illegal == 1 and "creatures from" in r.stats[V].last_problem
r = play_game(line_board(5, 5, max_turns=4), {V: StepTowardEnemy(), W: Crashes()})
assert r.forfeit == W and r.winner == V and r.stats[W].crashes == 1
print("OK  illegal move and crash: the offender loses immediately")

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
