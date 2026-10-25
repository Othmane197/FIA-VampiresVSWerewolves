import os
import sys
import threading
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

    return host, port, name, delay

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


class Watchdog:
    """
    Runs agent.compute_moves in a worker thread and waits at most `limit` seconds: a late answer
    would make the server skip our turn (and can desynchronise the protocol). After `limit`, this
    turn's search is asked for its best plan so far (agent.anytime_moves, already legality-checked);
    without one, the caller sends fallback_moves. While a late worker is still running, the agent
    is not called again (its state is not thread-safe): the fallback is used until it finishes.
    """

    def __init__(self, limit: float):
        """limit = seconds from the UPD to the MOV (the server allows 2 s)."""
        self.limit = limit
        self.worker = None
        self.late = 0

    def decide(self, agent, state, start: float):
        """Moves from the agent, or None if it crashed, returned nothing or was too slow."""
        if self.worker is not None and self.worker.is_alive():
            return None                         # previous turn's search still running
        box = {}

        def work():
            try:
                box["moves"] = agent.compute_moves(state)
            except Exception as e:              # never let the agent drop the connection
                box["error"] = e

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()
        self.worker.join(max(0.05, self.limit - (time.time() - start)))
        if self.worker.is_alive():
            self.late += 1
            anytime = getattr(agent, "anytime_moves", None)
            moves = anytime() if anytime is not None else None
            if moves:
                print(f"[Watchdog] agent still thinking after {self.limit:.2f}s -> its best plan so far")
                return moves
            print(f"[Watchdog] agent still thinking after {self.limit:.2f}s -> fallback move")
            return None
        if "error" in box:
            print(f"[Error] compute_moves crashed: {box['error']!r} -> fallback move")
        return box.get("moves")


def main():
    """Protocol loop: NME, then SET/HUM/HME/MAP to build the state, then answer every UPD with a MOV."""
    host, port, name, delay = parse_args()
    print(f"=== Starting Vampires VS Werewolves AI Bot: {name} (Delay: {delay}s) ===")
    print(f"Connecting to {host}:{port} ...")

    client = NetworkClient(host, port)
    state = GameState()
    agent = AIAgent(name=name)
    watchdog = Watchdog(float(os.environ.get("SPLITTER_WATCHDOG", "1.8")))

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
                moves = watchdog.decide(agent, state, start_time)
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
