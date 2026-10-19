"""
Replay one arena game verbosely (same seed => same dice as in the benchmark CSV).

    python -m arena.replay --bot Splitter --opp RaceMCTS --map testmap --side V --first V --seed 559485
    options: --time 0.2  --last 20 (only print the last N plies with boards)  --boards (every ply)
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from arena.maps import build_suite, render
from arena.opponents import make_bot
from arena.referee import play_game
from splitter.rules import V, W


def main():
    """Command line: replay one game verbosely, optionally with the board after every ply."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", default="Splitter")
    ap.add_argument("--opp", default="Apex")
    ap.add_argument("--map", default="testmap")
    ap.add_argument("--side", default="V")
    ap.add_argument("--first", default="V")
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--time", type=float, default=0.2)
    ap.add_argument("--last", type=int, default=0)
    ap.add_argument("--boards", action="store_true")
    a = ap.parse_args()
    side = V if a.side == "V" else W
    state = dict(build_suite(a.map))[a.map]
    bots = {side: make_bot(a.bot, a.time), 1 - side: make_bot(a.opp, a.time)}
    frames = []

    def rec(st):
        frames.append(render(st))
        return ""
    r = play_game(state, bots, first=V if a.first == "V" else W, seed=a.seed, verbose=False,
                  render=None)
    # play again, recording (same seed -> same game only for deterministic bots; MCTS bots vary)
    r = play_game(state, bots, first=V if a.first == "V" else W, seed=a.seed, verbose=True, render=rec) \
        if a.boards or a.last else r
    if a.last:
        for line, fr in list(zip(r.log, frames))[-a.last:]:
            print(line)
            print(fr)
    print(f"winner {'VW'[r.winner] if r.winner is not None else 'draw'} totals V/W {r.totals} "
          f"reason {r.reason} plies {r.plies}")


if __name__ == "__main__":
    main()
