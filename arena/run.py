"""
Arena: measure a bot against a panel of opponents on a suite of maps.

    python -m arena.run                                      # Splitter vs default panel, all maps
    python -m arena.run --bot Splitter Splitter-Classic --opp Apex RaceMCTS --games 2 --time 0.3
    python -m arena.run --bot "Splitter:c=0.9,rollout_depth=0" --maps villages,given
    python -m arena.run --bot Splitter --opp Apex --maps testmap --watch      # one game, verbose

Every (opponent, map) pair is played with our bot on BOTH species, `--games` times each, and
the first player alternates. Seeds are fixed, so two configurations meet the same dice.
Score: win = 1, draw = 0.5, loss = 0. "+-" is one standard error; differences smaller than
~2 standard errors are noise. Rows are also saved to arena/results/*.csv.
"""
import argparse
import csv
import json
import math
import os
import sys
import time
import zlib
from collections import defaultdict
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from arena.maps import build_suite, render
from arena.opponents import PANEL, STYLED_PANEL, make_bot
from arena.referee import play_game
from splitter.rules import V, W

FIELDS = ["bot", "opp", "map", "side", "first", "seed", "score", "margin", "plies", "reason",
          "our_max_s", "our_avg_s", "our_timeouts", "our_illegal", "our_crashes", "our_splits",
          "our_max_groups", "opp_problems", "problem"]


def _file_safe(name: str, limit: int = 120) -> str:
    """A bot spec as a file-name part ('py:C:/x/bot.py:Cls', 'Splitter:c=0.8' contain : / = ...)."""
    return "".join(c if c.isalnum() or c in "-+." else "_" for c in name)[:limit]


def _play_task(task):
    """Worker: play one game (bot vs opponent on a map and side) and return its CSV row."""
    bot_spec, opp, map_name, maps_arg, side, first, seed, t, hard, max_ply, log_dir, trace_dir = task[:12]
    game_seconds = task[12] if len(task) > 12 else None
    state = dict(build_suite(maps_arg, max_ply))[map_name]
    ours = make_bot(bot_spec, t)
    theirs = make_bot(opp, t)
    bots = {side: ours, 1 - side: theirs}
    r = play_game(state, bots, first=first, seed=seed, hard_limit=hard, record=trace_dir is not None,
                  game_seconds=game_seconds)
    if trace_dir is not None:             # full game record (tools/tune_eval.py)
        os.makedirs(trace_dir, exist_ok=True)
        names = {side: bot_spec, 1 - side: opp}
        rec = {"map": map_name, "rows": state.rows, "cols": state.cols, "max_ply": max_ply, "seed": seed,
               "names": [names[V], names[W]], "winner": r.winner, "trace": r.trace}
        fn = f"{_file_safe(opp)}_{map_name}_{'VW'[side]}{'VW'[first]}_{seed}.json"
        with open(os.path.join(trace_dir, fn), "w") as f:
            json.dump(rec, f)
    s = r.stats[side]
    o = r.stats[1 - side]
    score = 0.5 if r.winner is None else (1.0 if r.winner == side else 0.0)
    if score < 1.0:                       # keep the move log of every game we did not win
        d = log_dir
        os.makedirs(d, exist_ok=True)
        fn = f"{_file_safe(bot_spec, 60)}_{_file_safe(opp, 60)}_{map_name}_{'VW'[side]}{'VW'[first]}_{seed}.txt"
        with open(os.path.join(d, fn), "w") as f:
            f.write(render(state) + "\n" + "\n".join(r.log)
                    + f"\nresult score={score} totals={r.totals} {r.reason}\n")
    return {
        "bot": bot_spec, "opp": opp, "map": map_name, "side": "VW"[side], "first": "VW"[first],
        "seed": seed, "score": score, "margin": r.totals[side] - r.totals[1 - side],
        "plies": r.plies, "reason": r.reason,
        "our_max_s": round(max(s.times, default=0.0), 3),
        "our_avg_s": round(sum(s.times) / max(1, len(s.times)), 3),
        "our_timeouts": s.timeouts, "our_illegal": s.illegal, "our_crashes": s.crashes,
        "our_splits": s.splits, "our_max_groups": s.max_groups,
        "opp_problems": o.timeouts + o.illegal + o.crashes,
        "problem": (s.problem or ("opp: " + o.problem if o.problem else ""))[:300],
    }


def _score(rows):
    """Win rate (win 1, draw 0.5) with its standard error."""
    n = len(rows)
    if not n:
        return 0.0, 0.0, 0
    p = sum(r["score"] for r in rows) / n
    return p, math.sqrt(max(p * (1 - p), 1e-9) / n), n


