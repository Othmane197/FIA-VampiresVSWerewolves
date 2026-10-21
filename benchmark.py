"""
benchmark.py  (our own file)

Measures how strong a configuration of our bot is: it plays the whole panel (sparring_agents.py)
on the whole map suite (maps.py), as BOTH species, with fixed seeds. Vampires always move first (official server); an illegal or empty
turn loses the game at once.

    python3 benchmark.py                       # baseline: depth 2, race_weight 0.5
    python3 benchmark.py --depth 3 --race 0.3  # try another configuration
    python3 benchmark.py --games 4 --opp Rusher Turtle

Score of a game: win = 1, draw = 0.5, loss = 0. "score%" is the average over games.
The +- is one standard error (sqrt(p(1-p)/n)); two configurations whose difference is smaller than
about two of these are NOT distinguishable. This is a lower bound on the noise (games on one map
are not independent), so be conservative.

Importable: run_benchmark(cfg, games_per_side=2, opponents=None, maps=None, workers=2) -> Report
"""
import argparse
import math
import time
from collections import defaultdict
from dataclasses import dataclass
from multiprocessing import Pool
from typing import Dict, List, Optional, Tuple

from game_state import Species
from maps import build_suite
from search_agent import SearchAgent
from selfplay import play_game
from sparring_agents import PANEL, make_opponent

V, W = Species.VAMPIRE, Species.WEREWOLF

# One row per game: (opponent, map, our_species_name, score, plies, our_max_decision_s, problems)
Row = Tuple[str, str, str, float, int, float, int]


def _play_one(task) -> Row:
    cfg, opp, map_index, ours_is_vampire, first_is_ours, seed = task
    name, board = build_suite()[map_index]
    ours = V if ours_is_vampire else W
    theirs = W if ours_is_vampire else V
    agents = {ours: SearchAgent("Ours", **cfg), theirs: make_opponent(opp)}
    r = play_game(board, agents, first=V, seed=seed)       # vampires always start
    if r.winner is None:
        score = 0.5
    else:
        score = 1.0 if r.winner == ours else 0.0
    st = r.stats[ours]
    problems = st.illegal + st.timeouts + st.crashes
    return (opp, name, ours.value, score, r.plies, max(st.decision_times, default=0.0), problems)


@dataclass
class Report:
    rows: List[Row]
    cfg: dict
    seconds: float

    def score(self, rows=None) -> Tuple[float, float, int]:
        rows = self.rows if rows is None else rows
        n = len(rows)
        if n == 0:
            return 0.0, 0.0, 0
        p = sum(r[3] for r in rows) / n
        return p, math.sqrt(max(p * (1 - p), 1e-9) / n), n

    def by(self, index: int) -> Dict[str, List[Row]]:
        d = defaultdict(list)
        for r in self.rows:
            d[r[index]].append(r)
        return d

    @property
    def problems(self) -> int:
        return sum(r[6] for r in self.rows)

    @property
    def slowest(self) -> float:
        return max(r[5] for r in self.rows)

    def print(self, per_map: bool = True) -> None:
        p, se, n = self.score()
        print(f"\nconfig {self.cfg}   ({n} games, {self.seconds:.0f}s)")
        print(f"  OVERALL  {100 * p:5.1f}% +- {100 * se:.1f}")
        print(f"  by opponent:")
        for opp, rows in self.by(0).items():
            p, se, n = self.score(rows)
            draws = sum(1 for r in rows if r[3] == 0.5)
            print(f"    {opp:8s} {100 * p:5.1f}% +- {100 * se:4.1f}   ({n} games, {draws} draws)")
        sides = self.by(2)
        print("  by our species: " + ",  ".join(
            f"{k} {100 * self.score(v)[0]:.0f}%" for k, v in sides.items()))
        if per_map:
            print("  by map: " + ",  ".join(
                f"{k} {100 * self.score(v)[0]:.0f}%" for k, v in self.by(1).items()))
        print(f"  illegal/timeouts/crashes: {self.problems}   slowest decision: {1000 * self.slowest:.0f} ms")


def run_benchmark(cfg: Optional[dict] = None, games_per_side: int = 2,
                  opponents: Optional[List[str]] = None, maps: Optional[List[str]] = None,
                  workers: int = 2, seed0: int = 1000) -> Report:
    cfg = dict(cfg or {})
    opponents = opponents or list(PANEL)
    suite = build_suite()
    indices = [i for i, (n, _) in enumerate(suite) if maps is None or n in maps]
    tasks = []
    for opp in opponents:
        for mi in indices:
            for ours_is_vampire in (True, False):
                for g in range(games_per_side):
                    seed = seed0 + g                       # same seeds for every configuration
                    tasks.append((cfg, opp, mi, ours_is_vampire, g % 2 == 0, seed))
    t0 = time.perf_counter()
    if workers > 1:
        with Pool(workers) as pool:
            rows = pool.map(_play_one, tasks, chunksize=4)
    else:
        rows = [_play_one(t) for t in tasks]
    return Report(rows, cfg, time.perf_counter() - t0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--race", type=float, default=0.5)
    ap.add_argument("--battles", type=int, default=2)
    ap.add_argument("--time", type=float, default=1.5)
    ap.add_argument("--games", type=int, default=2, help="games per (opponent, map, species)")
    ap.add_argument("--opp", nargs="*", default=None)
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    cfg = dict(depth=a.depth, race_weight=a.race, max_chance_battles=a.battles, time_limit=a.time)
    run_benchmark(cfg, a.games, a.opp, workers=a.workers).print()
