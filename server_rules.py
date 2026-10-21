"""
server_rules.py  (our own file; it does not modify any shared repo file)

A Python port of the rules of the OFFICIAL game server, read from the course's compiled
VVSW.Model.dll (Board.CheckMoves, Board.PerformMoves, Board.GetProba, Board.PerformRandomBattle,
GameControl.GameRoutine). It is NOT taken from Projectv10.pdf or from the repo's game_engine.py,
because those differ from the real server in a few places (marked DIFF below).

Why we need it
  1. A last safety gate: before we send a turn we check it with `check_moves`. On the real server an
     illegal or EMPTY turn ends the game and the opponent wins ("the player cheated").
  2. A faithful simulator for self-play (`perform_moves`).
  3. The rules for a fake local server (end-to-end tests of main.py / network.py).

What the real server does (verified by reading the DLL)
  * Validation, per move: the source holds our species, count >= 1, count <= creatures on the source,
    target is at most 1 step away in x and in y. A cell that is both a source and a target of this
    turn makes the moves touching it illegal (Rule 5). The moves leaving one source cell may not add
    up to more than it holds. An empty list of moves is illegal ("stayed static").
  * Execution: moves are grouped by TARGET cell and their counts are ADDED (attackers coming from
    several cells fight as one group). The moved creatures leave their source cells, then per target:
      - empty cell                       -> the group stands there
      - our own group                    -> the groups merge
      - humans, attackers >= humans      -> certain: all humans convert, all attackers live
      - monsters, attackers >= 1.5*enemy -> certain: enemy dies, all attackers live
      - anything else                    -> random battle (below)
  * Random battle, P = get_proba(attackers, defenders):
      attackers win with probability P:
          every attacker survives with probability P, and (vs humans) every human also converts
          with probability P. There is NO minimum of one survivor.
      attackers lose: ALL attackers die, every defender survives with probability 1 - P.
  * DIFF 1: there is NO "certain loss" rule. Spec and game_engine.py say that defenders >= 1.5x
    the attackers wipe them out for sure; the real server runs a random battle with
    P = E1 / (2*E2) (e.g. 3 against 5 monsters: P = 0.3).
  * DIFF 2: game_engine.py forces at least 1 survivor in Monte-Carlo mode; the server does not.
  * End: a species with no creatures left loses at once; after MaxPlays (200) plies the larger
    total wins, equal totals = no winner. Vampires move first.

Known limits: counts are bytes on the real server (they would wrap above 255); we do not model that.
"""
import random
from typing import Dict, List, Optional, Tuple

from game_engine import BoardState
from game_state import Species

Move = Tuple[int, int, int, int, int]            # (src_x, src_y, count, dst_x, dst_y)
Pos = Tuple[int, int]

HUMANS_TIMES_GREATER = 1.0                       # attackers >= 1.0 * humans  -> certain conversion
MONSTERS_TIMES_GREATER = 1.5                     # attackers >= 1.5 * enemy   -> certain kill


# ---------------------------------------------------------------- probabilities

def win_probability(attackers: int, defenders: int, defenders_are_humans: bool) -> float:
    """Port of Board.GetProba. 1.0 means a certain win, never 0.0 (there is no certain loss)."""
    if attackers == defenders:
        return 0.5
    factor = HUMANS_TIMES_GREATER if defenders_are_humans else MONSTERS_TIMES_GREATER
    if attackers >= factor * defenders:
        return 1.0
    if attackers < defenders:
        return attackers / (2.0 * defenders)
    # defenders < attackers < factor * defenders: the line through (defenders, 0.5) and (factor*defenders, 1)
    slope = (1.0 - 0.5) / (factor * defenders - defenders)
    intercept = 1.0 - slope * factor * defenders
    return slope * attackers + intercept


def is_certain_win(attackers: int, defenders: int, defenders_are_humans: bool) -> bool:
    """The two thresholds PerformMoves tests before it starts a random battle."""
    factor = HUMANS_TIMES_GREATER if defenders_are_humans else MONSTERS_TIMES_GREATER
    return factor * defenders <= attackers