def report(rows, title=""):
    """Print the results grouped by opponent, map, our side and first player."""
    p, se, n = _score(rows)
    print(f"\n=== {title}  {n} games  OVERALL {100 * p:5.1f}% +- {100 * se:.1f} ===")
    for key, label in (("opp", "opponent"), ("map", "map"), ("side", "our side"), ("first", "first player")):
        groups = defaultdict(list)
        for r in rows:
            groups[r[key]].append(r)
        print(f"  by {label}:")
        for k in sorted(groups):
            g = groups[k]
            p, se, n = _score(g)
            w = sum(1 for r in g if r["score"] == 1)
            d = sum(1 for r in g if r["score"] == 0.5)
            margin = sum(r["margin"] for r in g) / n
            print(f"    {k:18s} {100 * p:5.1f}% +- {100 * se:4.1f}   W{w:3d} D{d:3d} L{n - w - d:3d}"
                  f"   margin {margin:+6.1f}")
    probs = sum(r["our_timeouts"] + r["our_illegal"] + r["our_crashes"] for r in rows)
    slow = max((r["our_max_s"] for r in rows), default=0)
    splits = sum(r["our_splits"] for r in rows) / max(1, len(rows))
    print(f"  our problems (timeouts+illegal+crashes): {probs}   slowest move: {1000 * slow:.0f} ms"
          f"   split-turns/game: {splits:.1f}")
    bad = [r for r in rows if r["problem"] and (r["our_timeouts"] or r["our_illegal"] or r["our_crashes"])]
    for r in bad[:5]:
        print(f"    !! {r['opp']} {r['map']} {r['side']}: {r['problem']}")


# expensive opponents (they think for their whole time budget): scheduled first
SEARCH_BOTS = ("Apex", "RaceMCTS", "Expecti", "MonteCarlo", "ShallowMinimax", "AIAgent", "Splitter", "Snap:",
               "Styled:")
FAST_PANEL = ["Apex", "RaceMCTS", "Expecti", "TacticalSplitter"]   # the most discriminating opponents


def _cost(task) -> float:
    """Rough game duration, to schedule the longest games first (no idle workers at the end)."""
    opp, map_name, maps_arg = task[1], task[2], task[3]
    state = dict(build_suite(maps_arg))[map_name]
    thinkers = 1 + any(opp.startswith(b) for b in SEARCH_BOTS)
    return thinkers * (state.rows * state.cols) ** 0.5


HISTORY = os.path.join(ROOT, "arena", "results", "history.csv")
COMPARISONS = os.path.join(ROOT, "arena", "results", "comparisons.csv")


