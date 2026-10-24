"""Run terminal-rendered Apex vs Splitter MCTS matches on fresh symmetric maps."""

import argparse
import random
import time

from game_engine import BoardState
from game_state import Species
from apex_agent import ApexAlphaBetaAgent
from splitter.agent import SplitterAgent
from tournament_arena import generate_random_symmetric_map, play_match_visual


class SplitterAdapter:
    def __init__(self, seconds: float):
        self.name = "SplitterMCTS"
        self.agent = SplitterAgent(
            name=self.name, time_limit=seconds, splits=True, search="mcts"
        )

    def reset(self):
        self.agent.reset()

    def compute_moves(self, state: BoardState, species: Species):
        return self.agent.compute_moves_board(state, species)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=10, help="square map size (10 or 50)")
    parser.add_argument("--games", type=int, default=2, help="even number; alternates sides")
    parser.add_argument("--time", type=float, default=1.8, help="Apex seconds per move")
    parser.add_argument("--splitter-time", type=float, default=1.5,
                        help="Splitter MCTS seconds per move")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="pause after each rendered position")
    parser.add_argument("--seed", type=int, default=41023)
    args = parser.parse_args()

    if args.size < 6 or args.games < 1:
        parser.error("--size must be at least 6 and --games must be positive")

    apex = ApexAlphaBetaAgent(
        name="Apex_OFR_VOR_QS", max_time_seconds=args.time,
        enable_foraging_yield=True, enable_voronoi=True, enable_quiescence=True,
    )
    splitter = SplitterAdapter(args.splitter_time)
    results = []

    print(f"Fresh map per match: {args.size}x{args.size}, starting seed={args.seed}; "
          f"Apex budget={args.time:.2f}s/move; Splitter MCTS={args.splitter_time:.2f}s/move",
          flush=True)
    for i in range(args.games):
        map_seed = args.seed + i
        initial = generate_random_symmetric_map(
            args.size, args.size, start_units=10, num_pairs=5, seed=map_seed
        )
        apex.transposition_table.clear()
        splitter.reset()
        random.seed(map_seed)
        apex_is_vampire = (i % 2 == 0)
        vampires, werewolves = (apex, splitter) if apex_is_vampire else (splitter, apex)
        print(f"\nMATCH {i + 1}/{args.games}: map seed={map_seed}; Apex is "
              f"{'Vampires' if apex_is_vampire else 'Werewolves'}", flush=True)
        started = time.perf_counter()
        winner, turns, v_count, w_count = play_match_visual(
            vampires, werewolves, initial, visualize=True, delay=args.delay
        )
        elapsed = time.perf_counter() - started
        results.append((winner, turns, v_count, w_count, elapsed))
        print(f"RESULT: winner={winner}; plies={turns}; V={v_count}; W={w_count}; "
              f"elapsed={elapsed:.1f}s", flush=True)

    apex_wins = sum(row[0] == apex.name for row in results)
    splitter_wins = sum(row[0] == splitter.name for row in results)
    draws = len(results) - apex_wins - splitter_wins
    print(f"\nTOTAL: Apex {apex_wins} - Splitter MCTS {splitter_wins} - Draws {draws} "
          f"({len(results)} games)", flush=True)


if __name__ == "__main__":
    main()
