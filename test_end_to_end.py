"""Run with:  python3 test_end_to_end.py   (from the repo folder)

Plays real games over a real TCP socket: main.py's loop + network.py + SafeAgent on one side,
fake_server.py (official rules from server_rules.py) on the other."""
import io
import random
import sys
import time
from contextlib import redirect_stdout

import main as bot_main
from fake_server import FakeServer
from game_state import GameState, Species
from map_loader import load_map
from network import NetworkClient
from safe_agent import SafeAgent
from sparring_agents import make_opponent

V, W = Species.VAMPIRE, Species.WEREWOLF
trap = load_map("thetrap.xml")


def play(board, species, opponent, inner=None, max_plies=40, time_limit=0.2, sabotage=None, seed=0,
         answer_timeout=5.0):
    """One game through the real client code. Returns (server, agent, bot_output)."""
    server = FakeServer(board, species, opponent, max_plies=max_plies, seed=seed, sabotage=sabotage,
                        answer_timeout=answer_timeout).start()
    agent = SafeAgent(name="TestBot", inner=inner, time_limit=time_limit)
    client = NetworkClient("127.0.0.1", server.port)
    out = io.StringIO()
    with redirect_stdout(out):
        client.connect()
        client.send_name(agent.name)
        bot_main.run_game_loop(client, GameState(), agent, "TestBot", delay=0.0, verbose=True)
        client.close()
    server.join()
    return server, agent, out.getvalue()


class Garbage:
    def __init__(self, seed):
        self.rng = random.Random(seed)

    def compute_moves(self, state):
        return [(self.rng.randint(-1, 9), self.rng.randint(-1, 9), self.rng.randint(0, 20),
                 self.rng.randint(-1, 9), self.rng.randint(-1, 9)) for _ in range(self.rng.randint(0, 3))]


class Crashing:
    def compute_moves(self, state):
        raise RuntimeError("search exploded")


# 1) Full games on thetrap, both species, against two opponents: the server accepts every turn.
total_turns = 0
for species in (V, W):
    for opp_name in ("Grabber", "Rusher"):
        for seed in (1, 2, 3):                 # a game can end early when a 4v4 coin flip wipes a side out
            s, agent, _ = play(trap, species, make_opponent(opp_name), max_plies=60, seed=seed)
            assert s.error is None, s.error
            assert s.name_received == "TestBot"
            assert s.invalid == [], s.invalid
            assert s.silent_turns == 0 and s.replies >= 1, (s.silent_turns, s.replies)
            assert s.plies == 60 or s.final_board.is_game_over()[0], "game stopped for no reason"
            assert max(s.answer_times) < 2.0, max(s.answer_times)
            assert agent.counts["search"] == s.replies and agent.counts["fallback"] == 0, agent.counts
            total_turns += s.replies
print(f"OK  12 games over TCP (both species x Grabber/Rusher x 3 seeds): {total_turns} turns, every one "
      "accepted by the server rules, all answers < 2 s, all from the search tier")

# 2) The real default budget (1.2 s) on a bigger map: stays below the 2 s limit including the socket.
from maps import build_suite
suite = build_suite()
name, big = next((n, b) for n, b in suite if n.startswith("g15x29"))
s, agent, _ = play(big, V, make_opponent("Grabber"), max_plies=12, time_limit=1.2, seed=2)
assert s.invalid == [] and s.silent_turns == 0 and s.replies >= 1
worst = max(s.answer_times)
assert worst < 2.0, worst
print(f"OK  {name} with the 1.2 s budget: slowest answer {worst:.2f} s (limit 2 s) over {s.replies} turns")

# 2b) A long game (many turns) against the passive Turtle, so the loop is exercised over many UPDs.
s, agent, _ = play(big, V, make_opponent("Turtle"), max_plies=80, time_limit=0.3, seed=5)
assert s.invalid == [] and s.silent_turns == 0 and s.error is None
assert s.replies >= 20, s.replies
print(f"OK  long game on {name}: {s.replies} turns, none rejected, slowest answer {max(s.answer_times):.2f} s")

# 3) A broken search agent: garbage moves or exceptions are replaced, the server never sees an illegal turn.
for label, inner in (("garbage", Garbage(5)), ("exception", Crashing())):
    s, agent, _ = play(trap, V, make_opponent("Grabber"), inner=inner, max_plies=30, seed=3)
    assert s.invalid == [] and s.silent_turns == 0 and s.replies >= 1, (label, s.invalid)
    assert agent.counts["search"] == 0 and agent.counts["candidate"] + agent.counts["fallback"] == s.replies
print("OK  search agent returning garbage / raising: the server still gets a legal turn every time")

# 4) The protocol goes wrong: the loop ends cleanly (no hang, no traceback).
for sab in ("unknown_command", "hangup"):
    t0 = time.perf_counter()
    s, agent, out = play(trap, V, make_opponent("Grabber"), sabotage=sab)
    assert time.perf_counter() - t0 < 5 and "Traceback" not in out
print("OK  unknown command / server hang-up: the loop returns cleanly")

# 5) A species with no creature left: we stay silent instead of sending an empty (losing) MOV.
class Dead:
    pass
only_wolves = trap.clone()
for pos, (h, v, w) in list(only_wolves.grid.items()):
    only_wolves.set_cell(pos, h, 0, w)
only_wolves.set_cell((4, 3), 0, 1, 0)                 # keeps the vampire home, then it is removed below
s_board = only_wolves.clone()
s_board.set_cell((4, 3), 0, 0, 0)
agent = SafeAgent(name="TestBot")
state = GameState()
state.set_grid(s_board.rows, s_board.cols)
state.our_species = V
assert agent.compute_moves(state) == []
print("OK  no creature: SafeAgent returns [] and main.py sends nothing (never an empty MOV)")

# 6) main.main() itself: command line, handshake, default delay 0.0, budget flag.
server = FakeServer(trap, V, make_opponent("Grabber"), max_plies=10, seed=4).start()
sys.argv = ["main.py", "--name", "CentraleBot", "--time", "0.2", "127.0.0.1", str(server.port)]
out = io.StringIO()
with redirect_stdout(out):
    bot_main.main()
server.join()
assert server.name_received == "CentraleBot" and server.invalid == [] and server.replies >= 1
sys.argv = ["main.py", "127.0.0.1", "5555"]
host, port, name, delay, budget = bot_main.parse_args()
assert (host, port, delay, budget) == ("127.0.0.1", 5555, 0.0, 1.2)
print("OK  main.main(): connects, sends the name, plays, exits cleanly; defaults are delay 0.0 s / budget 1.2 s")

print("\nAll tests passed.")
