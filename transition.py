"""
transition.py  (our own file; it does not modify any shared repo file)

"If `species` plays this turn on this board, which boards can result, and how likely is each?"
This is the CHANCE NODE of expectiminimax. game_engine.apply_moves returns ONE board
(either pessimistic or a random dice roll); here we return the list of possible boards
with their probabilities, using battle_model.py.

How a turn is resolved (same order as game_engine.apply_moves):
  1. creatures leave their source cells;
  2. creatures arriving on the same cell are merged into ONE attacking group;
  3. each destination is resolved:
       - empty or friendly cell: the groups simply merge (certain);
       - humans / enemy monsters: battle_model.certain_outcome if the result is not random,
         otherwise a RANDOM battle.
  4. the random battles multiply: k random battles would give 2^k boards, so only the
     `max_chance_battles` biggest random battles (by attackers + defenders) keep their two
     outcomes (win / lose); the others are replaced by their rounded average outcome.
     This keeps the tree small. It is an approximation (averaging blurs thresholds),
     but a turn rarely contains more than two real gambles.

Assumption (not verified on the real server): attackers all die when they lose a battle.
Survivor counts are rounded to whole creatures (battle_model level "two").
"""
from typing import Dict, List, Tuple

from battle_model import Outcome, battle_outcomes, certain_outcome
from game_engine import BoardState
from game_state import Species

Pos = Tuple[int, int]
Cell = Tuple[int, int, int]          # (humans, vampires, werewolves)
Move = Tuple[int, int, int, int, int]


def _round_half_up(x: float) -> int:
    return int(x + 0.5)


def _cell_from(outcome: Outcome, species: Species) -> Cell:
    """Cell contents after a battle won/lost by `species` attacking (as ints)."""
    humans = _round_half_up(outcome.humans)
    friendly = _round_half_up(outcome.friendly)
    enemy = _round_half_up(outcome.enemy)
    return (humans, friendly, enemy) if species == Species.VAMPIRE else (humans, enemy, friendly)


def _resolve(board: BoardState, turn: List[Move], species: Species):
    """
    Common part: returns (base, sure_cells, random_battles) where
      base            = board copy with the moving creatures removed and turn_count + 1,
      sure_cells      = {pos: cell} for destinations whose result is certain,
      random_battles  = [(stakes, pos, attackers, defenders, defenders_are_humans)].
    """
    is_vampire = species == Species.VAMPIRE
    base = board.clone()
    base.turn_count += 1

    arriving: Dict[Pos, int] = {}
    for x1, y1, count, x2, y2 in turn:
        h, v, w = base.get_cell((x1, y1))
        if is_vampire:
            base.set_cell((x1, y1), h, v - count, w)
        else:
            base.set_cell((x1, y1), h, v, w - count)
        arriving[(x2, y2)] = arriving.get((x2, y2), 0) + count

    sure_cells: Dict[Pos, Cell] = {}
    random_battles = []
    for dst, attackers in arriving.items():
        h, v, w = base.get_cell(dst)
        friendly, enemy = (v, w) if is_vampire else (w, v)
        if enemy > 0:
            defenders, humans_target = enemy, False
        elif h > 0:
            defenders, humans_target = h, True
        else:                                            # empty or friendly: merge
            total = friendly + attackers
            sure_cells[dst] = (0, total, 0) if is_vampire else (0, 0, total)
            continue
        sure = certain_outcome(attackers, defenders, humans_target)
        if sure is not None:
            sure_cells[dst] = _cell_from(sure, species)
        else:
            random_battles.append((attackers + defenders, dst, attackers, defenders, humans_target))
    random_battles.sort(key=lambda b: (-b[0], b[1]))     # biggest stakes first (deterministic order)
    return base, sure_cells, random_battles


def count_random_battles(board: BoardState, turn: List[Move], species: Species) -> int:
    """How many destinations of this turn are real gambles."""
    return len(_resolve(board, turn, species)[2])


def turn_outcomes(board: BoardState, turn: List[Move], species: Species,
                  max_chance_battles: int = 2) -> List[Tuple[float, BoardState]]:
    """
    All boards that can result from `species` playing `turn` on `board`, as a list of
    (probability, new_board). Probabilities sum to 1. `board` is not modified.
    """
    base, sure_cells, battles = _resolve(board, turn, species)

    results: List[Tuple[float, Dict[Pos, Cell]]] = [(1.0, dict(sure_cells))]
    for index, (_, dst, attackers, defenders, humans_target) in enumerate(battles):
        level = "two" if index < max_chance_battles else "mean"
        outcomes = battle_outcomes(attackers, defenders, humans_target, level)
        expanded = []
        for prob, cells in results:
            for o in outcomes:
                new_cells = dict(cells)
                new_cells[dst] = _cell_from(o, species)
                expanded.append((prob * o.prob, new_cells))
        results = expanded

    boards = []
    for prob, cells in results:
        b = base.clone()
        for pos, cell in cells.items():
            b.set_cell(pos, *cell)
        boards.append((prob, b))
    return boards
