"""
Play ANY two client programs against each other over the real network protocol, in any
language: our main.py, a teammate's client, another team's Java/C++/exe bot, ...

    python tools/server_match.py \
        --a "python main.py --name Splitter {host} {port}" \
        --b "python ../OtherTeam/main.py {host} {port}" \
        --maps testmap,thetrap,vil_10x16 --games 2 --timeout 2.0

{host} and {port} are replaced for every game (the tournament launch convention puts them at
the end of the command line). Each game runs tools/fake_server.py (the official server's
protocol, 2 s move limit, cheating rules - docs/SERVER_FINDINGS.md) on a free port; the two
clients alternate who connects first (player 0 = vampires = moves first), so each plays both
species and both move orders.

Results: one row per game in arena/results/server_matches/<time>_<A>_vs_<B>.csv, and a summary
line appended to arena/results/history.csv (same file as the arena).
"""
import argparse
import csv
import math
import os
import shlex
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from arena.maps import build_suite, load_xml
from arena.run import keep_awake
from tools.fake_server import FakeServer

HISTORY = os.path.join(ROOT, "arena", "results", "history.csv")


def _label(cmd: str) -> str:
    """Short name of a client command (its --name, else the script / program name)."""
    parts = shlex.split(cmd, posix=os.name != "nt")
    if "--name" in parts and parts.index("--name") + 1 < len(parts):
        return parts[parts.index("--name") + 1]
    prog = [p for p in parts if not p.startswith("-") and "{" not in p]
    return os.path.basename(prog[1] if len(prog) > 1 else prog[0]) if prog else "client"


def _maps(spec: str, max_ply: int):
    """Map names / families of arena.maps, or .xml paths."""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if part.endswith(".xml"):
            out.append((os.path.basename(part)[:-4], load_xml(part, max_ply)))
        else:
            out += build_suite(part, max_ply)
    return out


def play_one(cmd_first: str, cmd_second: str, state, timeout: float, seed: int, log=print) -> dict:
    """One game: server thread + two client processes. Returns the server's result dict."""
    srv = FakeServer(state, port=0, move_timeout=timeout, seed=seed, log=lambda *_: None)
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    procs = []
    for i, cmd in enumerate((cmd_first, cmd_second)):
        full = cmd.format(host="127.0.0.1", port=srv.port)
        procs.append(subprocess.Popen(full, shell=True, cwd=ROOT, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL))
        limit = time.time() + 60                # connection order = player order: wait for this client
        while srv.connected <= i and time.time() < limit and th.is_alive():
            time.sleep(0.05)
    th.join(timeout=state.max_ply * (timeout + 0.5) + 60)
    for p in procs:
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            log("  client did not exit after BYE: killed")
    return srv.result or {"reason": "server-timeout", "winner": None, "timeouts": [0, 0], "cheat": None,
                          "totals": (0, 0), "plies": 0}


def main():
    """Command line: play the matches, print a summary, store the results."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", required=True, help='client A command, with {host} {port}')
    ap.add_argument("--b", required=True, help='client B command, with {host} {port}')
    ap.add_argument("--maps", default="given", help="map names/families (arena.maps) or .xml paths, comma-separated")
    ap.add_argument("--games", type=int, default=1, help="games per map and connection order")
    ap.add_argument("--timeout", type=float, default=2.0, help="seconds per move (server limit)")
    ap.add_argument("--max-ply", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-store", action="store_true", help="print only (used by the tests)")
    a = ap.parse_args()
    keep_awake()
    la, lb = _label(a.a), _label(a.b)
    if la == lb:
        la, lb = la + "#A", lb + "#B"
    rows = []
    for map_name, state in _maps(a.maps, a.max_ply):
        for g in range(a.games):
            for a_first in (True, False):
                first, second = (a.a, a.b) if a_first else (a.b, a.a)
                r = play_one(first, second, state, a.timeout, a.seed + len(rows))
                a_player = 0 if a_first else 1
                if r.get("winner") is None:
                    score = 0.5
                else:
                    score = 1.0 if r["winner"] == a_player else 0.0
                cheat = r.get("cheat")
                row = {"map": map_name, "game": g, "a_first": a_first, "a_species": "VW"[a_player],
                       "score_a": score, "reason": r.get("reason"), "plies": r.get("plies"),
                       "totals_vw": r.get("totals"), "timeouts_a": r.get("timeouts", [0, 0])[a_player],
                       "timeouts_b": r.get("timeouts", [0, 0])[1 - a_player],
                       "cheat": f"{cheat[0]}: {cheat[1]}" if cheat else ""}
                rows.append(row)
                print(f"  {map_name:14s} {la} as {row['a_species']}: {score:3.1f}  ({row['reason']}, "
                      f"{row['plies']} plies, totals V/W {row['totals_vw']}"
                      f"{', CHEAT ' + row['cheat'] if cheat else ''})", flush=True)
    n = len(rows)
    p = sum(r["score_a"] for r in rows) / max(1, n)
    se = math.sqrt(max(p * (1 - p), 1e-9) / max(1, n))
    print(f"\n{la} vs {lb}: {100 * p:.1f}% +- {100 * se:.1f} over {n} games  "
          f"(timeouts A/B: {sum(r['timeouts_a'] for r in rows)}/{sum(r['timeouts_b'] for r in rows)}, "
          f"cheats: {sum(1 for r in rows if r['cheat'])})")
    if a.no_store:
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = os.path.join(ROOT, "arena", "results", "server_matches")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{stamp}_{la}_vs_{lb}.csv".replace(" ", "_"))
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["map"])
        w.writeheader()
        w.writerows(rows)
    new = not os.path.exists(HISTORY)
    with open(HISTORY, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["run", "bot", "opponents", "maps", "games", "time", "seed",
                                          "games_played", "score", "se", "problems"])
        if new:
            w.writeheader()
        w.writerow({"run": f"{stamp}_server_match", "bot": la, "opponents": lb, "maps": a.maps,
                    "games": a.games, "time": a.timeout, "seed": a.seed, "games_played": n,
                    "score": round(100 * p, 1), "se": round(100 * se, 1),
                    "problems": sum(r["timeouts_a"] for r in rows) + sum(1 for r in rows if r["cheat"])})
    print(f"rows saved to {out}\nsummary appended to {HISTORY}")


if __name__ == "__main__":
    main()
