"""Testing infrastructure: external bots (Python files, any program), kept variants, stored results."""
import csv
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from arena import run
from arena.maps import build_suite
from arena.opponents import BoardBot, GameStateBot, SplitterBot, make_bot
from arena.referee import play_game
from splitter.rules import V, W

GAMESTATE_BOT = '''
class WalkerBot:
    """External bot with the repo interface: compute_moves(GameState)."""
    def __init__(self, name="Walker"):
        self.name = name

    def compute_moves(self, state):
        (x, y), n = max(state.get_our_groups(), key=lambda g: g[1])
        for nx, ny in state.get_legal_adjacent_cells((x, y)):
            return [(x, y, n, nx, ny)]
'''

BOARD_BOT = '''
class BoardWalker:
    """External bot with Othmane's interface: compute_moves(BoardState, Species)."""
    def compute_moves(self, board, species):
        (x, y), n = max(board.get_species_groups(species), key=lambda g: g[1])
        nx, ny = board.get_neighbors((x, y))[0]
        return [(x, y, n, nx, ny)]
'''


class TestExternalBots(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.gs_path = os.path.join(self.tmp.name, "walker_bot.py")
        self.bd_path = os.path.join(self.tmp.name, "board_bot.py")
        with open(self.gs_path, "w") as f:
            f.write(GAMESTATE_BOT)
        with open(self.bd_path, "w") as f:
            f.write(BOARD_BOT)

    def tearDown(self):
        self.tmp.cleanup()

    def test_python_file_bots_are_loaded_and_play(self):
        gs_bot = make_bot(f"py:{self.gs_path}")
        bd_bot = make_bot(f"py:{self.bd_path}:BoardWalker")
        self.assertIsInstance(gs_bot, GameStateBot)
        self.assertIsInstance(bd_bot, BoardBot)
        state = dict(build_suite("thetrap"))["thetrap"]
        state.max_ply = 20
        r = play_game(state, {V: gs_bot, W: bd_bot}, seed=1)
        self.assertNotIn(r.reason, ("crash", "illegal"), (r.stats[V].problem, r.stats[W].problem))

    def test_arena_task_against_a_file_bot_stores_its_files(self):
        # the spec contains ':' and path separators: every file name built from it must stay valid
        spec = f"py:{self.gs_path}:WalkerBot"
        logs, traces = os.path.join(self.tmp.name, "logs"), os.path.join(self.tmp.name, "traces")
        row = run._play_task(("Splitter", spec, "thetrap", "given", V, V, 3, 0.05, 1.0, 12, logs, traces))
        self.assertEqual(row["opp"], spec)
        self.assertEqual(len(os.listdir(traces)), 1)
        self.assertEqual(row["our_crashes"] + row["our_illegal"], 0)


class TestVariants(unittest.TestCase):
    def test_flagship_and_backup(self):
        flagship = make_bot("Splitter", 0.05)
        backup = make_bot("Splitter-Classic", 0.05)
        assert isinstance(flagship, SplitterBot) and isinstance(backup, SplitterBot)
        self.assertEqual(flagship.agent.mcts.rollout_policy, "race")     # Splitter-R3 (chapter 16)
        self.assertEqual(backup.agent.mcts.rollout_policy, "quick")      # the campaign-2 flagship
        state = dict(build_suite("thetrap"))["thetrap"]
        state.max_ply = 16
        r = play_game(state, {V: backup, W: flagship}, seed=2)
        self.assertNotIn(r.reason, ("crash", "illegal"))
        self.assertIsNone(backup.agent.last_error, backup.agent.last_error)

    def test_styled_opponents_are_reproducible(self):
        from arena.opponents import styled_config
        self.assertEqual(styled_config(3), styled_config(3))
        self.assertNotEqual(styled_config(3), styled_config(4))
        self.assertIsInstance(make_bot("Styled:3", 0.05), SplitterBot)

    def test_unknown_option_is_refused(self):
        with self.assertRaises(TypeError):
            make_bot("Splitter:not_an_option=1", 0.05)


class TestResultStoring(unittest.TestCase):
    def test_history_and_comparisons_are_appended(self):
        tmp = tempfile.TemporaryDirectory()
        old = run.HISTORY, run.COMPARISONS
        run.HISTORY = os.path.join(tmp.name, "history.csv")
        run.COMPARISONS = os.path.join(tmp.name, "comparisons.csv")
        try:
            rows = [{"bot": b, "opp": "X", "map": "m", "side": "V", "seed": s, "score": sc, "our_timeouts": 0,
                     "our_illegal": 0, "our_crashes": 0}
                    for b, sc in (("A", 1.0), ("B", 0.0)) for s in (1, 2)]

            class Args:
                maps, games, time, seed = "given", 1, 0.1, 1
            comps = run.compare(rows, ["A", "B"])
            run.store_history("test-run", ["A", "B"], ["X"], Args, rows, comps)
            with open(run.HISTORY) as f:
                hist = list(csv.DictReader(f))
            with open(run.COMPARISONS) as f:
                comp = list(csv.DictReader(f))
            self.assertEqual([h["bot"] for h in hist], ["A", "B"])
            self.assertEqual(float(comp[0]["delta"]), -100.0)
        finally:
            run.HISTORY, run.COMPARISONS = old
            tmp.cleanup()


class TestFasterBenchmarks(unittest.TestCase):
    def test_rounds_keep_the_pairs_together(self):
        tasks = [(b, opp, mp, "given", side, 0, 7, 0.1, 1.0, 50, None, None)
                 for opp in ("A", "B") for mp in ("m1", "m2", "m3") for side in (V, W) for b in ("x", "y")]
        rounds = run._rounds(tasks, 4)
        self.assertEqual(sum(len(r) for r in rounds), len(tasks))
        for r in rounds:                  # both bots of every game are in the same round
            games = {(t[1], t[2], t[4]) for t in r}
            self.assertEqual(len(r), 2 * len(games))

    def test_paired_delta_and_drop_rule(self):
        rows = [{"bot": b, "opp": "o", "map": "m", "side": "V", "first": "V", "seed": s,
                 "score": 1.0 if b == "ref" else (0.0 if s % 4 else 1.0)} for b in ("ref", "bad") for s in range(40)]
        m, se, n = run.paired_delta(rows, "ref", "bad")
        self.assertEqual(n, 40)
        self.assertAlmostEqual(m, -0.75)
        self.assertLess(m + 2 * se, 0)    # --drop-worse would stop this candidate

    def test_informative_slots_skip_games_nobody_disagrees_on(self):
        import json

        from tools import informative_slots as islots
        tmp = tempfile.TemporaryDirectory()
        path = os.path.join(tmp.name, "run.csv")
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["bot", "opp", "map", "side", "first", "seed", "score", "plies",
                                              "our_timeouts", "opp_problems"])
            w.writeheader()
            for b in ("ref", "c1", "c2"):
                for s in range(4):
                    w.writerow({"bot": b, "opp": "Easy", "map": "m", "side": "V", "first": "V", "seed": s,
                                "score": 1.0, "plies": 100, "our_timeouts": 0, "opp_problems": 0})
                    w.writerow({"bot": b, "opp": "Hard", "map": "m", "side": "V", "first": "V", "seed": s,
                                "score": float((s + len(b)) % 2), "plies": 100, "our_timeouts": 0,
                                "opp_problems": 0})
        keep, info, cost = islots.select(islots.slot_information([path]), 0.9)
        self.assertEqual(keep, [["Hard", "m"]])
        self.assertEqual(info, 1.0)
        self.assertAlmostEqual(cost, 0.5)
        self.assertTrue(json.dumps(keep))
        tmp.cleanup()


