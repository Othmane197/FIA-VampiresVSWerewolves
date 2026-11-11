"""
tcp_match.py  (our own file)

Our bot (in-process, SafeAgent + DeepAgent) against ANY external client program that speaks the
real protocol over TCP: the program is started unmodified, e.g. a teammate's `main.py host port`,
and connects to fake_server.FakeServer, which applies the official rules (server_rules.py).

Useful for bots that cannot be imported (Harsha's starts its own process pool), and as the most
faithful test of tournament conditions for the external program (its own process, its own network
loop, a 2-second answer limit).

    python3 tcp_match.py --client-dir rivals/Harsha --maps 1,2,big40x40.xml --seeds 1

One game at a time (the external bot may use several processes). Prints one JSON line per game
(same fields as tourney.py, A = our bot) and a summary.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time

from game_state import Species
from map_loader import load_map
from maps import build_suite
from fake_server import FakeServer

V, W = Species.VAMPIRE, Species.WEREWOLF


class Timed:
    """Wraps our agent: records decision times and empty answers."""

    def __init__(self, inner):
        self.inner = inner
        self.times = []
        self.empty = 0

    def compute_moves(self, state):
        t = time.perf_counter()
        moves = self.inner.compute_moves(state)
        self.times.append(time.perf_counter() - t)
        if not moves:
            self.empty += 1
        return moves


def load(ident):
    if ident.isdigit():
        return build_suite()[int(ident)]
    return ident.replace(".xml", ""), load_map(ident)


def play(map_ident, ours_vampire, seed, client_dir, client_cmd, deep_cfg, answer_timeout):
    from deep_agent import DeepAgent
    from safe_agent import SafeAgent
    name, board = load(map_ident)
    our_sp = V if ours_vampire else W
    ext_sp = W if ours_vampire else V
    ours = Timed(SafeAgent("Deep", inner=DeepAgent(**deep_cfg)))
    srv = FakeServer(board, our_species=ext_sp, opponent=ours, max_plies=200,
                     answer_timeout=answer_timeout, seed=seed).start()
    cmd = client_cmd.format(port=srv.port).split()
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=client_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        srv.join(timeout=1200)
    finally:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    b = srv.final_board
    ours_left = b.get_species_total(our_sp) if b is not None else 0
    ext_left = b.get_species_total(ext_sp) if b is not None else 0
    over = b is not None and b.is_game_over()[0]
    problem_a = problem_b = ""
    forfeit = None
    if srv.invalid:
        problem_b, forfeit = "illegal move: " + srv.invalid[0], ext_sp.value
        score = 1.0
    elif srv.error:
        problem_b, score = "server/client error: " + srv.error, 0.5
    elif srv.plies < 200 and not over:
        problem_a, forfeit, score = "our bot gave an empty or illegal turn", our_sp.value, 0.0
    else:
        score = 1.0 if ours_left > ext_left else (0.0 if ours_left < ext_left else 0.5)
    if srv.silent_turns:
        problem_b += f" {srv.silent_turns} turns without answer in {answer_timeout}s"
    return dict(map=name, a_side="V" if ours_vampire else "W", seed=seed, score=score, plies=srv.plies,
                a_left=ours_left, b_left=ext_left,
                a_max=round(max(ours.times, default=0), 2), b_max=round(max(srv.answer_times, default=0), 2),
                a_problem=problem_a, b_problem=problem_b.strip(), forfeit=forfeit, secs=round(time.time() - t0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-dir", required=True)
    ap.add_argument("--client-cmd", default=f"{sys.executable} main.py 127.0.0.1 {{port}}")
    ap.add_argument("--maps", default="1,2")
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--seed0", type=int, default=100)
    ap.add_argument("--deep", default="{}", help="DeepAgent parameters (JSON)")
    ap.add_argument("--answer-timeout", type=float, default=2.0)
    args = ap.parse_args()
    rows = []
    for s in range(args.seeds):
        for k, m in enumerate(args.maps.split(",")):
            for ours_v in (True, False):
                row = play(m, ours_v, args.seed0 + 1000 * s + k, os.path.abspath(args.client_dir),
                           args.client_cmd, json.loads(args.deep), args.answer_timeout)
                rows.append(row)
                print(json.dumps(row), flush=True)
    n = len(rows)
    sc = sum(r["score"] for r in rows) / n
    wins = sum(r["score"] == 1 for r in rows)
    draws = sum(r["score"] == 0.5 for r in rows)
    se = math.sqrt(max(sc * (1 - sc), 0.01) / n)
    print(f"SUMMARY ours vs {args.client_dir}: {n} games, A wins {wins}, draws {draws}, losses {n - wins - draws} "
          f"| score {100 * sc:.1f}% +- {100 * se:.1f} | A max time {max(r['a_max'] for r in rows)}s "
          f"| B max answer {max(r['b_max'] for r in rows)}s")


if __name__ == "__main__":
    main()
