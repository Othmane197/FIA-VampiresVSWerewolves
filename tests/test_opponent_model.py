"""Opponent model: observation reconstruction, HMM maths, online inference, integration safety."""
import itertools
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from splitter.agent import SplitterAgent
from splitter.observe import ATTACK_LONG, HEAD_HOUSE, OpponentTracker, features_from_flows, reconstruct_flows
from splitter.opponent_model import (
    EXPERTS,
    GoalRecognizer,
    K,
    PolicyHMM,
    StyleHMM,
    baum_welch,
    default_params,
    greedy_steps,
    sequence_loglik,
)
from splitter.rules import V, W, check_moves
from splitter.state import State


def flows_of(moves):
    return [((m[0], m[1]), (m[3], m[4]), m[2]) for m in moves]


class TestObservation(unittest.TestCase):
    def check(self, mid, mover, moves):
        after = mid.apply(mover, moves, mode="mean")
        truth = features_from_flows(mid, mover, flows_of(moves)).vector()
        recon = features_from_flows(mid, mover, reconstruct_flows(mid, after, mover)).vector()
        self.assertEqual(truth, recon, (moves, reconstruct_flows(mid, after, mover)))
        return truth

    def test_plain_split_conversion(self):
        mid = State(9, 9, {(2, 2): 3, (2, 4): 3}, {(7, 7): 8}, {(3, 3): 10})
        f = self.check(mid, W, [(3, 3, 3, 2, 2), (3, 3, 3, 2, 4)])   # split onto two houses of 3
        self.assertEqual(f[0], 1)
        self.assertEqual(f[3], 1)
        self.assertEqual(f[2], HEAD_HOUSE)

    def test_crossing_sources_are_not_a_split(self):
        # two groups of 2 and 4 swap columns: the reconstruction must not invent a split
        mid = State(10, 10, {}, {(0, 0): 9}, {(4, 8): 2, (4, 9): 4})
        f = self.check(mid, W, [(4, 8, 2, 3, 9), (4, 9, 4, 3, 8)])
        self.assertEqual(f[0], 0)

    def test_long_shot_attack(self):
        mid = State(9, 9, {}, {(4, 4): 10}, {(5, 4): 4})
        f = features_from_flows(mid, W, flows_of([(5, 4, 4, 4, 4)])).vector()
        self.assertEqual(f[1], ATTACK_LONG)

    def test_tracker_end_to_end(self):
        t = OpponentTracker()
        s0 = State(9, 9, {(1, 1): 3}, {(4, 4): 6}, {(8, 8): 6})
        our = [(4, 4, 6, 3, 3)]
        t.note_our_move(s0, V, our)
        s1 = s0.apply(V, our, mode="mean").apply(W, [(8, 8, 6, 7, 7)], mode="mean")
        obs = t.observe(s1)
        self.assertIsNotNone(obs)
        self.assertEqual(sorted(obs.flows), [((8, 8), (7, 7), 6)])


class TestHMM(unittest.TestCase):
    def test_forward_matches_brute_force(self):
        p = default_params()
        seq = [((0, 0, 1, 1), 0), ((1, 0, 1, 0), 0), ((0, 3, 0, 0), 1)]
        brute = 0.0
        for path in itertools.product(range(K), repeat=len(seq)):
            pr = p["pi"][path[0]]
            for t, z in enumerate(path):
                if t:
                    pr *= p["A"][seq[t][1]][path[t - 1]][z]
                for f, v in enumerate(seq[t][0]):
                    pr *= p["B"][f][z][v]
            brute += pr
        self.assertAlmostEqual(sequence_loglik(p, seq), math.log(brute), places=9)

    def test_baum_welch_improves_likelihood(self):
        rng = random.Random(1)
        p = default_params()
        seqs = []
        for _ in range(30):
            z = rng.randrange(K)
            seq = []
            for _ in range(25):
                obs = tuple(rng.choices(range(len(p["B"][f][z])), weights=p["B"][f][z])[0] for f in range(4))
                seq.append((obs, 0))
            seqs.append(seq)
        _, hist = baum_welch(seqs, p, iters=15)
        self.assertGreater(hist[-1], hist[0])
        for a, b in zip(hist, hist[1:]):
            self.assertGreater(b, a - 1e-3 * abs(a))

    def test_style_belief_recovers_a_splitter(self):
        p = default_params()
        hmm = StyleHMM(p)
        for _ in range(12):
            hmm.update((1, 0, 1, 1), 0)          # splits and converts every turn
        self.assertEqual(max(hmm.mode_probs(), key=hmm.mode_probs().get), "SPLITFARM")

    def test_goal_recognition_straight_walk(self):
        g = GoalRecognizer()
        pos = (0, 4)
        state = State(9, 12, {(8, 4): 3, (0, 0): 3}, {(11, 8): 4}, {pos: 5})
        for _ in range(3):
            nxt = (pos[0] + 1, pos[1])
            after = State(9, 12, state.humans, state.groups[V], {nxt: 5})
            g.update(state, after, W, [(pos, nxt, 5)])
            pos, state = nxt, after
        pred = g.predict(state, W)[pos]
        self.assertEqual(pred.targets[0][0], ("H", (8, 4)))
        self.assertEqual(pred.next_cell(), (pos[0] + 1, pos[1]))

    def test_policy_hmm_identifies_greedy_opponent(self):
        goals = GoalRecognizer()
        pol = PolicyHMM(goals)
        s = State(12, 12, {(2, 9): 2, (9, 2): 3, (6, 6): 4}, {(0, 0): 5}, {(11, 11): 6})
        for _ in range(6):
            dists = pol.expert_dists(s, W)
            steps = greedy_steps(s, W)
            pol.update(dists, steps)
            moves = [(p[0], p[1], s.groups[W][p], d[0], d[1]) for p, d in steps.items() if d != p]
            if not moves:
                break
            after = s.apply(W, moves, mode="mean")
            goals.update(s, after, W, flows_of(moves))
            s = after
        self.assertEqual(EXPERTS[max(range(len(EXPERTS)), key=lambda e: pol.belief[e])], "GREEDY")


class TestIntegration(unittest.TestCase):
    def test_agent_with_model_never_illegal(self):
        rng = random.Random(5)
        a = SplitterAgent(time_limit=0.03, seed=2, game_seconds=None, opponent_model=True)
        s = State(9, 12, {(2, 2): 3, (9, 6): 2, (5, 1): 4}, {(0, 8): 9}, {(11, 0): 9})
        for ply in range(30):
            side = V if ply % 2 == 0 else W
            if side == V:
                moves = a.choose(s.copy(), V, ply)
                self.assertTrue(check_moves(s.rows, s.cols, s.groups[V], moves)[0], moves)
                self.assertIsNone(a.last_error, a.last_error)
            else:
                from splitter.planner import generate_plans
                plans = generate_plans(s, W)
                moves = list(rng.choice(plans).moves)
            s = s.apply(side, moves, rng)
            if s.is_terminal():
                break


if __name__ == "__main__":
    unittest.main()
