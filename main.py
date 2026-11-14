import sys
import time
from network import NetworkClient
from game_state import GameState
from ai_agent import AIAgent

def create_agent(agent_type: str, name: str):
    agent_type = (agent_type or "apex").lower()
    if agent_type in ("apex", "champion", "minimax"):
        return AIAgent(name=name)
    elif agent_type in ("mohamed", "splitter"):
        try:
            from splitter.agent import SplitterAgent, MODELS
            return SplitterAgent(name=name, time_limit=1.5, **MODELS["flagship"])
        except Exception as e:
            print(f"[Warning] Could not load Mohamed SplitterAgent ({e}), using default AIAgent")
            return AIAgent(name=name)
    elif agent_type in ("harsha", "mcts"):
        try:
            import harsha_agent
            harsha_agent.TIME_LIMIT = 1.5
            return harsha_agent.AIAgent(name=name)
        except Exception as e:
            print(f"[Warning] Could not load Harsha AIAgent ({e}), using default AIAgent")
            return AIAgent(name=name)
    elif agent_type in ("greedy", "reflex"):
        from rival_agents import GreedyReflexAgent
        from game_engine import BoardState
        class GreedyWrapper:
            def __init__(self, n):
                self.name = n
                self.inner = GreedyReflexAgent(n)
            def compute_moves(self, gs):
                bs = BoardState(gs.rows, gs.cols)
                for p, c in gs.board.items():
                    bs.set_cell(p, c.humans, c.vampires, c.werewolves)
                return self.inner.compute_moves(bs, gs.our_species)
            def reset(self):
                pass
        return GreedyWrapper(name)
    else:
        return AIAgent(name=name)

def parse_args():
    host = "127.0.0.1"
    port = 5555
    name = "CentraleBot"
    delay = 0.0  # 0.0s for official competition (use --delay 0.5 only for GUI visualization)
    agent_type = "apex"

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

    if "--agent" in args:
        idx = args.index("--agent")
        if idx + 1 < len(args):
            agent_type = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    if len(args) >= 2:
        host = args[-2]
        port = int(args[-1])
    elif len(args) == 1:
        port = int(args[0])

    return host, port, name, delay, agent_type

def main():
    host, port, name, delay, agent_type = parse_args()
    print(f"=== Starting Vampires VS Werewolves AI Bot: {name} (Agent: {agent_type}, Delay: {delay}s) ===")
    print(f"Connecting to {host}:{port} ...")

    client = NetworkClient(host, port)
    state = GameState()
    agent = create_agent(agent_type, name)

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
                moves = agent.compute_moves(state)
                elapsed = time.time() - start_time
                for x1, y1, cnt, x2, y2 in moves:
                    print(f"[{name}] Move: {cnt} units from ({x1}, {y1}) -> ({x2}, {y2}) (eval: {elapsed*1000:.1f}ms)")
                client.send_moves(moves)

            elif cmd == "END":
                print("[Game] Game finished! Awaiting new game...")
                state.reset_for_new_game()
                if hasattr(agent, "reset"):
                    try:
                        agent.reset()
                    except Exception:
                        pass

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