class TestTeammateMatches(unittest.TestCase):
    def test_real_conditions_script_plays_and_records(self):
        tmp = tempfile.TemporaryDirectory()
        cmd = [sys.executable, os.path.join(ROOT, "tools", "teammate_matches.py"), "--opp", "Starter",
               "--games", "2", "--maps", "thetrap.xml", "--max-ply", "10", "--time", "0.2", "--opp-time", "0.2",
               "--out", tmp.name, "--no-history"]
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=300, check=False)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        with open(os.path.join(tmp.name, "games.csv")) as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)
        self.assertEqual([r["our_species"] for r in rows], ["Vampires", "Werewolves"])   # order alternates
        self.assertTrue(all(r["cheat"] == "" and r["our_timeouts"] == "0" for r in rows))
        self.assertTrue(os.path.exists(os.path.join(tmp.name, "summary.md")))
        tmp.cleanup()

    def test_schedule_covers_every_map_and_side(self):
        from tools.teammate_matches import schedule
        maps = ["testmap.xml", "thetrap.xml"]
        self.assertEqual([schedule(g, maps) for g in range(4)],
                         [("testmap.xml", True), ("thetrap.xml", True), ("testmap.xml", False), ("thetrap.xml", False)])


class TestServerMatch(unittest.TestCase):
    def test_two_programs_play_over_the_protocol(self):
        env = dict(os.environ, SPLITTER_TIME="0.2")
        cmd = [sys.executable, os.path.join(ROOT, "tools", "server_match.py"),
               "--a", f'"{sys.executable}" main.py --name Flagship {{host}} {{port}}',
               "--b", f'"{sys.executable}" main.py --name Other {{host}} {{port}}',
               "--maps", "thetrap", "--max-ply", "12", "--no-store"]
        out = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=300, check=False)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        self.assertIn("over 2 games", out.stdout)
        self.assertIn("cheats: 0", out.stdout)


if __name__ == "__main__":
    unittest.main()
