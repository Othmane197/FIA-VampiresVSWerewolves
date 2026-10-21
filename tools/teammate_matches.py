"""
Real-conditions matches: our tournament bot against each teammate's bot, 3 games each, recorded.

    python tools/teammate_matches.py                       # the flagship vs Apex, TacticalSplitter, RaceMCTS, Expecti
    python tools/teammate_matches.py --model backup        # the backup model instead
    python tools/teammate_matches.py --opp Apex RaceMCTS   # only some opponents
    python tools/teammate_matches.py --all                 # every bot on the teammates' branches

First time only: python -m arena.fetch_opponents   (copies the teammates' bots into arena/vendor/)

WHAT "REAL CONDITIONS" MEANS HERE
  * Every game is played over the real network protocol, through tools/fake_server.py (a copy of
    the official server: 2 s per move, a late move skips the turn, an illegal or empty move or a
    dropped connection is cheating and loses, player 0 = first to connect = Vampires = moves first).
  * The official limits: 200 plies in total and a 5-minute game clock (MaxGameDuration).
  * Our side is the real tournament client, main.py (with its watchdog), as launched on tournament
    day; each teammate's bot runs as its own client process (tools/play_bot.py).
  * Every bot thinks 1.5 s per move (ours and theirs, --time / --opp-time).
  * One game at a time by default: no other game competes for the CPU.
  * NONE of the arena's speed-ups: every game is played to its real end (no informative-slot
    selection, no early stopping, no shortened thinking time).
  * The games per opponent cycle through every (map, side) combination of the official sample
    maps: game 1 testmap.xml as Vampires (we connect first, so we move first), game 2 thetrap.xml as
    Vampires, game 3 testmap.xml as Werewolves, game 4 thetrap.xml as Werewolves, then again.

HOW LONG: a game takes 1 to 5 minutes, so the default 12 games take about 30-60 minutes.

RESULTS go to arena/results/teammates/<date-time>_<model>/
    games.csv     one row per game (written as soon as each game ends)
    summary.md    the summary table printed at the end
    logs/         the output of both clients for every game
plus one line per opponent in arena/results/history.csv (see them with: python -m arena.history).
"""
import argparse
import csv
import math
import os
import re
import subprocess
import sys
import threading
import time
from contextlib import ExitStack

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from arena.maps import build_suite, load_xml
from arena.run import keep_awake
from tools.fake_server import FakeServer

# The teammates' bots, and the git branch each comes from (arena/fetch_opponents.py)
TEAMMATE_BOTS = {
    "Apex": "Othmane", "TacticalSplitter": "Othmane",        # Othmane's main bots
    "RaceMCTS": "Ronita",                                     # Ronita's MCTS
    "Expecti": "Dana",                                        # Dana's expectiminimax
    "Greedy": "Othmane", "PotentialField": "Othmane", "ShallowMinimax": "Othmane",
    "MonteCarlo": "Othmane", "Grabber": "Dana", "Rusher": "Dana", "Turtle": "Dana",
}
MAIN_BOTS = ["Apex", "TacticalSplitter", "RaceMCTS", "Expecti"]
HISTORY = os.path.join(ROOT, "arena", "results", "history.csv")
FIELDS = ["opponent", "game", "map", "we_connect_first", "our_species", "result", "score", "reason",
          "plies", "our_total", "their_total", "our_timeouts", "their_timeouts", "our_slowest_move_ms",
          "watchdog_fallbacks", "cheat", "minutes"]


def load_map(name: str, max_ply: int):
    """An .xml map file (relative to the repo) or a map name of arena/maps.py."""
    if name.endswith(".xml"):
        return load_xml(os.path.join(ROOT, name), max_ply)
    return dict(build_suite(name, max_ply))[name]


