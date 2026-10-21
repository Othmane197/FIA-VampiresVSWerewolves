"""SplitterAgent: tactical puzzles, the time budget and the never-illegal guarantee."""
import os
import random
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arena.maps import load_xml
from splitter.agent import SplitterAgent
from splitter.rules import V, W, cheb, check_moves
from splitter.state import State


def agent(t=0.4, **kw):
    return SplitterAgent(time_limit=t, seed=1, game_seconds=None, **kw)


class TestPuzzles(unittest.TestCase):
    def test_takes_the_sure_kill(self):
        # 12 vampires next to the only werewolf group of 8: 12 >= 1.5 * 8 -> win the game now
        s = State(7, 7, {(0, 6): 3}, {(3, 3): 12}, {(4, 3): 8})
        moves = agent().choose(s, V, 10)
        self.assertIn((3, 3, 12, 4, 3), moves)

    def test_does_not_suicide_or_wait_next_to_a_killer(self):
        # 4 vampires next to 10 werewolves who move next: run (never attack, never stay adjacent)
        s = State(9, 9, {(8, 8): 2}, {(4, 4): 4}, {(5, 4): 10})
        moves = agent().choose(s, V, 10)
        self.assertTrue(moves)
        for _, _, _, x2, y2 in moves:
            self.assertNotEqual((x2, y2), (5, 4))
            self.assertGreater(cheb((x2, y2), (5, 4)), 1, moves)

    def test_splits_to_take_two_adjacent_houses(self):
        # 6 vampires between two houses of 3, enemy far away: take both at once
        s = State(9, 15, {(3, 4): 3, (5, 4): 3}, {(4, 4): 6}, {(14, 0): 6})
        moves = agent(0.6).choose(s, V, 0)
        dests = {(m[3], m[4]): m[2] for m in moves}
        self.assertEqual(dests.get((3, 4)), 3, moves)
        self.assertEqual(dests.get((5, 4)), 3, moves)

    def test_converges_two_groups_on_a_big_house(self):
        # 6 + 6 vampires next to a house of 10: only a synchronized entry converts it
        s = State(9, 15, {(5, 4): 10}, {(4, 3): 6, (6, 5): 6}, {(14, 0): 8})
        moves = agent(0.6).choose(s, V, 20)
        dests = {}
        for m in moves:
            dests[(m[3], m[4])] = dests.get((m[3], m[4]), 0) + m[2]
        self.assertEqual(dests.get((5, 4)), 12, moves)


class TestSafety(unittest.TestCase):
    def test_time_budget_big_map(self):
        s = load_xml("testmap.xml")
        a = agent(0.5)
        t0 = time.perf_counter()
        moves = a.choose(s, V, 0)
        self.assertLess(time.perf_counter() - t0, 0.6)
        self.assertTrue(check_moves(s.rows, s.cols, s.groups[V], moves)[0])

    def test_fuzz_never_illegal(self):
        rng = random.Random(3)
        a = agent(0.03)
        for i in range(60):
            rows, cols = rng.randint(3, 12), rng.randint(3, 16)
            cells = rng.sample([(x, y) for x in range(cols) for y in range(rows)], min(rows * cols, 9))
            s = State(rows, cols, {c: rng.randint(1, 20) for c in cells[2:5]},
                      {cells[0]: rng.randint(1, 40), **({cells[5]: rng.randint(1, 9)} if i % 2 else {})},
                      {cells[1]: rng.randint(1, 40), **({cells[6]: rng.randint(1, 9)} if i % 3 else {})},
                      rng.randint(0, 190))
            for side in (V, W):
                moves = a.choose(s.copy(), side)
                ok, why = check_moves(s.rows, s.cols, s.groups[side], moves)
                self.assertTrue(ok, f"{why} {moves} {s}")
                self.assertIsNone(a.last_error, a.last_error)

    def test_backup_model_never_illegal(self):
        from splitter.agent import MODELS
        rng = random.Random(5)
        a = SplitterAgent(time_limit=0.03, seed=2, game_seconds=None, **MODELS["backup"])
        self.assertEqual((a.ev.discount, a.ev.k0, a.ev.k1), (0.845, 8.5, 27.0))
        for i in range(40):
            rows, cols = rng.randint(3, 12), rng.randint(3, 16)
            cells = rng.sample([(x, y) for x in range(cols) for y in range(rows)], min(rows * cols, 9))
            s = State(rows, cols, {c: rng.randint(1, 20) for c in cells[2:5]} if i % 4 else {},
                      {cells[0]: rng.randint(1, 40), **({cells[5]: rng.randint(1, 9)} if i % 2 else {})},
                      {cells[1]: rng.randint(1, 40), **({cells[6]: rng.randint(1, 9)} if i % 3 else {})},
                      rng.randint(0, 190))
            for side in (V, W):
                moves = a.choose(s.copy(), side)
                ok, why = check_moves(s.rows, s.cols, s.groups[side], moves)
                self.assertTrue(ok, f"{why} {moves} {s}")
                self.assertIsNone(a.last_error, a.last_error)

    def test_tournament_client_selects_the_model(self):
        from ai_agent import AIAgent
        old = os.environ.get("SPLITTER_MODEL")
        try:
            os.environ["SPLITTER_MODEL"] = "backup"
            engine = AIAgent("x", time_limit=0.05).engine
            assert engine is not None
            self.assertEqual(engine.ev.k1, 27.0)
            os.environ["SPLITTER_MODEL"] = "flagship"
            engine = AIAgent("x", time_limit=0.05).engine
            assert engine is not None
            self.assertEqual(engine.ev.k1, 14.0)
        finally:
            if old is None:
                os.environ.pop("SPLITTER_MODEL", None)
            else:
                os.environ["SPLITTER_MODEL"] = old

    def test_watchdog_sends_the_fallback_when_late(self):
        import main

        class Slow:
            def __init__(self):
                self.calls = 0

            def compute_moves(self, _state):
                self.calls += 1
                time.sleep(0.5)
                return [(0, 0, 1, 1, 1)]

        slow = Slow()
        dog = main.Watchdog(0.2)
        self.assertIsNone(dog.decide(slow, None, time.time()))     # too late -> fallback
        self.assertIsNone(dog.decide(slow, None, time.time()))     # still running: not called again
        self.assertEqual(slow.calls, 1)
        time.sleep(0.4)
        dog.limit = 2.0
        self.assertEqual(dog.decide(slow, None, time.time()), [(0, 0, 1, 1, 1)])
        self.assertEqual(dog.late, 1)

    def test_gamestate_interface(self):
        from ai_agent import AIAgent
        s = load_xml("testmap.xml")
        gs = s.to_game_state(W, home=(0, 0))
        moves = AIAgent("T", time_limit=0.2).compute_moves(gs)
        self.assertTrue(check_moves(s.rows, s.cols, s.groups[W], moves)[0], moves)


if __name__ == "__main__":
    unittest.main()
