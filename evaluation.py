"""
evaluation.py  (our own file; it does not modify any shared repo file)

Scores a board with ONE number, from the point of view of `species`:
    higher = better for `species`,  lower = better for the opponent.
Search algorithms (minimax, expectiminimax) call it where they stop looking ahead.

Version 1 = two terms (our own design, not from the course):

  1. MATERIAL  = (our creatures) - (enemy creatures).   This is the real win condition.

  2. RACE TO THE HUMANS.  For every human group of size H we ask who can reach it first.
     Only a group with at least H creatures counts, because only then is conversion certain.
     Distance = king-move distance  max(|dx|, |dy|).
        our nearest strong-enough group is closer  ->  +H
        the enemy's is closer                      ->  -H
        same distance (or nobody can)              ->   0
     The sum is multiplied by `race_weight` (default 0.5): the race can still change, so we
     do not count it fully. 0.5 is a first guess, to be tuned with the self-play scoreboard.

  GAME OVER (same rules as game_engine.BoardState.is_game_over):
     the winner gets +WIN_SCORE, the loser -WIN_SCORE, a draw 0.

Known limits of version 1 (to check with matches, not assumed):
  * ties in the race are scored 0, although the player to move would arrive first;
  * it does not see threats (a group that the enemy can kill next turn);
  * it does not know that converting a group can give a decisive 1.5x advantage
    (e.g. the 4 humans on thetrap.xml: 8 creatures next to 4 enemies kill them for sure).

The function is zero-sum by construction:  evaluate(b, V) == -evaluate(b, W).
"""
from typing import List, Optional, Tuple

from game_engine import BoardState
from game_state import Species

WIN_SCORE = 10_000.0
DEFAULT_RACE_WEIGHT = 0.5

Pos = Tuple[int, int]


def _cheb(a: Pos, b: Pos) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _nearest_strong_enough(groups: List[Tuple[Pos, int]], target: Pos, needed: int) -> Optional[int]:
    """Distance from `target` to the nearest group of at least `needed` creatures (None if none)."""
    best = None
    for pos, count in groups:
        if count >= needed:
            d = _cheb(pos, target)
            if best is None or d < best:
                best = d
    return best


def race_term(board: BoardState, species: Species) -> float:
    """Sum over human groups of +H / -H / 0 (see module docstring), before weighting."""
    enemy = Species.WEREWOLF if species == Species.VAMPIRE else Species.VAMPIRE
    ours = board.get_species_groups(species)
    theirs = board.get_species_groups(enemy)
    total = 0
    for pos, humans in board.get_humans():
        mine = _nearest_strong_enough(ours, pos, humans)
        other = _nearest_strong_enough(theirs, pos, humans)
        if mine is None and other is None:
            continue
        if other is None or (mine is not None and mine < other):
            total += humans
        elif mine is None or other < mine:
            total -= humans
    return total


def _closeness(board: BoardState, species: Species) -> float:
    """How close `species` is to a human group it can convert: cap - (distance of the closest
    group that has >= H creatures to a human group of size H); 0 if no such pair exists."""
    cap = max(board.rows, board.cols)
    best = None
    groups = board.get_species_groups(species)
    for hpos, h in board.get_humans():
        d = _nearest_strong_enough(groups, hpos, h)
        if d is not None and (best is None or d < best):
            best = d
    return 0.0 if best is None else float(max(0, cap - best))


def progress_term(board: BoardState, species: Species) -> float:
    """Our closeness minus the enemy's closeness (antisymmetric, so evaluate stays zero-sum).
    Gives a small push toward actually walking to convertible humans (see module docstring)."""
    enemy = Species.WEREWOLF if species == Species.VAMPIRE else Species.VAMPIRE
    return _closeness(board, species) - _closeness(board, enemy)


def evaluate(board: BoardState, species: Species, race_weight: float = DEFAULT_RACE_WEIGHT,
             progress_weight: float = 0.0) -> float:
    """Score of `board` for `species` (see module docstring)."""
    enemy = Species.WEREWOLF if species == Species.VAMPIRE else Species.VAMPIRE
    ours = board.get_species_total(species)
    theirs = board.get_species_total(enemy)

    # Game over: same conditions as BoardState.is_game_over
    if ours == 0 and theirs == 0:
        return 0.0
    if theirs == 0:
        return WIN_SCORE
    if ours == 0:
        return -WIN_SCORE
    if board.turn_count >= board.max_turns:
        return WIN_SCORE if ours > theirs else (-WIN_SCORE if ours < theirs else 0.0)

    value = (ours - theirs) + race_weight * race_term(board, species)
    if progress_weight:
        value += progress_weight * progress_term(board, species)
    return value
