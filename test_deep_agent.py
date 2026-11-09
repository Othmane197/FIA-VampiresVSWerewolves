"""
test_deep_agent.py  (our own file)

1. every turn DeepAgent's generator proposes is accepted by the official rules (server_rules.check_moves),
   on positions taken from real self-play games on the whole map suite;
2. apply_turn gives the same board as the official perform_moves whenever no random battle happens,
   and probabilities that sum to 1 otherwise;
3. the agent answers within its budget and its answer passes the gate.
"""
import random
import time

from deep_agent import DeepAgent, Geometry, Params, apply_turn, gen_turns, state_from_game
from game_engine import BoardState
from game_state import Species
from maps import build_suite
from selfplay import play_game
from server_rules import check_moves, perform_moves
from sparring_agents import make_opponent
from state_converter import state_from_board

SP = [Species.VAMPIRE, Species.WEREWOLF]


def to_board(S, rows, cols):
    b = BoardState(rows, cols)
    for pos, n in S[0]:
        b.set_cell(pos, b.get_cell(pos)[0], n, 0)
    for pos, n in S[1]:
        h, v, _ = b.get_cell(pos)
        b.set_cell(pos, h, v, n)
    for pos, n in S[2]:
        _, v, w = b.get_cell(pos)
        b.set_cell(pos, n, v, w)
    b.turn_count = S[3]
    return b


class Recorder:
    """Wraps an agent and keeps every position it was asked about."""
    def __init__(self, inner, store):
        self.inner, self.store = inner, store

    def compute_moves(self, state):
        self.store.append((state_from_game(state, 0), 0 if state.our_species == Species.VAMPIRE else 1,
                           state.rows, state.cols))
        return self.inner.compute_moves(state)


def collect_positions(n_maps=17):
    store = []
    for name, board in build_suite()[:n_maps]:
        agents = {Species.VAMPIRE: Recorder(make_opponent("Grabber"), store),
                  Species.WEREWOLF: Recorder(make_opponent("Rusher"), store)}
        play_game(board, agents, seed=7)
    return store


def test_generator_legal_and_transition_exact():
    P = Params()
    rng = random.Random(1)
    positions = collect_positions()
    checked = gambles = 0
    for S, side, rows, cols in positions:
        geo = Geometry(cols, rows)
        board = to_board(S, rows, cols)
        for other in (side, 1 - side):                    # both players' turns
            turns = gen_turns(S, other, geo, P, 30)
            assert turns or not S[other], "no turn for a side that has creatures"
            for turn in turns:
                msg = check_moves(board, SP[other], list(turn))
                assert msg is None, (msg, turn, S)
                outs = apply_turn(S, other, turn)
                assert abs(sum(p for p, _ in outs) - 1.0) < 1e-9
                if len(outs) == 1:
                    ref = perform_moves(board, SP[other], list(turn), rng)
                    got = to_board(outs[0][1], rows, cols)
                    assert ref.grid == got.grid, (turn, ref.grid, got.grid)
                else:
                    gambles += 1
                checked += 1
    print(f"  {len(positions)} positions, {checked} turns legal and exact ({gambles} with a random battle)")


def test_agent_answers_in_time():
    for name, board in build_suite():
        for sp in SP:
            agent = DeepAgent(time_limit=0.3)
            state = state_from_board(board, sp)
            t = time.perf_counter()
            moves = agent.compute_moves(state)
            dt = time.perf_counter() - t
            assert check_moves(board, sp, moves) is None, (name, moves)
            assert dt < 0.45, (name, dt)
    print("  every map, both species: legal answer within budget")


def test_counts_fit_in_a_byte():
    """The protocol sends counts as one byte: a group of 260 must never be moved in one piece."""
    S = ((((5, 5), 260),), (((20, 20), 30),), (((7, 5), 10), ((3, 5), 250)), 0)
    board = to_board(S, 30, 30)
    for side, sp in ((0, Species.VAMPIRE), (1, Species.WEREWOLF)):
        for turn in gen_turns(S, side, Geometry(30, 30), Params(), 30):
            assert check_moves(board, sp, list(turn)) is None, turn
    agent = DeepAgent(time_limit=0.3)
    moves = agent.compute_moves(state_from_board(board, Species.VAMPIRE))
    assert moves and check_moves(board, Species.VAMPIRE, moves) is None, moves
    print("  a group of 260: every proposed turn moves at most 255 creatures per cell")


if __name__ == "__main__":
    test_generator_legal_and_transition_exact()
    test_agent_answers_in_time()
    test_counts_fit_in_a_byte()
    print("All tests passed.")
