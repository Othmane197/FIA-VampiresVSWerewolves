"""
Connect ANY arena bot (a teammate's bot, a Splitter variant, a snapshot) to a real game server,
e.g. to watch Splitter vs Apex on the official GUI:

    python main.py --name Splitter 127.0.0.1 5555          # terminal 1 (our tournament bot)
    python tools/play_bot.py Apex 127.0.0.1 5555            # terminal 2
    python tools/play_bot.py "Splitter-nosplit" 127.0.0.1 5555 --time 1.5

Same protocol loop as main.py; the bot spec is the one used by `python -m arena.run`.
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from arena.opponents import make_bot
from game_state import GameState
from network import NetworkClient
from splitter.state import State, side_of_species


def main():
    """Command line: connect any arena bot to a game server and play."""
    ap = argparse.ArgumentParser()
    ap.add_argument("bot")
    ap.add_argument("host")
    ap.add_argument("port", type=int)
    ap.add_argument("--time", type=float, default=1.5)
    a = ap.parse_args()
    bot = make_bot(a.bot, a.time)
    client = NetworkClient(a.host, a.port)
    client.connect()
    name = "".join(c for c in a.bot if c.isalnum())[:20] or "Bot"
    client.send_name(name)
    gs = GameState()
    plies = 0
    while True:
        cmd, data = client.receive_command()
        if cmd == "SET":
            gs.set_grid(data["rows"], data["cols"])
        elif cmd == "HUM":
            gs.set_houses(data["houses"])
        elif cmd == "HME":
            gs.set_home(data["home"])
        elif cmd == "MAP":
            gs.apply_updates(data["changes"])
            bot.reset()
        elif cmd == "UPD":
            gs.apply_updates(data["changes"])
            t0 = time.time()
            state = State.from_game_state(gs, ply=plies)
            moves = bot.play(state, side_of_species(gs.our_species))
            plies += 2
            print(f"[{name}] {len(moves)} moves in {1000 * (time.time() - t0):.0f} ms")
            client.send_moves(moves)
        elif cmd == "END":
            gs.reset_for_new_game()
        elif cmd == "BYE":
            break
    client.close()


if __name__ == "__main__":
    main()
