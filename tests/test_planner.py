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
