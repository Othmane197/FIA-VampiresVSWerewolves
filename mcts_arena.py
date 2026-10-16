# local test arena, no server needed
# plays RaceMCTS vs the test bots on every map, both sides
#   python mcts_arena.py --rival Greedy --time 0.3 --games 2
# needs rival_agents.py / apex_agent.py from Othmane's branch for the opponents

import argparse
import random
import time
import xml.etree.ElementTree as ET

from game_state import Species
from game_engine import BoardState
from mcts_agent import MCTSAgent, other_species

MAPS = ["testmap.xml", "testmap2.xml", "thetrap.xml"]


def load_map(path: str, max_turns: int) -> BoardState:
    root = ET.parse(path).getroot()
    state = BoardState(int(root.attrib["Rows"]), int(root.attrib["Columns"]), max_turns=max_turns)
    for elem in root:
        x, y, n = int(elem.attrib["X"]), int(elem.attrib["Y"]), int(elem.attrib["Count"])
        h, v, w = state.get_cell((x, y))
        if elem.tag == "Humans":
            state.set_cell((x, y), h + n, v, w)
        elif elem.tag == "Vampires":
            state.set_cell((x, y), h, v + n, w)
        elif elem.tag == "Werewolves":
            state.set_cell((x, y), h, v, w + n)
    return state


def play_game(vamp_agent, wolf_agent, state: BoardState, verbose: bool = False):
    # vampires start, returns (winner, vampires left, werewolves left, plies)
    agents = {Species.VAMPIRE: vamp_agent, Species.WEREWOLF: wolf_agent}
    to_move = Species.VAMPIRE
    while True:
        over, winner = state.is_game_over()
        if over:
            return (winner, state.get_species_total(Species.VAMPIRE),
                    state.get_species_total(Species.WEREWOLF), state.turn_count)
        moves = agents[to_move].compute_moves(state, to_move)
        valid, reason = state.validate_moves(moves, to_move)
        if not valid:
            print(f"   !! {agents[to_move].name} illegal move ({reason}) -> loses")
            return other_species(to_move), 0, 0, state.turn_count
        state = state.apply_moves(moves, to_move, deterministic=False)
        if verbose:
            print(f"   ply {state.turn_count:3d} {to_move.value:9s} {moves}")
        to_move = other_species(to_move)


def get_rivals(think_time: float):
    rivals = []
    try:
        from rival_agents import RandomAgent, GreedyReflexAgent, PotentialFieldAgent, MonteCarloAgent
        rivals += [RandomAgent("Random"), GreedyReflexAgent("Greedy"),
                   PotentialFieldAgent("PotentialField"), MonteCarloAgent("MonteCarlo")]
    except ImportError:
        print("(rival_agents.py not found: copy it from the Othmane branch for more opponents)")
    try:
        from apex_agent import ApexAlphaBetaAgent
        rivals.append(ApexAlphaBetaAgent(name="AlphaBeta(Othmane)", max_time_seconds=think_time))
    except ImportError:
        pass
    return rivals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rival", default=None, help="only play opponents whose name contains this")
    ap.add_argument("--time", type=float, default=0.3, help="thinking time per move (seconds)")
    ap.add_argument("--games", type=int, default=1, help="games per map per side")
    ap.add_argument("--turns", type=int, default=120, help="max plies per game")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    me = MCTSAgent(name="RaceMCTS", max_time_seconds=args.time)
    rivals = [r for r in get_rivals(args.time)
              if args.rival is None or args.rival.lower() in r.name.lower()]

    for rival in rivals:
        wins = losses = draws = 0
        print(f"\n=== RaceMCTS vs {rival.name} ===")
        for map_path in MAPS:
            for _ in range(args.games):
                for my_side in (Species.VAMPIRE, Species.WEREWOLF):
                    state = load_map(map_path, args.turns)
                    vamp, wolf = (me, rival) if my_side == Species.VAMPIRE else (rival, me)
                    t0 = time.time()
                    winner, v, w, plies = play_game(vamp, wolf, state, args.verbose)
                    mine, theirs = (v, w) if my_side == Species.VAMPIRE else (w, v)
                    if winner == my_side:
                        wins += 1; result = "WIN "
                    elif winner is None:
                        draws += 1; result = "DRAW"
                    else:
                        losses += 1; result = "LOSS"
                    print(f"  {map_path:13s} as {my_side.value:9s}: {result}  "
                          f"{mine:3d} vs {theirs:3d}  ({plies} plies, {time.time()-t0:.0f}s)")
        print(f"  --> {wins} wins / {losses} losses / {draws} draws")


if __name__ == "__main__":
    main()