def schedule(g: int, maps):
    """Game g (0-based): every map as Vampires (we connect first), then every map as Werewolves."""
    return maps[g % len(maps)], (g // len(maps)) % 2 == 0


def play_game(opponent: str, map_name: str, we_first: bool, a, log_prefix: str, seed: int) -> dict:
    """One full game over the protocol: fake server + main.py + the teammate's bot. Returns one row."""
    state = load_map(map_name, a.max_ply)
    server = FakeServer(state, port=0, move_timeout=a.timeout, seed=seed, log=lambda *_: None,
                        game_seconds=a.game_seconds)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    host, port = "127.0.0.1", str(server.port)
    py = sys.executable
    ours = [py, "main.py", "--name", "Splitter", host, port]
    theirs = [py, os.path.join("tools", "play_bot.py"), opponent, host, port, "--time", str(a.opp_time)]
    env = dict(os.environ, SPLITTER_MODEL=a.model, SPLITTER_TIME=str(a.time), PYTHONUNBUFFERED="1")
    order = [("us", ours), ("them", theirs)] if we_first else [("them", theirs), ("us", ours)]
    t0 = time.time()
    with ExitStack() as files:
        procs = {}
        for i, (who, cmd) in enumerate(order):
            log = files.enter_context(open(f"{log_prefix}_{who}.log", "w"))
            procs[who] = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            deadline = time.time() + 60            # connection order decides who is player 0
            while server.connected <= i and time.time() < deadline and thread.is_alive():
                time.sleep(0.05)
        longest = a.game_seconds if a.game_seconds else a.max_ply * (a.timeout + 0.5)
        thread.join(timeout=longest + 120)         # the server ends the game itself; this is a safety net
        for p in procs.values():
            try:
                p.wait(timeout=15)
            except subprocess.TimeoutExpired:
                p.kill()
    r = server.result or {"reason": "server-error", "winner": None, "timeouts": [0, 0], "cheat": None,
                          "totals": (0, 0), "plies": 0}
    us = 0 if we_first else 1                      # our player number = our species index (0 = V)
    totals = r.get("totals", (0, 0))
    if r.get("winner") is None:
        score, result = 0.5, "draw"
    elif r["winner"] == us:
        score, result = 1.0, "WIN"
    else:
        score, result = 0.0, "loss"
    with open(f"{log_prefix}_us.log", errors="replace") as f:
        our_log = f.read()
    evals = [float(x) for x in re.findall(r"\(eval: ([0-9.]+)ms\)", our_log)]
    cheat = r.get("cheat")
    return {"opponent": opponent, "map": map_name, "we_connect_first": we_first,
            "our_species": "Vampires" if us == 0 else "Werewolves", "result": result, "score": score,
            "reason": r.get("reason"), "plies": r.get("plies"), "our_total": totals[us],
            "their_total": totals[1 - us], "our_timeouts": r.get("timeouts", [0, 0])[us],
            "their_timeouts": r.get("timeouts", [0, 0])[1 - us],
            "our_slowest_move_ms": round(max(evals), 0) if evals else "",
            "watchdog_fallbacks": our_log.count("[Watchdog]"),
            "cheat": f"{cheat[0]}: {cheat[1]}" if cheat else "", "minutes": round((time.time() - t0) / 60, 1)}


def summarize(rows, model: str) -> str:
    """Per-opponent table (markdown) of the finished games."""
    lines = [f"# Real-conditions matches: Splitter ({model}) vs the teammates' bots", "",
             "| Opponent | Games | W - D - L | Score | Avg. margin | Our timeouts | Cheats | Slowest move |",
             "|---|---|---|---|---|---|---|---|"]
    groups = {}
    for r in rows:
        groups.setdefault(r["opponent"], []).append(r)
    for name, rs in list(groups.items()) + [("**All**", rows)]:
        n = len(rs)
        wins = sum(r["result"] == "WIN" for r in rs)
        draws = sum(r["result"] == "draw" for r in rs)
        losses = n - wins - draws
        score = 100 * sum(r["score"] for r in rs) / n
        margin = sum(r["our_total"] - r["their_total"] for r in rs) / n
        timeouts = sum(r["our_timeouts"] for r in rs)
        cheats = sum(1 for r in rs if r["cheat"])
        slow = [r["our_slowest_move_ms"] for r in rs if r["our_slowest_move_ms"] != ""]
        slowest = f"{max(slow):.0f} ms" if slow else "-"
        lines.append(f"| {name} | {n} | {wins} - {draws} - {losses} | {score:.0f}% | {margin:+.1f} | "
                     f"{timeouts} | {cheats} | {slowest} |")
    lines += ["", (f"{len(rows)} games over the real protocol (2 s per move, 200 plies, 5-minute clock), "
                   "one game at a time, no speed-ups. Margin = our creatures - theirs at the end.")]
    return "\n".join(lines)


def store_history(rows, a, run_id: str):
    """One line per opponent in arena/results/history.csv (same file as the arena and server matches)."""
    new = not os.path.exists(HISTORY)
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    with open(HISTORY, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["run", "bot", "opponents", "maps", "games", "time", "seed",
                                          "games_played", "score", "se", "problems"])
        if new:
            w.writeheader()
        for opp in dict.fromkeys(r["opponent"] for r in rows):
            rs = [r for r in rows if r["opponent"] == opp]
            p = sum(r["score"] for r in rs) / len(rs)
            se = math.sqrt(max(p * (1 - p), 1e-9) / len(rs))
            w.writerow({"run": run_id, "bot": f"Splitter-{a.model} (real conditions)", "opponents": opp,
                        "maps": a.maps, "games": a.games, "time": a.time, "seed": a.seed,
                        "games_played": len(rs), "score": round(100 * p, 1), "se": round(100 * se, 1),
                        "problems": sum(r["our_timeouts"] for r in rs) + sum(1 for r in rs if r["cheat"])})


def main():
    """Command line: play every (opponent, game), record each game at once, print the summary."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", choices=("flagship", "backup"), default="flagship", help="which of our two models plays")
    ap.add_argument("--opp", nargs="+", default=None, help=f"opponents (default: {' '.join(MAIN_BOTS)})")
    ap.add_argument("--all", action="store_true", help="every teammate bot: " + " ".join(TEAMMATE_BOTS))
    ap.add_argument("--games", type=int, default=3, help="games per opponent (default 3)")
    ap.add_argument("--maps", default="testmap.xml,thetrap.xml",
                    help="maps; the games cycle through every (map, side) combination")
    ap.add_argument("--time", type=float, default=1.5, help="our seconds per move (tournament: 1.5)")
    ap.add_argument("--opp-time", type=float, default=1.5, help="the teammates' bots' seconds per move")
    ap.add_argument("--timeout", type=float, default=2.0, help="server limit per move (real server: 2.0)")
    ap.add_argument("--max-ply", type=int, default=200, help="plies per game (real server: 200)")
    ap.add_argument("--game-seconds", type=float, default=300.0, help="game clock (real server: 300)")
    ap.add_argument("--seed", type=int, default=1, help="dice of the random battles")
    ap.add_argument("--out", default=None, help="results folder (default arena/results/teammates/<time>_<model>)")
    ap.add_argument("--no-history", action="store_true", help="do not append to arena/results/history.csv (tests)")
    a = ap.parse_args()
    opponents = list(TEAMMATE_BOTS) if a.all else (a.opp or MAIN_BOTS)
    missing = sorted({TEAMMATE_BOTS[o] for o in opponents if o in TEAMMATE_BOTS
                      and not os.path.isdir(os.path.join(ROOT, "arena", "vendor", TEAMMATE_BOTS[o]))})
    if missing:
        sys.exit(f"The teammates' bots are missing ({', '.join(missing)}): run  python -m arena.fetch_opponents")
    keep_awake()
    maps = [m.strip() for m in a.maps.split(",") if m.strip()]
    run_id = time.strftime("%Y%m%d-%H%M%S") + f"_{a.model}"
    out = a.out or os.path.join(ROOT, "arena", "results", "teammates", run_id)
    os.makedirs(os.path.join(out, "logs"), exist_ok=True)
    total = len(opponents) * a.games
    print(f"Splitter ({a.model}) vs {', '.join(opponents)}: {a.games} games each = {total} games, "
          f"one at a time, real server conditions. Results: {out}\n")
    rows = []
    with open(os.path.join(out, "games.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        n = 0
        for opp in opponents:
            for g in range(a.games):
                n += 1
                map_name, we_first = schedule(g, maps)
                prefix = os.path.join(out, "logs", f"{opp}_game{g + 1}")
                print(f"[{n:2d}/{total}] vs {opp:16s} game {g + 1}  {map_name:12s} "
                      f"we are {'Vampires (move first)' if we_first else 'Werewolves'} ...", end=" ", flush=True)
                row = play_game(opp, map_name, we_first, a, prefix, a.seed + n)
                row["game"] = g + 1
                rows.append(row)
                w.writerow(row)
                f.flush()
                extra = f", CHEAT {row['cheat']}" if row["cheat"] else ""
                print(f"{row['result']:4s} {row['our_total']:3d}-{row['their_total']:<3d} ({row['reason']}, "
                      f"{row['plies']} plies, {row['minutes']} min{extra})", flush=True)
    summary = summarize(rows, a.model)
    with open(os.path.join(out, "summary.md"), "w", encoding="utf-8") as f:
        f.write(summary + "\n")
    if not a.no_history:
        store_history(rows, a, run_id)
    print("\n" + summary)
    print(f"\nSaved: {os.path.join(out, 'games.csv')}, summary.md, logs/; one line per opponent in {HISTORY}")


if __name__ == "__main__":
    main()
