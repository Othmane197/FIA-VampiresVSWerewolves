import sys
import time

from ai_agent import AIAgent
from game_state import GameState
from network import NetworkClient


def parse_args():
    """Read --name / --delay and the server ip + port (the last two arguments, as the caller adds them)."""
    host = "127.0.0.1"
    port = 5555
    name = "CentraleBot"
    delay = 0.0  # No delay by default: the server gives only 2 s per move (use --delay 0.5 to watch)

    args = sys.argv[1:]
    if "--name" in args:
        idx = args.index("--name")
        if idx + 1 < len(args):
            name = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    pregame = "--pregame" in args       # pre-game analysis between MAP and the first UPD (off by default)
    if pregame:
        args = [a for a in args if a != "--pregame"]

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

    return host, port, name, delay, pregame

def fallback_moves(state: GameState):
    """One legal move (biggest group to a free neighbour that is not a source): never send an empty MOV."""
    groups = state.get_our_groups()
    if not groups:
        return []
    (x, y), count = max(groups, key=lambda g: g[1])
    cells = state.get_legal_adjacent_cells((x, y))
    free = [c for c in cells if c not in state.board or state.board[c].is_empty()]
    nx, ny = (free or cells)[0]
    return [(x, y, count, nx, ny)]


def main():
    """Protocol loop: NME, then SET/HUM/HME/MAP to build the state, then answer every UPD with a MOV."""
    host, port, name, delay, pregame = parse_args()
    print(f"=== Starting Vampires VS Werewolves AI Bot: {name} (Delay: {delay}s) ===")
    print(f"Connecting to {host}:{port} ...")

    client = NetworkClient(host, port)
    state = GameState()
    agent = AIAgent(name=name)

    try:
        client.connect()
    except Exception as e:
        print(f"[Error] Could not connect to game server: {e}")
        return

    # Handshake: send our bot name
    client.send_name(agent.name)

    # Main protocol loop
    try:
        while True:
            cmd, data = client.receive_command()

            if cmd == "SET":
                state.set_grid(data["rows"], data["cols"])
                print(f"[Game] Grid set to {data['rows']} rows x {data['cols']} cols")

            elif cmd == "HUM":
                state.set_houses(data["houses"])
                print(f"[Game] Houses registered: {len(data['houses'])} houses")

            elif cmd == "HME":
                state.set_home(data["home"])
                print(f"[Game] Home position: {data['home']}")

            elif cmd == "MAP":
                state.apply_updates(data["changes"])
                print(f"[Game] Initial MAP loaded ({len(data['changes'])} cells)")
                if pregame and hasattr(agent, "pregame"):
                    agent.pregame(state)
                print("\n=== Initial Board State ===")
                print(state.render_board())

            elif cmd == "UPD":
                state.apply_updates(data["changes"])
                
                # Visual delay to observe on the WPF server GUI
                if delay > 0:
                    print(f"\n--- Turn Update for {name} ---")
                    print(state.render_board())
                    time.sleep(delay)

                start_time = time.time()
                try:
                    moves = agent.compute_moves(state)
                except Exception as e:
                    # never drop the connection (the server counts that as cheating)
                    print(f"[Error] compute_moves crashed: {e!r} -> fallback move")
                    moves = []
                if not moves:
                    moves = fallback_moves(state)
                elapsed = time.time() - start_time
                for x1, y1, cnt, x2, y2 in moves:
                    print(f"[{name}] Move: {cnt} units from ({x1}, {y1}) -> ({x2}, {y2}) (eval: {elapsed*1000:.1f}ms)")
                client.send_moves(moves)

            elif cmd == "END":
                print("[Game] Game finished! Awaiting new game...")
                state.reset_for_new_game()
                if hasattr(agent, "reset"):
                    agent.reset()

            elif cmd == "BYE":
                print("[Game] Server instructed BYE. Exiting cleanly.")
                break

    except ConnectionError:
        print("[Network] Server disconnected.")
    except Exception as e:
        print(f"[Error] Unexpected error in game loop: {e}")
    finally:
        client.close()
        print("=== Bot stopped ===")

if __name__ == "__main__":
    main()
