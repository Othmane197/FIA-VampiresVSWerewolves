"""Planner: every plan is legal, splits are generated when they should be and refused when unsafe."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from splitter.planner import PlanConfig, detachment_safe, fallback_plan, generate_plans, quick_plan, safe_step
from splitter.rules import V, W, check_moves
from splitter.state import State


def random_state(rng: random.Random) -> State:
    rows, cols = rng.randint(3, 15), rng.randint(3, 20)
    cells = rng.sample([(x, y) for x in range(cols) for y in range(rows)], min(rows * cols, rng.randint(3, 14)))
    h, v, w = {}, {}, {}
    for i, c in enumerate(cells):
        kind = i % 3 if i >= 2 else i + 1
        n = rng.randint(1, 30)
        (h, v, w)[kind][c] = n
    return State(rows, cols, h, v, w, rng.randint(0, 150))


class TestLegality(unittest.TestCase):
    def test_fuzz_all_plans_legal(self):
        rng = random.Random(42)
        cfgs = [PlanConfig(), PlanConfig(splits=False), PlanConfig(gamble="always", max_detachments=4)]
        n_plans = 0
        for i in range(500):
            s = random_state(rng)
            for side in (V, W):
                if not s.groups[side]:
                    continue
                for cfg in cfgs:
                    plans = generate_plans(s, side, cfg, behind=bool(i % 2))
                    self.assertTrue(plans, f"no plan for {s}")
                    for p in plans:
                        n_plans += 1
                        ok, why = check_moves(s.rows, s.cols, s.groups[side], p.moves)
                        self.assertTrue(ok, f"{why}: {p.tag} {p.moves} in {s}")
                ok, why = check_moves(s.rows, s.cols, s.groups[side], quick_plan(s, side))
                self.assertTrue(ok, why)
                ok, why = check_moves(s.rows, s.cols, s.groups[side], fallback_plan(s, side).moves)
                self.assertTrue(ok, why)
        self.assertGreater(n_plans, 1000)

    def test_safe_step_never_walks_into_bigger_humans(self):
        s = State(5, 5, {(1, 1): 9, (2, 1): 9, (1, 2): 9}, {(2, 2): 4}, {(4, 4): 1})
        for goal in [(0, 0), (1, 1), (4, 0)]:
            dst = safe_step(s, V, (2, 2), 4, goal, {(2, 2)}, s.groups[W], 3.0)
            self.assertNotIn(dst, s.humans)


class TestSplitterR(unittest.TestCase):
    def test_race_rollouts_and_root_plans_are_legal(self):
        from splitter.planner import race_plans, race_rollout_plan
        rng = random.Random(7)
        n = 0
        for _ in range(400):
            s = random_state(rng)
            for side in (V, W):
                if not s.groups[side]:
                    continue
                for strike in (0.0, 0.45):
                    moves = race_rollout_plan(s, side, rng, 0.15, strike)
                    ok, why = check_moves(s.rows, s.cols, s.groups[side], moves)
                    self.assertTrue(ok, f"{why}: {moves} in {s}")
                for p in race_plans(s, side):
                    n += 1
                    ok, why = check_moves(s.rows, s.cols, s.groups[side], p.moves)
                    self.assertTrue(ok, f"{why}: {p.tag} {p.moves} in {s}")
        self.assertGreater(n, 300)

    def test_fast_race_rollouts_match_the_reference(self):
        # race_rollout_plan is an optimized copy of this reference (_race_goals + _race_step):
        # same moves and same random draws, on every position
        from splitter.planner import MAX_CELL, _race_goals, _race_step, race_rollout_plan
        from splitter.rules import cheb, win_probability

        def reference(s, side, rng, eps, strike_p):
            mine, enemies, sources, moves = s.groups[side], s.groups[1 - side], set(s.groups[side]), {}
            for pos, cnt in sorted(mine.items(), key=lambda g: -g[1]):
                dst = None
                if strike_p > 0.0:
                    best = None
                    for ep, e in enemies.items():
                        if cheb(pos, ep) == 1 and cnt < 1.5 * e:
                            p = win_probability(cnt, e, False)
                            if p >= strike_p and (best is None or p * e > best[0]):
                                best = (p * e, ep)
                    if best is not None:
                        dst = best[1]
                if dst is None:
                    goals = _race_goals(s, pos, cnt, mine, enemies)
                    goal = goals[1][1] if len(goals) > 1 and rng.random() < eps else goals[0][1]
                    dst = _race_step(s, side, pos, cnt, goal, sources, enemies)
                if dst is not None:
                    moves[(pos, dst)] = moves.get((pos, dst), 0) + cnt
            out = tuple((a[0], a[1], n, d[0], d[1]) for (a, d), n in moves.items() if mine.get(d, 0) + n <= MAX_CELL)
            return out or fallback_plan(s, side).moves

        rng = random.Random(13)
        for i in range(500):
            s = random_state(rng)
            for side in (V, W):
                if s.groups[side]:
                    strike = 0.45 if i % 2 else 0.0
                    self.assertEqual(race_rollout_plan(s, side, random.Random(i), 0.15, strike),
                                     reference(s, side, random.Random(i), 0.15, strike), str(s))

    def test_bait_check_refuses_the_trap(self):
        # our 9 can kill the enemy 4 for sure, but an enemy 12 stands next to it: after the kill,
        # the 12 would strike our 9 at better than even odds
        s = State(6, 6, {}, {(1, 2): 9}, {(2, 2): 4, (3, 2): 12})
        def base_takes_bait(cfg):
            base = next(p for p in generate_plans(s, V, cfg) if p.tag == "base")
            return any((m[3], m[4]) == (2, 2) for m in base.moves)
        self.assertTrue(base_takes_bait(PlanConfig()))                    # the flagship walks into it
        self.assertFalse(base_takes_bait(PlanConfig(bait_check=True)))     # Splitter-R flees instead

    def test_strike_plan_offered_when_not_behind(self):
        # 13 vampires next to 10 werewolves: not a sure kill (13 < 15), but a strike wins 80%
        s = State(7, 7, {(0, 6): 2}, {(3, 3): 13}, {(4, 3): 10})
        strike = (3, 3, 13, 4, 3)
        self.assertFalse(any(strike in p.moves for p in generate_plans(s, V, PlanConfig())))
        plans = generate_plans(s, V, PlanConfig(strike_p=0.6))
        self.assertTrue(any(p.tag == "strike" and strike in p.moves for p in plans))
        # 11 vs 10 wins only 60%: below a 0.65 threshold, no strike plan
        s = State(7, 7, {(0, 6): 2}, {(3, 3): 11}, {(4, 3): 10})
        self.assertFalse(any(p.tag == "strike" for p in generate_plans(s, V, PlanConfig(strike_p=0.65))))
        rng = random.Random(17)
        for _ in range(300):
            s = random_state(rng)
            for side in (V, W):
                if s.groups[side]:
                    for p in generate_plans(s, side, PlanConfig(strike_p=0.55)):
                        ok, why = check_moves(s.rows, s.cols, s.groups[side], p.moves)
                        self.assertTrue(ok, f"{why}: {p.tag} {p.moves}")


class TestSplits(unittest.TestCase):
    def test_split_generated_for_two_small_houses(self):
        # 10 vampires, houses of 3 on both sides, enemy far away -> a 3 + 3 (+4) split must exist
        s = State(9, 15, {(3, 2): 3, (3, 6): 3}, {(5, 4): 10}, {(14, 8): 10})
        plans = generate_plans(s, V)
        splits = [p for p in plans if p.tag.startswith("split")]
        self.assertTrue(splits, [p.tag for p in plans])
        two = [p for p in splits if p.tag.startswith("split2")]
        self.assertTrue(two)
        self.assertTrue(any({m[2] for m in p.moves} >= {3} for p in two))

    def test_no_split_when_disabled(self):
        s = State(9, 15, {(3, 2): 3, (3, 6): 3}, {(5, 4): 10}, {(14, 8): 10})
        for p in generate_plans(s, V, PlanConfig(splits=False)):
            srcs = {}
            for m in p.moves:
                srcs.setdefault((m[0], m[1]), set()).add((m[3], m[4]))
            self.assertTrue(all(len(d) == 1 for d in srcs.values()), p)

    def test_detachment_safety(self):
        enemy = {(6, 2): 5}
        # 3 creatures walking to a house next to an enemy group of 5: dead (5 >= 3, and 5 >= 1.5*... )
        self.assertFalse(detachment_safe((2, 2), 3, (5, 2), 3, enemy))
        # same detachment, enemy far away: fine
        self.assertTrue(detachment_safe((2, 2), 3, (4, 2), 3, {(14, 8): 5}))
        # enemy smaller than the detachment: fine (it attacks at < 50%)
        self.assertTrue(detachment_safe((2, 2), 3, (4, 2), 3, {(6, 2): 2}))

    def test_unsafe_house_not_split_to(self):
        # the only house is right next to a big enemy: no detachment may go there
        s = State(9, 15, {(9, 4): 2}, {(5, 4): 10}, {(10, 4): 9})
        for p in generate_plans(s, V):
            self.assertFalse(p.tag.startswith("split"), p)


if __name__ == "__main__":
    unittest.main()