def _append_csv(path, fields, records):
    """Append records to a persistent CSV (header written once)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(records)


def store_history(run_id, bots, opps, args, rows, comparisons):
    """Persist one summary line per bot (history.csv) and per paired comparison (comparisons.csv)."""
    common = {"run": run_id, "opponents": " ".join(opps), "maps": args.maps, "games": args.games,
              "time": args.time, "seed": args.seed}
    recs = []
    for b in bots:
        rs = [r for r in rows if r["bot"] == b]
        p, se, n = _score(rs)
        recs.append({**common, "bot": b, "games_played": n, "score": round(100 * p, 1), "se": round(100 * se, 1),
                     "problems": sum(r["our_timeouts"] + r["our_illegal"] + r["our_crashes"] for r in rs)})
    _append_csv(HISTORY, ["run", "bot", "opponents", "maps", "games", "time", "seed", "games_played",
                          "score", "se", "problems"], recs)
    if comparisons:
        _append_csv(COMPARISONS, ["run", "bot", "reference", "scope", "delta", "se", "games", "opponents",
                                  "maps", "games_per_side", "time", "seed"],
                    [{**c, "run": run_id, "opponents": common["opponents"], "maps": args.maps,
                      "games_per_side": args.games, "time": args.time, "seed": args.seed} for c in comparisons])


def compare(rows, bots):
    """Paired comparison of every bot with the first one: same opponent, map, side and seed.
    Prints the table and returns it as records (stored in comparisons.csv)."""
    records = []
    key = lambda r: (r["opp"], r["map"], r["side"], r["seed"])
    by_bot = {b: {key(r): r["score"] for r in rows if r["bot"] == b} for b in bots}
    ref = bots[0]
    print()
    print(f"=== paired comparison vs {ref} (same games; +- = paired standard error) ===")
    for b in bots[1:]:
        common = [k for k in by_bot[b] if k in by_bot[ref]]
        if not common:
            continue
        print(f"  {b}:")
        groups = {"OVERALL": common}
        for k in common:
            groups.setdefault(k[0], []).append(k)
        for name in ["OVERALL"] + sorted(g for g in groups if g != "OVERALL"):
            ks = groups[name]
            d = [by_bot[b][k] - by_bot[ref][k] for k in ks]
            n = len(d)
            mean = sum(d) / n
            var = sum((x - mean) ** 2 for x in d) / max(1, n - 1)
            se = math.sqrt(var / n)
            flag = "  <-- better" if mean > 2 * se else ("  <-- worse" if mean < -2 * se else "")
            print(f"    {name:18s} {100 * mean:+6.1f} pts +- {100 * se:4.1f}  ({n} games){flag}")
            records.append({"bot": b, "reference": ref, "scope": name, "delta": round(100 * mean, 1),
                            "se": round(100 * se, 1), "games": n})
    return records


def paired_delta(rows, ref: str, bot: str):
    """(mean paired difference, its standard error, games) of `bot` vs `ref` on the same games."""
    def key(r):
        return (r["opp"], r["map"], r["side"], r["first"], r["seed"])
    a = {key(r): r["score"] for r in rows if r["bot"] == ref}
    d = [r["score"] - a[key(r)] for r in rows if r["bot"] == bot and key(r) in a]
    n = len(d)
    if n < 2:
        return 0.0, 1.0, n
    mean = sum(d) / n
    var = sum((x - mean) ** 2 for x in d) / (n - 1)
    return mean, math.sqrt(var / n), n


def _row_key(r) -> tuple:
    """Identity of one game of a run: (bot, opponent, map, our side, first player, seed)."""
    return (r["bot"], r["opp"], r["map"], r["side"], r["first"], int(r["seed"]))


def _load_rows(path: str) -> list:
    """Rows of an earlier (possibly interrupted) run, with numeric fields converted back."""
    ints = ("seed", "margin", "plies", "our_timeouts", "our_illegal", "our_crashes", "our_splits",
            "our_max_groups", "opp_problems")
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            r["score"] = float(r["score"])
            for k in ints:
                r[k] = int(r[k])
            for k in ("our_max_s", "our_avg_s"):
                r[k] = float(r[k])
            rows.append(r)
    return rows


def _rounds(tasks, n: int):
    """Split tasks into n rounds by GAME (all bots of one game stay in the same round), each round
    with a mix of long and short games, longest first inside a round."""
    if n <= 1:
        return [tasks]
    games = list(dict.fromkeys((t[1], t[2], t[4], t[5], t[6]) for t in tasks))   # already longest first
    which = {g: i % n for i, g in enumerate(games)}
    return [[t for t in tasks if which[(t[1], t[2], t[4], t[5], t[6])] == r] for r in range(n)]


def keep_awake() -> None:
    """
    Windows: keep the machine awake while this process runs (a sleep in the middle of a benchmark
    turns the games in progress into fake timeouts). Released automatically when the process ends.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        es_continuous, es_system_required = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | es_system_required)
    except (AttributeError, OSError):
        pass


