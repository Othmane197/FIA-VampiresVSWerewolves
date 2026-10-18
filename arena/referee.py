"""
Local referee: plays one game between two bots with the REAL server's rules
(docs/SERVER_FINDINGS.md):
  * player 0 moves first; battles are resolved by splitter.state.State.apply (server dice);
  * an illegal move list (rules.check_moves = the server's "cheating" checks) ends the game:
    the offender loses;
  * a crash ends the game too (on the server the connection would drop = cheating);
  * a reply slower than `hard_limit` is a timeout: the turn is skipped (server behaviour);
  * the game ends when a species is wiped out or after max_ply plies; the bigger side wins.
"""
import random
import time
import traceback
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from splitter.rules import V, W, check_moves, other
from splitter.state import State


@dataclass
class SideStats:
    times: List[float] = field(default_factory=list)
    timeouts: int = 0
    illegal: int = 0
    crashes: int = 0
    problem: str = ""
    splits: int = 0            # turns where one cell sent moves to 2+ destinations
    max_groups: int = 1


@dataclass
class GameResult:
    winner: Optional[int]      # V / W / None (draw)
    plies: int
    totals: tuple              # (vampires, werewolves) at the end
    humans_left: int
    reason: str                # "wipeout" | "plies" | "illegal" | "crash"
    stats: Dict[int, SideStats]
    log: List[str] = field(default_factory=list)


def play_game(initial: State, bots: Dict[int, object], first: int = V, seed: Optional[int] = None,
              hard_limit: float = 2.0, verbose: bool = False, render=None) -> GameResult:
    rng = random.Random(seed)
    if seed is not None:
        random.seed(seed)                   # some bots use the global random module
    state = initial.copy()
    state.ply = 0
    stats = {V: SideStats(), W: SideStats()}
    for b in bots.values():
        b.reset()
    to_move = first
    log: List[str] = []
    reason = "plies"
    winner: Optional[int] = None
    while True:
        if not state.groups[V] or not state.groups[W]:
            reason = "wipeout"
            winner = state.winner()
            break
        if state.ply >= state.max_ply:
            reason = "plies"
            winner = state.winner()
            break
        st = stats[to_move]
        t0 = time.perf_counter()
        try:
            moves = bots[to_move].play(state.copy(), to_move)
        except Exception as e:
            st.crashes += 1
            st.problem = f"crash: {e!r}\n{traceback.format_exc()}"
            reason, winner = "crash", other(to_move)
            break
        dt = time.perf_counter() - t0
        st.times.append(dt)
        if dt > hard_limit:
            st.timeouts += 1
            st.problem = f"timeout {dt:.2f}s at ply {state.ply}"
            state = state.copy()
            state.ply += 1
            to_move = other(to_move)
            continue
        try:
            moves = [tuple(int(v) for v in m) for m in (moves or [])]
            ok, why = check_moves(state.rows, state.cols, state.groups[to_move], moves)
        except Exception as e:
            ok, why = False, f"malformed moves {moves!r}: {e!r}"
        if not ok:
            st.illegal += 1
            st.problem = f"illegal at ply {state.ply}: {why}"
            reason, winner = "illegal", other(to_move)
            break
        srcs = {}
        for m in moves:
            srcs.setdefault((m[0], m[1]), set()).add((m[3], m[4]))
        if any(len(d) > 1 for d in srcs.values()):
            st.splits += 1
        state = state.apply(to_move, moves, rng)
        st.max_groups = max(st.max_groups, len(state.groups[to_move]))
        line = (f"ply {state.ply:3d} {'VW'[to_move]} {getattr(bots[to_move], 'name', '?')}: {moves}"
                f"   -> V{dict(state.groups[V])} W{dict(state.groups[W])} H{state.humans_total()}")
        log.append(line)
        if verbose:
            print(line)
            if render:
                print(render(state))
        to_move = other(to_move)
    return GameResult(winner, state.ply, (state.total(V), state.total(W)), state.humans_total(),
                      reason, stats, log)
