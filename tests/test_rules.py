"""Rules = the real server's behaviour (docs/SERVER_FINDINGS.md). Run: python -m unittest discover tests"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from splitter.rules import V, W, check_moves, resolve_battle, win_probability
from splitter.state import State


class TestProbability(unittest.TestCase):
    def test_server_formula(self):
        self.assertEqual(win_probability(5, 5, False), 0.5)
        self.assertEqual(win_probability(5, 5, True), 0.5)
        self.assertAlmostEqual(win_probability(6, 10, False), 0.3)       # E1 < E2
        self.assertAlmostEqual(win_probability(12, 10, False), 0.7)      # E2 < E1 < 1.5 E2
        self.assertEqual(win_probability(15, 10, False), 1.0)            # 1.5x exactly
        self.assertAlmostEqual(win_probability(4, 9, True), 4 / 18)

    def test_defender_1_5x_is_random_not_sure(self):
        # server: 6 attacking 10 is a random battle (the PDF says the attackers all die)
        rng = random.Random(0)
        wins = sum(resolve_battle(6, 10, False, "sample", rng)[0] for _ in range(4000))
        self.assertAlmostEqual(wins / 4000, 0.3, delta=0.03)

    def test_sure_results(self):
        self.assertEqual(resolve_battle(3, 3, True), (True, 6))            # convert all
        self.assertEqual(resolve_battle(15, 10, False), (True, 15))        # no losses
        win, n = resolve_battle(4, 9, True, "sample", random.Random(1))
        if not win:
            self.assertLessEqual(n, 9)                                     # attackers all dead


class TestCheckMoves(unittest.TestCase):
    def setUp(self):
        self.mine = {(2, 2): 10, (5, 5): 3}

    def ok(self, moves):
        return check_moves(5, 10, self.mine, moves)[0]

    def test_legal_split(self):
        self.assertTrue(self.ok([(2, 2, 3, 1, 1), (2, 2, 3, 3, 1)]))

    def test_cheats(self):
        self.assertFalse(self.ok([]))                                       # empty MOV
        self.assertFalse(self.ok([(2, 2, 11, 2, 3)]))                       # too many
        self.assertFalse(self.ok([(2, 2, 6, 2, 3), (2, 2, 5, 3, 3)]))       # sum too big
        self.assertFalse(self.ok([(0, 0, 1, 1, 1)]))                        # not ours
        self.assertFalse(self.ok([(2, 2, 1, 4, 2)]))                        # 2 steps
        self.assertFalse(self.ok([(2, 2, 1, 2, 2)]))                        # no move
        self.assertFalse(self.ok([(2, 2, 0, 2, 3)]))                        # zero
        # rule 5: (2,3) is a target and a source
        self.mine[(2, 3)] = 4
        self.assertFalse(self.ok([(2, 2, 5, 2, 3), (2, 3, 4, 2, 4)]))
        # off the board (the server does not check: it would crash)
        self.assertFalse(check_moves(5, 10, {(9, 4): 2}, [(9, 4, 1, 10, 4)])[0])

    def test_byte_overflow_refused(self):
        self.assertFalse(check_moves(5, 10, {(1, 1): 200, (2, 1): 100}, [(1, 1, 200, 2, 1)])[0])


class TestApply(unittest.TestCase):
    def test_probe1_split_and_merged_attack(self):
        # replay of the real-server probe "rules" (tools/probe_server.py)
        s = State(5, 10, {(1, 1): 3, (3, 1): 3, (1, 3): 9, (7, 0): 5}, {(2, 2): 10}, {(7, 2): 10})
        s = s.apply(V, [(2, 2, 3, 1, 1), (2, 2, 3, 3, 1)])
        self.assertEqual(s.groups[V], {(1, 1): 6, (3, 1): 6, (2, 2): 4})
        s = s.apply(W, [(7, 2, 3, 6, 1), (7, 2, 3, 8, 1)])
        s = s.apply(W, [(6, 1, 3, 7, 0), (8, 1, 3, 7, 0)])                 # 3 + 3 summed vs 5
        self.assertEqual(s.groups[W][(7, 0)], 11)
        self.assertNotIn((7, 0), s.humans)

    def test_sure_kill_and_merge(self):
        s = State(5, 10, {}, {(2, 2): 15, (2, 3): 1}, {(3, 2): 10})
        s = s.apply(V, [(2, 2, 15, 3, 2)])
        self.assertEqual(s.groups[V], {(3, 2): 15, (2, 3): 1})
        self.assertEqual(s.groups[W], {})
        s = s.apply(V, [(2, 3, 1, 3, 2)])                                   # merge into own cell
        self.assertEqual(s.groups[V], {(3, 2): 16})

    def test_mean_mode_deterministic(self):
        s = State(5, 10, {(1, 1): 9}, {(2, 2): 4}, {(8, 4): 3})
        a = s.apply(V, [(2, 2, 4, 1, 1)], mode="mean")
        b = s.apply(V, [(2, 2, 4, 1, 1)], mode="mean")
        self.assertEqual(a.key(), b.key())


if __name__ == "__main__":
    unittest.main()
