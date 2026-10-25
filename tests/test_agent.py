"""SplitterAgent: tactical puzzles, the time budget and the never-illegal guarantee."""
import os
import random
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arena.maps import load_xml
from splitter.agent import MODELS, SplitterAgent
from splitter.rules import V, W, cheb, check_moves
from splitter.state import State


def agent(t=0.4, **kw):
    return SplitterAgent(time_limit=t, seed=1, game_seconds=None, **kw)


def takes_both_houses(model) -> bool:
    """6 vampires between two houses of 3, enemy far away: split 3 + 3 and take both at once."""
    s = State(9, 15, {(3, 4): 3, (5, 4): 3}, {(4, 4): 6}, {(14, 0): 6})
    dests = {(m[3], m[4]): m[2] for m in agent(0.6, **model).choose(s, V, 0)}
    return dests.get((3, 4)) == 3 and dests.get((5, 4)) == 3


def enters_together(model) -> bool:
    """6 + 6 vampires next to a house of 10: only a synchronized entry converts it."""
    s = State(9, 15, {(5, 4): 10}, {(4, 3): 6, (6, 5): 6}, {(14, 0): 8})
    dests: dict = {}
    for m in agent(0.6, **model).choose(s, V, 20):
        dests[(m[3], m[4])] = dests.get((m[3], m[4]), 0) + m[2]
    return dests.get((5, 4)) == 12


class TestPuzzles(unittest.TestCase):
    """The tactical puzzles; each is solved by both kept models unless marked otherwise."""

    def test_takes_the_sure_kill(self):
        # 12 vampires next to the only werewolf group of 8: 12 >= 1.5 * 8 -> win the game now
        s = State(7, 7, {(0, 6): 3}, {(3, 3): 12}, {(4, 3): 8})
        for model, kw in MODELS.items():
            with self.subTest(model=model):
                self.assertIn((3, 3, 12, 4, 3), agent(**kw).choose(s.copy(), V, 10))

    def test_does_not_suicide_or_wait_next_to_a_killer(self):
        # 4 vampires next to 10 werewolves who move next: run (never attack, never stay adjacent)
        s = State(9, 9, {(8, 8): 2}, {(4, 4): 4}, {(5, 4): 10})
        for model, kw in MODELS.items():
            with self.subTest(model=model):
                moves = agent(**kw).choose(s.copy(), V, 10)
                self.assertTrue(moves)
                for _, _, _, x2, y2 in moves:
                    self.assertNotEqual((x2, y2), (5, 4))
                    self.assertGreater(cheb((x2, y2), (5, 4)), 1, moves)

    def test_splits_to_take_two_adjacent_houses(self):
        self.assertTrue(takes_both_houses(MODELS["backup"]))

    def test_does_not_offer_a_desperate_opponent_a_shot(self):
        # stage-2 loss (ho_11x11, ply 33): 40 vampires lead 40 to 26, no humans left. Stepping next
        # to the 17 lets them strike first at 21%, which a losing bot takes: it wiped us out.
        # Only the flagship models the desperate opponent (desperate_p)
        s = State(11, 11, {}, {(5, 3): 40}, {(5, 5): 17, (8, 2): 9}, 32)
        moves = agent(0.4, **MODELS["flagship"]).choose(s.copy(), V)
        for _, _, _, x2, y2 in moves:
            self.assertTrue(all(cheb((x2, y2), e) > 1 for e in s.groups[W]), moves)

    def test_converges_two_groups_on_a_big_house(self):
        self.assertTrue(enters_together(MODELS["backup"]))

    @unittest.expectedFailure
    def test_flagship_tempo_puzzles(self):
        # KNOWN WEAKNESS of the flagship (chapter 16.9): when far ahead, desperate_p makes the tree
        # expect a low-odds strike from the enemy, and our own planned follow-up still chases it,
        # so lines that convert at once look riskier: it converts one house now and one later.
        # An "unexpected success" here means the weakness is fixed: move these into the tests above.
        self.assertTrue(takes_both_houses(MODELS["flagship"]) or enters_together(MODELS["flagship"]))


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

    def test_flagship_model_never_illegal(self):
        rng = random.Random(5)
        a = SplitterAgent(time_limit=0.03, seed=2, game_seconds=None, **MODELS["flagship"])
        self.assertEqual((a.mcts.rollout_policy, a.desperate_p, a.cfg.strike_p), ("race", 0.1, 0.6))
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

    def test_splitter_r_options_never_illegal(self):
        rng = random.Random(9)
        a = SplitterAgent(time_limit=0.05, seed=4, game_seconds=None, rollout_policy="race", rollout_strike=0.45,
                          rollout_depth_contact=6, leaf_mix=0.5, race_root=True, bait_check=True,
                          strike_p=0.55, desperate_p=0.1)
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
            self.assertEqual((engine.desperate_p, engine.cfg.strike_p, engine.mcts.rollout_policy), (0.0, 0.0, "quick"))
            os.environ.pop("SPLITTER_MODEL")                 # the default is the flagship
            engine = AIAgent("x", time_limit=0.05).engine
            assert engine is not None
            self.assertEqual((engine.desperate_p, engine.cfg.strike_p, engine.mcts.rollout_policy), (0.1, 0.6, "race"))
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

    def test_splitter_options_never_cost_the_engine(self):
        # SPLITTER_OPTIONS (testing a candidate under real conditions) adds options to the model;
        # a bad value is ignored with a warning: the tournament bot never falls back to the starter
        from ai_agent import AIAgent
        old = os.environ.get("SPLITTER_OPTIONS")
        try:
            os.environ["SPLITTER_OPTIONS"] = "keep_away=true,strike_p=0.6"
            engine = AIAgent("x", time_limit=0.05).engine
            assert engine is not None
            self.assertEqual((engine.keep_away, engine.desperate_p), (True, 0.1))
            os.environ["SPLITTER_OPTIONS"] = "not_an_option=1,broken"
            engine = AIAgent("x", time_limit=0.05).engine
            assert engine is not None
            self.assertEqual((engine.keep_away, engine.mcts.rollout_policy), (False, "race"))
        finally:
            if old is None:
                os.environ.pop("SPLITTER_OPTIONS", None)
            else:
                os.environ["SPLITTER_OPTIONS"] = old

    def test_watchdog_sends_the_best_plan_so_far_when_late(self):
        # a search that would take 1.0 s behind a 0.3 s watchdog: the late answer is the search's
        # current best plan (legal), not the naive fallback step; nothing is offered afterwards
        import main
        from ai_agent import AIAgent
        s = load_xml("testmap.xml")
        gs = s.to_game_state(W, home=(0, 0))
        ai = AIAgent("T", time_limit=1.0)
        dog = main.Watchdog(0.3)
        moves = dog.decide(ai, gs, time.time())
        self.assertEqual(dog.late, 1)
        assert moves, moves
        self.assertTrue(check_moves(s.rows, s.cols, s.groups[W], moves)[0], moves)
        worker = dog.worker
        assert worker is not None
        worker.join(3.0)
        self.assertFalse(worker.is_alive())
        self.assertIsNone(ai.anytime_moves())          # no decision in progress any more

    def test_gamestate_interface(self):
        from ai_agent import AIAgent
        s = load_xml("testmap.xml")
        gs = s.to_game_state(W, home=(0, 0))
        moves = AIAgent("T", time_limit=0.2).compute_moves(gs)
        self.assertTrue(check_moves(s.rows, s.cols, s.groups[W], moves)[0], moves)


if __name__ == "__main__":
    unittest.main()
