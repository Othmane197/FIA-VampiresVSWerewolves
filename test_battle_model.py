"""Run with:  python3 test_battle_model.py   (from the repo folder)"""
import random

from battle_model import (battle_outcomes, certain_outcome, expected_outcome,
                          win_probability)
from game_engine import combat_win_probability   # the repo's own formula, for a cross-check


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def mean_of(outcomes):
    return (sum(o.prob * o.friendly for o in outcomes),
            sum(o.prob * o.enemy for o in outcomes),
            sum(o.prob * o.humans for o in outcomes))


# 1) Win probability: spec examples, and agreement with the repo's function where it is used.
assert close(win_probability(4, 4), 0.5)
assert close(win_probability(3, 4), 0.375)
assert close(win_probability(5, 4), 0.75)
assert close(win_probability(6, 4), 1.0)                  # P reaches 1 exactly at 1.5x
for e1 in range(1, 40):
    for e2 in range(1, 40):
        if e1 < 1.5 * e2:                                 # beyond that the battle is certain
            assert close(win_probability(e1, e2), combat_win_probability(e1, e2))
print("OK  win probability matches the spec and game_engine.py")

# 2) Certain battles give exactly one outcome of probability 1.
assert certain_outcome(5, 4, True) == (1.0, 9, 0, 0)       # humans: 5 >= 4 -> convert all
assert certain_outcome(4, 4, True) == (1.0, 8, 0, 0)       # humans: equal is enough
assert certain_outcome(6, 4, False) == (1.0, 6, 0, 0)      # monsters: 6 >= 1.5*4
assert certain_outcome(4, 6, False) is None                # NO certain loss on the real server (4 v 6 = 1/3)
assert certain_outcome(5, 4, False) is None                # 5 v 4 monsters is a real gamble
assert certain_outcome(3, 4, True) is None
for level in ("mean", "two", "full"):
    assert battle_outcomes(6, 4, False, level) == [(1.0, 6, 0, 0)]
print("OK  certain battles")

# 2b) Same probabilities as the port of the official server, for every battle up to 40 v 40.
from server_rules import win_probability as server_p
for e1 in range(1, 41):
    for e2 in range(1, 41):
        for humans in (True, False):
            if humans and e1 >= e2 or (not humans and e1 >= 1.5 * e2):
                continue                                    # certain: no probability needed
            assert close(win_probability(e1, e2), server_p(e1, e2, humans)), (e1, e2, humans)
two = battle_outcomes(3, 5, False, "two")
assert close(sum(o.prob for o in two), 1.0) and close(sorted(o.prob for o in two)[0], 0.3)
print("OK  win probabilities identical to server_rules; 3 v 5 monsters is a 30% battle, not a certain loss")

# 3) Probabilities sum to 1 for every battle, every level.
for e1 in range(1, 26):
    for e2 in range(1, 26):
        for humans in (True, False):
            for level in ("mean", "two", "full"):
                outs = battle_outcomes(e1, e2, humans, level)
                assert close(sum(o.prob for o in outs), 1.0), (e1, e2, humans, level)
print("OK  probabilities sum to 1 (625 battles x 2 targets x 3 levels)")

# 4) The numbers worked out by hand in the chat.
m = expected_outcome(3, 4, True)                           # 3 vampires attack 4 humans
assert close(m.friendly, 0.984375) and close(m.humans, 1.5625) and m.enemy == 0
m = expected_outcome(5, 4, False)                          # 5 vampires attack 4 werewolves
assert close(m.friendly, 2.8125) and close(m.enemy, 0.25) and m.humans == 0
two = battle_outcomes(5, 4, False, "two")
assert sorted(two) == [(0.25, 0, 1, 0), (0.75, 4, 0, 0)]   # win: 3.75 -> 4 left | lose: 1 werewolf left
print("OK  hand-computed examples (3 v 4 humans, 5 v 4 monsters)")

# 5) The full distribution has the same averages as the closed formulas (exact identity).
for e1, e2, humans in [(3, 4, True), (2, 7, True), (5, 4, False), (4, 4, False), (10, 9, False), (20, 17, False)]:
    full = mean_of(battle_outcomes(e1, e2, humans, "full"))
    mean = mean_of(battle_outcomes(e1, e2, humans, "mean"))
    assert all(close(a, b) for a, b in zip(full, mean)), (e1, e2, humans, full, mean)
print("OK  'full' and 'mean' agree exactly")

# 6) Two-outcome level: its average is within 0.5 of the true average (only rounding differs).
for e1, e2, humans in [(3, 4, True), (5, 4, False), (4, 4, False), (10, 9, False), (20, 17, False)]:
    two = mean_of(battle_outcomes(e1, e2, humans, "two"))
    mean = mean_of(battle_outcomes(e1, e2, humans, "mean"))
    assert all(abs(a - b) <= 0.5 + 1e-9 for a, b in zip(two, mean)), (e1, e2, humans, two, mean)
print("OK  'two' differs from the true average by at most the rounding (0.5)")

# 7) Independent check against the rules of the spec, simulated creature by creature.
def simulate(e1, e2, humans, rng):
    # certain battles first, written directly from the spec (independent of battle_model.py)
    if humans and e1 >= e2:
        return e1 + e2, 0, 0
    if not humans and e1 >= 1.5 * e2:
        return e1, 0, 0
    p = win_probability(e1, e2)
    if rng.random() < p:                                    # attackers win
        surviving_attackers = sum(rng.random() < p for _ in range(e1))
        if humans:
            converted = sum(rng.random() < p for _ in range(e2))
            return surviving_attackers + converted, 0, 0
        return surviving_attackers, 0, 0
    left = sum(rng.random() < 1 - p for _ in range(e2))     # attackers lose
    return (0, 0, left) if humans else (0, left, 0)

rng = random.Random(12345)
N = 100_000
for e1, e2, humans in [(3, 4, True), (2, 7, True), (5, 4, False), (4, 4, False), (10, 9, False), (4, 5, False), (3, 5, False), (6, 4, False)]:
    sums = [0, 0, 0]
    for _ in range(N):
        for i, v in enumerate(simulate(e1, e2, humans, rng)):
            sums[i] += v
    sim = [s / N for s in sums]
    exact = expected_outcome(e1, e2, humans)
    for a, b in zip(sim, (exact.friendly, exact.enemy, exact.humans)):
        assert abs(a - b) < 0.05, (e1, e2, humans, sim, exact)
print("OK  matches a 100,000-run simulation of the spec's rules (8 battles)")

# 8) Dropping unlikely outcomes keeps probabilities summing to 1.
pruned = battle_outcomes(20, 17, False, "full", min_prob=0.01)
full = battle_outcomes(20, 17, False, "full")
assert len(pruned) < len(full) and close(sum(o.prob for o in pruned), 1.0)
print(f"OK  min_prob pruning (20 v 17: {len(full)} outcomes -> {len(pruned)})")
print("\nAll tests passed.")