def random_battle(attackers: int, defenders: int, defenders_are_humans: bool,
                  rng=random) -> Tuple[bool, int]:
    """Port of Board.PerformRandomBattle. Returns (attackers_won, survivors).
    The survivors belong to the attackers' species when they won, else to the defenders'.
    `rng` needs a .random() method (the default is Python's random module)."""
    p = win_probability(attackers, defenders, defenders_are_humans)
    if rng.random() < p:
        survivors = 0
        if defenders_are_humans:                         # converted humans first, then attackers
            survivors += sum(1 for _ in range(defenders) if rng.random() < p)
        survivors += sum(1 for _ in range(attackers) if rng.random() < p)
        return True, survivors
    return False, sum(1 for _ in range(defenders) if rng.random() < 1.0 - p)


# ---------------------------------------------------------------- validation

def _own_count(board: BoardState, species: Species, pos: Pos) -> int:
    h, v, w = board.get_cell(pos)
    return v if species == Species.VAMPIRE else w


def check_moves(board: BoardState, species: Species, moves: List[Move]) -> Optional[str]:
    """None if the real server would accept this turn, else the reason it would not.
    (Port of Board.CheckMoves; anything returned here means: the game is lost on the real server.)"""
    if not moves:
        return "empty turn (the server says the player 'stayed static' and ends the game)"
    sources = {(m[0], m[1]) for m in moves}
    targets = {(m[3], m[4]) for m in moves}
    both = sources & targets
    for x1, y1, count, x2, y2 in moves:
        src, dst = (x1, y1), (x2, y2)
        if dst in both or src in both:
            return f"Rule 5: {sorted(both)} is both source and target"
        if not (0 <= x1 < board.cols and 0 <= y1 < board.rows):
            return f"source {src} is outside the grid"
        if not (0 <= x2 < board.cols and 0 <= y2 < board.rows):
            return f"target {dst} is outside the grid"
        have = _own_count(board, species, src)
        if have <= 0:
            return f"no creature of ours on {src}"
        if have < count:
            return f"{count} creatures from {src}, which holds {have}"
        if abs(x1 - x2) > 1 or abs(y1 - y2) > 1:
            return f"{src} -> {dst} is not an adjacent cell"
        if count == 0:
            return "a move of 0 creatures"
        if count < 0 or count > 255:
            return f"count {count} cannot be sent (one byte)"
    totals: Dict[Pos, int] = {}
    for x1, y1, count, _, _ in moves:
        totals[(x1, y1)] = totals.get((x1, y1), 0) + count
    for src, total in totals.items():
        have = _own_count(board, species, src)
        if total > have:
            return f"{total} creatures leave {src} in total, but it holds {have}"
    return None


# ---------------------------------------------------------------- execution

def _put(board: BoardState, pos: Pos, species: Species, count: int) -> None:
    if species == Species.VAMPIRE:
        board.set_cell(pos, 0, count, 0)
    else:
        board.set_cell(pos, 0, 0, count)


def perform_moves(board: BoardState, species: Species, moves: List[Move], rng=random) -> BoardState:
    """Port of Board.PerformMoves: returns the new board (the input is not modified).
    The moves must already pass `check_moves` (this function does not re-check them)."""
    new = board.clone()
    new.turn_count += 1
    is_vamp = species == Species.VAMPIRE

    arrivals: Dict[Pos, int] = {}                        # grouped by target, in order of first appearance
    for x1, y1, count, x2, y2 in moves:
        h, v, w = new.get_cell((x1, y1))
        new.set_cell((x1, y1), h, v - count, w) if is_vamp else new.set_cell((x1, y1), h, v, w - count)
        arrivals[(x2, y2)] = arrivals.get((x2, y2), 0) + count

    for dst, total in arrivals.items():
        h, v, w = new.get_cell(dst)
        own, enemy = (v, w) if is_vamp else (w, v)
        if h == 0 and own == 0 and enemy == 0:
            _put(new, dst, species, total)                            # empty cell
        elif own > 0:
            _put(new, dst, species, own + total)                      # merge with our group
        elif h > 0:
            if is_certain_win(total, h, True):
                _put(new, dst, species, h + total)                    # convert everyone
            else:
                won, survivors = random_battle(total, h, True, rng)
                if won:
                    _put(new, dst, species, survivors)
                else:
                    new.set_cell(dst, survivors, 0, 0)                # the humans that survived
        else:
            if is_certain_win(total, enemy, False):
                _put(new, dst, species, total)                        # the enemy is wiped out
            else:
                won, survivors = random_battle(total, enemy, False, rng)
                if won:
                    _put(new, dst, species, survivors)
                else:                                                 # all attackers died
                    if is_vamp:
                        new.set_cell(dst, 0, 0, survivors)
                    else:
                        new.set_cell(dst, 0, survivors, 0)
    return new
