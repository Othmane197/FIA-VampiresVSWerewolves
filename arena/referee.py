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
from typing import Any, Dict, List, Mapping, Optional

from splitter.rules import V, W, check_moves, other
from splitter.state import State


@dataclass
class SideStats:
    """Per-side statistics of one game: decision times, problems, split turns, max groups."""
    times: List[float] = field(default_factory=list)
    timeouts: int = 0
    illegal: int = 0
    crashes: int = 0
    problem: str = ""
    splits: int = 0            # turns where one cell sent moves to 2+ destinations
    max_groups: int = 1


@dataclass
class GameResult:
    """Outcome of one game: winner, length, final totals, end reason, stats and move log."""
    winner: Optional[int]      # V / W / None (draw)
    plies: int
    totals: tuple              # (vampires, werewolves) at the end
    humans_left: int
    reason: str                # "wipeout" | "plies" | "illegal" | "crash"
    stats: Dict[int, SideStats]
    log: List[str] = field(default_factory=list)
    trace: List[dict] = field(default_factory=list)   # filled when play_game(record=True)


def state_to_dict(s: State) -> dict:
    """JSON-friendly board: lists of [x, y, n] for humans, vampires and werewolves."""
    return {"h": [[p[0], p[1], n] for p, n in s.humans.items()],
            "v": [[p[0], p[1], n] for p, n in s.groups[V].items()],
            "w": [[p[0], p[1], n] for p, n in s.groups[W].items()], "ply": s.ply}


def state_from_dict(d: dict, rows: int, cols: int, max_ply: int = 200) -> State:
    """Inverse of state_to_dict."""
    return State(rows, cols, {(x, y): n for x, y, n in d["h"]}, {(x, y): n for x, y, n in d["v"]},
                 {(x, y): n for x, y, n in d["w"]}, d.get("ply", 0), max_ply)


def play_game(initial: State, bots: Mapping[int, Any], first: int = V, seed: Optional[int] = None,
              hard_limit: float = 2.0, verbose: bool = False, render=None,
              record: bool = False) -> GameResult:
    """Play one full game between two bots with the real server's rules (see module docstring)."""
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
    trace: List[dict] = []
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
            moves = [(int(a), int(b), int(c), int(d), int(e)) for a, b, c, d, e in (moves or [])]
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
        before = state
        state = state.apply(to_move, moves, rng)
        if record:                          # ground truth for the opponent model (opponent_model.py)
            trace.append({"side": to_move, "moves": moves, "before": state_to_dict(before),
                          "after": state_to_dict(state)})
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
                      reason, stats, log, trace)
