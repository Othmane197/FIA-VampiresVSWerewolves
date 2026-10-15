"""
Rival AI Bot Client for Vampires VS Werewolves Server
Allows connecting any rival baseline agent to the official game server for live matches.
Usage:
    python rival_bot.py --ai GreedyReflexAI 127.0.0.1 5555
    python rival_bot.py --ai PotentialFieldAI 127.0.0.1 5555
    python rival_bot.py --ai ShallowMinimaxAI 127.0.0.1 5555
    python rival_bot.py --ai MonteCarloAI 127.0.0.1 5555
"""

import sys
import time
from network import NetworkClient
from game_state import GameState, Species
from game_engine import BoardState
from rival_agents import (
    RandomAgent,
    GreedyReflexAgent,
    PotentialFieldAgent,
    ShallowMinimaxAgent,
    MonteCarloAgent,
    TacticalSplitterAgent
)

AGENT_MAP = {
    "RandomAI": RandomAgent,
    "GreedyReflexAI": GreedyReflexAgent,
    "PotentialFieldAI": PotentialFieldAgent,
    "ShallowMinimaxAI": ShallowMinimaxAgent,
    "MonteCarloAI": MonteCarloAgent,
    "TacticalSplitterAI": TacticalSplitterAgent
}

def parse_args():
    host = "127.0.0.1"
    port = 5555
    ai_type = "GreedyReflexAI"
    delay = 0.0

    args = sys.argv[1:]
    if "--ai" in args:
        idx = args.index("--ai")
        if idx + 1 < len(args):
            ai_type = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    if "--delay" in args:
        idx = args.index("--delay")
        if idx + 1 < len(args):
            delay = float(args[idx + 1])
            args = args[:idx] + args[idx + 2:]

    if len(args) >= 2:
        host = args[-2]
        port = int(args[-1])
    elif len(args) == 1:
        port = int(args[0])

    return host, port, ai_type, delay

def main():
    host, port, ai_type, delay = parse_args()
    agent_cls = AGENT_MAP.get(ai_type, GreedyReflexAgent)
    agent = agent_cls(name=ai_type)

    print(f"=== Starting Rival Bot [{agent.name}] connecting to {host}:{port} ===")
    client = NetworkClient(host, port)
    state = GameState()

    try:
        client.connect()
    except Exception as e:
        print(f"[Error] Could not connect: {e}")
        return

    client.send_name(agent.name)

    try:
        while True:
            cmd, data = client.receive_command()
            if cmd == "SET":
                state.set_grid(data["rows"], data["cols"])
            elif cmd == "HUM":
                state.set_houses(data["houses"])
            elif cmd == "HME":
                state.set_home(data["home"])
            elif cmd == "MAP":
                state.apply_updates(data["changes"])
            elif cmd == "UPD":
                state.apply_updates(data["changes"])
                if delay > 0:
                    time.sleep(delay)

                # Convert state
                bs = BoardState(state.rows, state.cols)
                for pos, cell in state.board.items():
                    bs.set_cell(pos, cell.humans, cell.vampires, cell.werewolves)

                moves = agent.compute_moves(bs, state.our_species or Species.WEREWOLF)
                client.send_moves(moves)
            elif cmd == "END":
                print(f"[{agent.name}] Game ended.")
                state.reset_for_new_game()
            elif cmd == "BYE":
                print(f"[{agent.name}] Server BYE.")
                break
    except ConnectionError:
        print(f"[{agent.name}] Server disconnected.")
    finally:
        client.close()

if __name__ == "__main__":
    main()
