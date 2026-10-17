"""
selfplay.py  (our own file)

Local referee: plays full games between two agents WITHOUT the real server, so we can
measure win rates, decision times and rule violations on our own machine.

An agent is any object with   compute_moves(state: GameState) -> list of
(src_x, src_y, count, dst_x, dst_y)   (the interface of the repo's AIAgent).

Run a demo:   python3 selfplay.py            (or: python3 selfplay.py 20   for 20 games per side)

Assumptions NOT yet checked against the real server (see notes in the chat):
  * which species moves first (setting `first`, default vampires);
  * battles follow the engine's Monte-Carlo mode (game_engine.apply_moves, deterministic=False);
  * an illegal / late / crashed turn is treated as a skipped turn (the real server may differ).
"""
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from game_engine import BoardState
from game_state import Species
from map_loader import load_map
from state_converter import state_from_board

TIME_LIMIT = 2.0  # seconds per turn (project specification)


def other(species: Species) -> Species:
    return Species.WEREWOLF if species == Species.VAMPIRE else Species.VAMPIRE


@dataclass
class PlayerStats:
    decision_times: List[float] = field(default_factory=list)
    illegal: int = 0      # returned moves that break Rules 1-6
    timeouts: int = 0     # took longer than the time limit
    crashes: int = 0      # compute_moves raised an exception
    last_problem: str = ""


@dataclass
class GameResult:
    winner: Optional[Species]          # None = draw
    plies: int
    vampires: int
    werewolves: int
    humans_left: int
    stats: Dict[Species, PlayerStats]


def _start_cell(board: BoardState, species: Species) -> Optional[Tuple[int, int]]:
    groups = board.get_species_groups(species)
    return groups[0][0] if groups else None


def play_game(initial: BoardState, agents: Dict[Species, object], first: Species = Species.VAMPIRE,
              time_limit: float = TIME_LIMIT, seed: Optional[int] = None,
              deterministic_battles: bool = False, verbose: bool = False) -> GameResult:
    """Play one full game from `initial` (it is not modified)."""
    if seed is not None:
        random.seed(seed)
    board = initial.clone()
    homes = {sp: _start_cell(initial, sp) for sp in Species}
    stats = {sp: PlayerStats() for sp in Species}
    current = first

    while not board.is_game_over()[0]:
        agent, st = agents[current], stats[current]
        state = state_from_board(board, current, homes[current])

        moves = None
        t0 = time.perf_counter()
        try:
            moves = agent.compute_moves(state)
        except Exception as e:                     # a real crash would drop the connection
            st.crashes += 1
            st.last_problem = f"crash: {e!r}"
        dt = time.perf_counter() - t0
        st.decision_times.append(dt)

        if moves is not None and dt > time_limit:
            st.timeouts += 1
            st.last_problem = f"timeout: {dt:.2f}s"
            moves = None
        if moves is not None:
            try:
                ok, msg = board.validate_moves(moves, current)
            except Exception as e:
                ok, msg = False, f"malformed moves: {e!r}"
            if not ok:
                st.illegal += 1
                st.last_problem = msg
                moves = None

        if moves:
            board = board.apply_moves(moves, current, deterministic=deterministic_battles)
        else:                                      # skipped turn still uses up a ply
            board = board.clone()
            board.turn_count += 1

        if verbose:
            from map_loader import render_board
            print(f"\nply {board.turn_count}: {current.value} moves {moves}")
            print(render_board(board))
        current = other(current)

    _, winner = board.is_game_over()
    return GameResult(winner, board.turn_count,
                      board.get_species_total(Species.VAMPIRE),
                      board.get_species_total(Species.WEREWOLF),
                      sum(c for _, c in board.get_humans()), stats)


@dataclass
class MapSummary:
    map_name: str
    games: int = 0
    a_wins: int = 0
    b_wins: int = 0
    draws: int = 0
    plies: List[int] = field(default_factory=list)
    times: Dict[str, List[float]] = field(default_factory=lambda: {"A": [], "B": []})
    problems: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: {"A": {"illegal": 0, "timeouts": 0, "crashes": 0},
                                 "B": {"illegal": 0, "timeouts": 0, "crashes": 0}})
    last_problem: Dict[str, str] = field(default_factory=lambda: {"A": "", "B": ""})


def run_match(make_a: Callable[[], object], make_b: Callable[[], object], map_paths: List[str],
              games_per_side: int = 10, seed: int = 0, first: Species = Species.VAMPIRE,
              time_limit: float = TIME_LIMIT, deterministic_battles: bool = False) -> List[MapSummary]:
    """A and B each play both species on every map. Fresh agents are created for every game."""
    summaries = []
    game_no = 0
    for path in map_paths:
        board = load_map(path)
        s = MapSummary(path)
        for a_species in (Species.VAMPIRE, Species.WEREWOLF):
            for _ in range(games_per_side):
                agents = {a_species: make_a(), other(a_species): make_b()}
                r = play_game(board, agents, first=first, time_limit=time_limit,
                              seed=seed + game_no, deterministic_battles=deterministic_battles)
                game_no += 1
                s.games += 1
                s.plies.append(r.plies)
                if r.winner is None:
                    s.draws += 1
                elif r.winner == a_species:
                    s.a_wins += 1
                else:
                    s.b_wins += 1
                for label, sp in (("A", a_species), ("B", other(a_species))):
                    st = r.stats[sp]
                    s.times[label] += st.decision_times
                    s.problems[label]["illegal"] += st.illegal
                    s.problems[label]["timeouts"] += st.timeouts
                    s.problems[label]["crashes"] += st.crashes
                    if st.last_problem:
                        s.last_problem[label] = st.last_problem
        summaries.append(s)
    return summaries


def print_summary(summaries: List[MapSummary], name_a: str = "A", name_b: str = "B") -> None:
    names = {"A": name_a, "B": name_b}
    for s in summaries:
        print(f"\n=== {s.map_name}: {s.games} games (each bot plays both species) ===")
        print(f"  {name_a} wins {s.a_wins} | {name_b} wins {s.b_wins} | draws {s.draws} "
              f"| average length {sum(s.plies) / len(s.plies):.0f} plies")
        for label in ("A", "B"):
            t = s.times[label]
            p = s.problems[label]
            print(f"  {names[label]}: decision time avg {1000 * sum(t) / len(t):.2f} ms, "
                  f"max {1000 * max(t):.2f} ms | illegal {p['illegal']}, "
                  f"timeouts {p['timeouts']}, crashes {p['crashes']}")
            if s.last_problem[label]:
                print(f"     last problem: {s.last_problem[label]}")


if __name__ == "__main__":
    from agents_baseline import RandomAgent
    from ai_agent import AIAgent          # the repo's starter agent (a reflex agent)

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    maps = ["thetrap.xml", "testmap.xml"]
    result = run_match(lambda: AIAgent("Starter"), lambda: RandomAgent(), maps, games_per_side=n)
    print_summary(result, "Starter", "Random")
