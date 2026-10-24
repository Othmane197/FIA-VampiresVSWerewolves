"""
Exact game rules, as implemented by the REAL server (see docs/SERVER_FINDINGS.md, which was
obtained by probing VampiresVSWerewolvesGameServer.exe and disassembling VVSW.Model.dll).

Sides are integers: V = 0 (vampires), W = 1 (werewolves).
A move is (src_x, src_y, count, dst_x, dst_y). Positions are (x, y) tuples, (0, 0) = top-left.

Differences with the PDF that matter:
  * monsters: a defender >= 1.5x the attackers does NOT kill them for sure; it is a random
    battle with P = E1 / (2 * E2) (game_engine.py in the starter kit gets this wrong);
  * moves into the same destination are summed before the battle;
  * the cell counts are bytes (> 255 wraps around), so we never build a cell above 255.
"""
import random as _random
from typing import Dict, Optional, Sequence, Tuple

V, W = 0, 1
Pos = Tuple[int, int]
Move = Tuple[int, int, int, int, int]
MAX_CELL = 255


def other(side: int) -> int:
    """The opposite side: V <-> W."""
    return 1 - side


def cheb(a: Pos, b: Pos) -> int:
    """King-move (Chebyshev) distance: number of moves between two cells."""
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    if dx < 0:
        dx = -dx
    if dy < 0:
        dy = -dy
    return max(dy, dx)


def win_probability(e1: int, e2: int, humans: bool) -> float:
    """Board.GetProba: probability that E1 attackers beat E2 defenders."""
    if e1 == e2:
        return 0.5
    threshold = 1.0 if humans else 1.5
    if e1 >= threshold * e2:
        return 1.0
    if e1 < e2:
        return e1 / (2.0 * e2)
    return e1 / e2 - 0.5          # E2 < E1 < 1.5 * E2 (monsters only)


def is_sure_win(e1: int, e2: int, humans: bool) -> bool:
    """No dice: humans need E1 >= E2, monsters need E1 >= 1.5 * E2."""
    return e1 >= e2 if humans else e1 >= 1.5 * e2


def binomial(n: int, p: float, rng) -> int:
    """Number of successes among n independent trials of probability p (server dice)."""
    if p >= 1.0:
        return n
    if p <= 0.0:
        return 0
    r = rng.random
    return sum(1 for _ in range(n) if r() < p)


def resolve_battle(e1: int, e2: int, humans: bool, mode: str = "sample",
                   rng=None) -> Tuple[bool, int]:
    """
    Board.PerformMoves + PerformRandomBattle for one destination cell.
    Returns (attackers_win, survivors): survivors are of the attacker's species when they win,
    of the defender's species (humans or enemy monsters) when they lose.
    mode: "sample" = server dice, "mean" = the more likely branch with rounded expected survivors.
    """
    if is_sure_win(e1, e2, humans):
        return True, (e1 + e2 if humans else e1)
    p = win_probability(e1, e2, humans)
    if mode == "mean":
        if p >= 0.5:
            n = int(p * (e1 + (e2 if humans else 0)) + 0.5)
            return (True, n) if n > 0 else (False, 0)
        return False, int((1.0 - p) * e2 + 0.5)
    rng = rng or _random
    if rng.random() < p:
        survivors = binomial(e1, p, rng)
        if humans:
            survivors += binomial(e2, p, rng)
        return True, survivors
    return False, binomial(e2, 1.0 - p, rng)


def check_moves(rows: int, cols: int, mine: Dict[Pos, int], moves: Sequence[Move],
                arrivals_cap: Optional[Dict[Pos, int]] = None) -> Tuple[bool, str]:
    """
    Board.CheckMoves (what the server calls cheating) + the checks the server forgets
    (target inside the board, cell count <= 255, counts are bytes).
    `mine` = our creatures per cell. `arrivals_cap` (optional) = current count of OUR creatures
    at each destination, to refuse merges above 255.
    """
    if not moves:
        return False, "empty MOV (server: 'restés statiques')"
    sources = set()
    targets = set()
    out: Dict[Pos, int] = {}
    arriving: Dict[Pos, int] = {}
    for mv in moves:
        if len(mv) != 5:
            return False, f"malformed move {mv!r}"
        x1, y1, n, x2, y2 = mv
        if not all(isinstance(v, int) for v in mv):
            return False, f"non-integer move {mv!r}"
        if n <= 0 or n > MAX_CELL:
            return False, f"bad count in {mv!r}"
        if not (0 <= x1 < cols and 0 <= y1 < rows and 0 <= x2 < cols and 0 <= y2 < rows):
            return False, f"out of the board {mv!r}"
        if abs(x1 - x2) > 1 or abs(y1 - y2) > 1 or (x1 == x2 and y1 == y2):
            return False, f"not a one-step move {mv!r}"
        src = (x1, y1)
        dst = (x2, y2)
        sources.add(src)
        targets.add(dst)
        out[src] = out.get(src, 0) + n
        arriving[dst] = arriving.get(dst, 0) + n
    both = sources & targets
    if both:
        return False, f"rule 5: {sorted(both)} both source and target"
    for src, n in out.items():
        have = mine.get(src, 0)
        if have <= 0:
            return False, f"no creatures of ours at {src}"
        if n > have:
            return False, f"moving {n} from {src} but only {have} there"
    for dst, n in arriving.items():
        already = mine.get(dst, 0) if arrivals_cap is None else arrivals_cap.get(dst, 0)
        if n + already > MAX_CELL:
            return False, f"cell {dst} would hold {n + already} > 255 (byte overflow)"
    return True, "ok"
