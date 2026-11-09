"""
tourney.py  (our own file)

Head-to-head matches between any two bots on the map suite, both species, several seeds, in parallel.

Bot specs:
    deep                      DeepAgent with default parameters
    deep:{"time_limit":0.5}   DeepAgent with parameters (JSON)
    expecti                   the previous SearchAgent (depth-2 expectiminimax)
    panel:Grabber             a sparring_agents opponent
    rival:Othmane             a teammate's bot from rivals/ (see rival_bots.py)

    python3 tourney.py deep rival:Othmane --maps all --seeds 2 --workers 2
    python3 tourney.py 'deep:{"squash":0.4}' deep --maps 1,2,8,10 --seeds 3

Prints one line per game and a summary: score of A (win 1, draw 0.5), +- one standard error.
"""
import argparse
import json
import math
import sys
import time
from multiprocessing import Pool

from game_state import Species
from maps import build_suite
from selfplay import play_game

V, W = Species.VAMPIRE, Species.WEREWOLF


def make_bot(spec: str):
    kind, _, arg = spec.partition(":")
    if kind == "deep":
        from deep_agent import DeepAgent
        return DeepAgent(**(json.loads(arg) if arg else {}))
    if kind == "expecti":
        from search_agent import SearchAgent
        return SearchAgent("Expecti", **(json.loads(arg) if arg else {}))
    if kind == "panel":
        from sparring_agents import make_opponent
        return make_opponent(arg)
    if kind == "rival":
        from rival_bots import make_rival
        return make_rival(arg)
    if kind == "safe":                                   # the exact tournament stack: SafeAgent(DeepAgent)
        from deep_agent import DeepAgent
        from safe_agent import SafeAgent
        return SafeAgent("Safe", inner=DeepAgent(**(json.loads(arg) if arg else {})))
    raise ValueError(spec)


def _map(ident):
    """An index into maps.build_suite(), or the path of an XML map file."""
    if isinstance(ident, int):
        return build_suite()[ident]
    from map_loader import load_map
    return ident.replace(".xml", ""), load_map(ident)


def play_one(task):
    spec_a, spec_b, map_index, a_is_vampire, seed = task
    name, board = _map(map_index)
    a_sp = V if a_is_vampire else W
    b_sp = W if a_is_vampire else V
    t = time.time()
    r = play_game(board, {a_sp: make_bot(spec_a), b_sp: make_bot(spec_b)}, first=V, seed=seed)
    score = 0.5 if r.winner is None else (1.0 if r.winner == a_sp else 0.0)
    sa, sb = r.stats[a_sp], r.stats[b_sp]
    return dict(map=name, a_side="V" if a_is_vampire else "W", seed=seed, score=score, plies=r.plies,
                a_left=r.vampires if a_is_vampire else r.werewolves,
                b_left=r.werewolves if a_is_vampire else r.vampires,
                a_max=round(max(sa.decision_times, default=0), 2), b_max=round(max(sb.decision_times, default=0), 2),
                a_problem=sa.last_problem, b_problem=sb.last_problem,
                forfeit=None if r.forfeit is None else r.forfeit.value, secs=round(time.time() - t))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--maps", default="all")
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--seed0", type=int, default=100)
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    n_maps = len(build_suite())
    maps = list(range(n_maps)) if args.maps == "all" else [int(m) if m.isdigit() else m
                                                           for m in args.maps.split(",")]
    tasks = [(args.a, args.b, m, av, args.seed0 + 1000 * s + (m if isinstance(m, int) else 50 + k))
             for s in range(args.seeds) for k, m in enumerate(maps) for av in (True, False)]
    rows = []
    with Pool(args.workers, maxtasksperchild=4) as pool:
        for row in pool.imap_unordered(play_one, tasks):
            rows.append(row)
            print(json.dumps(row), flush=True)
    n = len(rows)
    s = sum(r["score"] for r in rows) / n
    wins = sum(r["score"] == 1 for r in rows)
    draws = sum(r["score"] == 0.5 for r in rows)
    se = math.sqrt(max(s * (1 - s), 0.01) / n)
    print(f"SUMMARY {args.a} vs {args.b}: {n} games, A wins {wins}, draws {draws}, losses {n - wins - draws} "
          f"| score {100 * s:.1f}% +- {100 * se:.1f} | A max time {max(r['a_max'] for r in rows)}s "
          f"| problems A {sum(bool(r['a_problem']) for r in rows)} B {sum(bool(r['b_problem']) for r in rows)}")


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    main()
