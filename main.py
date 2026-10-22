import json
import os
import sys
import time
from network import NetworkClient
from game_state import GameState
from safe_agent import SafeAgent

# Changes compared with the original main.py (all on branch Dana):
#  * the agent is our SafeAgent (expectiminimax search + a gate that only lets legal turns through),
#  * --delay defaults to 0.0 (the old 0.5 s sleep ate a quarter of the 2 s budget), --time sets the
#    search budget in seconds,
#  * the game loop is the function run_game_loop(), so the end-to-end tests can reuse it,
#  * an error while handling one command is logged and the loop goes on (before, it ended the game),
#  * we NEVER send an empty MOV: on the official server that is "cheating" and loses the game at once,
#    whereas sending nothing only costs the turn (the server calls the other player after the time-out).


def parse_args():
    host = "127.0.0.1"
    port = 5555
    name = "CentraleBot"
    delay = 0.0   # seconds to wait before thinking (only useful to watch a game on the GUI)
    budget = 1.2  # search budget per turn in seconds (the limit is 2 s, the rest is safety margin)

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

    if "--time" in args:
        idx = args.index("--time")
        if idx + 1 < len(args):
            budget = float(args[idx + 1])
            args = args[:idx] + args[idx + 2:]

    if len(args) >= 2:
        host = args[-2]
        port = int(args[-1])
    elif len(args) == 1:
        port = int(args[0])

    return host, port, name, delay, budget


def run_game_loop(client, state, agent, name, delay=0.0, verbose=True):
    """Answer the server until it says BYE or the connection ends."""
    log = print if verbose else (lambda *a, **k: None)
    while True:
        try:
            cmd, data = client.receive_command()
        except ConnectionError:
            log("[Network] Server disconnected.")
            return
        except ValueError as e:                  # unknown command: the byte stream can no longer be trusted
            log(f"[Network] {e}")
            return

        try:
            if cmd == "SET":
                state.set_grid(data["rows"], data["cols"])
                log(f"[Game] Grid set to {data['rows']} rows x {data['cols']} cols")

            elif cmd == "HUM":
                state.set_houses(data["houses"])
                log(f"[Game] Houses registered: {len(data['houses'])} houses")

            elif cmd == "HME":
                state.set_home(data["home"])
                log(f"[Game] Home position: {data['home']}")

            elif cmd == "MAP":
                state.apply_updates(data["changes"])
                log(f"[Game] Initial MAP loaded ({len(data['changes'])} cells)")
                log("\n=== Initial Board State ===")
                log(state.render_board())

            elif cmd == "UPD":
                state.apply_updates(data["changes"])

                # Visual delay to observe on the WPF server GUI
                if delay > 0:
                    log(f"\n--- Turn Update for {name} ---")
                    log(state.render_board())
                    time.sleep(delay)

                start_time = time.time()
                moves = agent.compute_moves(state)
                elapsed = time.time() - start_time
                if not moves:
                    log(f"[{name}] No legal move to send: staying silent (an empty MOV would forfeit the game)")
                    continue
                for x1, y1, cnt, x2, y2 in moves:
                    log(f"[{name}] Move: {cnt} units from ({x1}, {y1}) -> ({x2}, {y2}) (eval: {elapsed*1000:.1f}ms)")
                client.send_moves(moves)

            elif cmd == "END":
                log("[Game] Game finished! Awaiting new game...")
                state.reset_for_new_game()

            elif cmd == "BYE":
                log("[Game] Server instructed BYE. Exiting cleanly.")
                return

        except ConnectionError:
            log("[Network] Server disconnected.")
            return
        except Exception as e:                   # one bad command must not end the game
            log(f"[Error] while handling {cmd}: {e!r} (continuing)")


def main():
    host, port, name, delay, budget = parse_args()
    print(f"=== Starting Vampires VS Werewolves AI Bot: {name} (Delay: {delay}s, budget {budget}s) ===")
    print(f"Connecting to {host}:{port} ...")

    client = NetworkClient(host, port)
    state = GameState()
    # Optional search settings as JSON in the environment (for experiments only), e.g.
    #   VVW_CFG='{"squash": 0.5}' python main.py ...
    cfg = json.loads(os.environ.get("VVW_CFG", "{}"))
    agent = SafeAgent(name=name, time_limit=budget, **cfg)

    try:
        client.connect()
    except Exception as e:
        print(f"[Error] Could not connect to game server: {e}")
        return

    try:
        # Handshake: send our bot name
        client.send_name(agent.name)
        run_game_loop(client, state, agent, name, delay)
    except Exception as e:
        print(f"[Error] Unexpected error in game loop: {e}")
    finally:
        client.close()
        print("=== Bot stopped ===")


if __name__ == "__main__":
    main()