def main():
    """Command line: build every (bot, opponent, map, side, game) task, run them in ONE pool, report."""
    keep_awake()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bot", nargs="+", default=["Splitter"],
                    help="one or more bot specs; several = one shared pool + paired comparison vs the first")
    ap.add_argument("--opp", nargs="*", default=None, help=f"default: {' '.join(PANEL)}")
    ap.add_argument("--panel", choices=("full", "fast", "styled"), default="full",
                    help=f"fast = {' '.join(FAST_PANEL)} (screening); styled = Styled:1..6; ignored if --opp is given")
    ap.add_argument("--maps", default="all", help="all | given | sym | villages | prize | close | sparse | names,...")
    ap.add_argument("--games", type=int, default=1, help="games per (opponent, map, side)")
    ap.add_argument("--time", type=float, default=0.3, help="seconds per move for every search bot")
    ap.add_argument("--hard", type=float, default=None, help="timeout (default: time + 1.0)")
    ap.add_argument("--max-ply", type=int, default=200)
    ap.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 2))
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--watch", action="store_true", help="play ONE game verbosely (first bot/opp/map)")
    ap.add_argument("--out", default=None, help="csv path (default arena/results/<time>_<bot>.csv)")
    ap.add_argument("--game-seconds", type=float, default=None,
                    help="game clock (the server's MaxGameDuration, total thinking time); default: none")
    ap.add_argument("--resume", default=None,
                    help="csv of an interrupted run with the same arguments: its games are not replayed")
    ap.add_argument("--slots", default=None,
                    help="JSON from tools/informative_slots.py: play only these (opponent, map) slots")
    ap.add_argument("--drop-worse", action="store_true",
                    help="play in 4 rounds; after each, stop candidates clearly worse than the first bot")
    ap.add_argument("--save-all-logs", action="store_true",
                    help="save every game's full move record (ground truth) to arena/results/traces/<run>/")
    a = ap.parse_args()

    opps = a.opp or {"fast": FAST_PANEL, "styled": STYLED_PANEL}.get(a.panel, PANEL)
    slots = None
    if a.slots:                                  # only the informative (opponent, map) slots
        with open(a.slots) as f:
            slots = {tuple(x) for x in json.load(f)["slots"]}
        if a.opp:                                # --opp narrows the slot file to these opponents
            slots = {s for s in slots if s[0] in a.opp}
        opps = list(dict.fromkeys(o for o, _ in sorted(slots)))
        a.maps = ",".join(sorted({m for _, m in slots}))
    suite = build_suite(a.maps, a.max_ply)
    hard = a.hard if a.hard is not None else a.time + 1.0
    bots = a.bot

    if a.watch:
        _, state = suite[0]
        players = {V: make_bot(bots[0], a.time), W: make_bot(opps[0], a.time)}
        print(render(state))
        r = play_game(state, players, seed=a.seed, hard_limit=hard, verbose=True, render=render)
        print()
        print(f"winner: {'VW'[r.winner] if r.winner is not None else 'draw'}  totals V/W {r.totals}"
              f"  reason {r.reason}  problems: {r.stats[V].problem} {r.stats[W].problem}")
        return

    label = "+".join(bots) if len(bots) <= 3 else f"{bots[0]}+{len(bots) - 1}more"
    run_id = time.strftime("%Y%m%d-%H%M%S") + "_" + _file_safe(label, 80)
    log_dir = os.path.join(ROOT, "arena", "results", "logs", run_id)
    trace_dir = os.path.join(ROOT, "arena", "results", "traces", run_id) if a.save_all_logs else None
    tasks = []
    for bot in bots:
        for opp in opps:
            for map_name, _ in suite:
                for side in (V, W):
                    for g in range(a.games):
                        if slots is not None and (opp, map_name) not in slots:
                            continue
                        first = V if g % 2 == 0 else W
                        # one seed per game (independent dice across opponents/maps), but the same
                        # seed for the same game for every bot, so configurations meet the same dice
                        seed = a.seed + zlib.crc32(f"{opp}|{map_name}|{side}|{g}".encode()) % 1000003
                        tasks.append((bot, opp, map_name, a.maps, side, first, seed, a.time, hard, a.max_ply,
                                      log_dir, trace_dir, a.game_seconds))
    tasks.sort(key=_cost, reverse=True)          # longest games first: no straggler tail
    out = a.resume or a.out or os.path.join(ROOT, "arena", "results", run_id + ".csv")
    rows = _load_rows(a.resume) if a.resume else []
    done = {_row_key(r) for r in rows}
    tasks = [t for t in tasks if (t[0], t[1], t[2], "VW"[t[4]], "VW"[t[5]], t[6]) not in done]
    print(f"{bots} vs {opps} on {len(suite)} maps: {len(tasks)} games to play"
          + (f" ({len(rows)} already in {out})" if rows else "") + f", {a.time}s/move, {a.workers} workers")
    t0 = time.time()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "a" if a.resume else "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not a.resume:
            w.writeheader()

        def keep(row):
            """Every finished game is written at once: an interrupted run can be resumed."""
            rows.append(row)
            w.writerow(row)
            f.flush()
        if a.workers > 1:
            rounds = _rounds(tasks, 4 if a.drop_worse else 1)
            alive = set(bots)
            played = 0
            with Pool(a.workers) as pool:
                for r_i, batch in enumerate(rounds):
                    batch = [t for t in batch if t[0] in alive]
                    for row in pool.imap_unordered(_play_task, batch):
                        keep(row)
                        played += 1
                        if played % max(1, len(tasks) // 20) == 0:
                            print(f"  {played}/{len(tasks)} games ({time.time() - t0:.0f}s)", flush=True)
                    if a.drop_worse and r_i < len(rounds) - 1:
                        for b in bots[1:]:
                            m, se, n = paired_delta(rows, bots[0], b)
                            if b in alive and n >= 20 and m + 2 * se < 0:
                                alive.discard(b)
                                print(f"  round {r_i + 1}: {b} dropped ({100 * m:+.1f} +- {100 * se:.1f} "
                                      f"after {n} games)", flush=True)
        else:
            for i, task in enumerate(tasks, 1):
                keep(_play_task(task))
                print(f"  {i}/{len(tasks)} {rows[-1]['opp']} {rows[-1]['map']} {rows[-1]['side']}: "
                      f"{rows[-1]['score']} ({rows[-1]['reason']})", flush=True)
    elapsed = time.time() - t0
    for bot in bots:
        report([r for r in rows if r["bot"] == bot], f"{bot} ({elapsed:.0f}s for the whole run)")
    comparisons = compare(rows, bots) if len(bots) > 1 else []
    store_history(run_id, bots, opps, a, rows, comparisons)
    print(f"  rows saved to {out}")
    print(f"  logs of games not won: {log_dir}")
    print(f"  summary appended to {HISTORY}" + (f" and {COMPARISONS}" if comparisons else ""))


if __name__ == "__main__":
    main()
