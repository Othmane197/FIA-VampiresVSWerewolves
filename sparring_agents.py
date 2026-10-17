"""
sparring_agents.py  (our own file; it does not modify any shared repo file)

A PANEL of opponents with deliberately different styles, used to test and tune our bot.
Every agent has the same interface as the repo's AIAgent:
    compute_moves(state: GameState) -> list of (src_x, src_y, count, dst_x, dst_y)

  Random   random legal moves (agents_baseline.py)                       - sanity floor
  Starter  the repo's AIAgent: walks toward the nearest target           - reflex baseline
  Grabber  converts every human group it is strong enough for, kills an
           adjacent enemy only when certain (>= 1.5x), never gambles     - cautious expander
  Rusher   ignores humans, charges the nearest enemy and attacks whenever
           its odds are at least 50%                                     - tests our defence
  Turtle   grabs only humans close to its start, attacks only certain
           kills, otherwise shuffles around its start cell               - tests whether we can make progress
  OnePly   our own SearchAgent with depth 1 (no look-ahead)              - tests the value of looking ahead

These are test opponents, not strategies we intend to submit. Because they play simple fixed rules,
a loss against one of them points at a specific weakness of our bot.
"""
from typing import Callable, Dict, List, Optional, Set, Tuple

from agents_baseline import RandomAgent
from ai_agent import AIAgent
from game_engine import BoardState
from game_state import GameState, Species
from search_agent import SearchAgent
from state_converter import board_from_state

Pos = Tuple[int, int]
Turn = List[Tuple[int, int, int, int, int]]


def _cheb(a: Pos, b: Pos) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _other(species: Species) -> Species:
    return Species.WEREWOLF if species == Species.VAMPIRE else Species.VAMPIRE


def _cell(board: BoardState, species: Species, pos: Pos) -> Tuple[int, int, int]:
    """(humans, friendly, enemy) on a cell, from the point of view of `species`."""
    h, v, w = board.get_cell(pos)
    return (h, v, w) if species == Species.VAMPIRE else (h, w, v)


def _danger(board: BoardState, species: Species, pos: Pos, my_count: int) -> int:
    """How many enemy groups could kill a group of `my_count` standing on `pos` next turn."""
    return sum(1 for p, c in board.get_species_groups(_other(species))
               if _cheb(p, pos) == 1 and c >= 1.5 * my_count)


def _nearest(items: List[Tuple[Pos, int]], pos: Pos) -> Tuple[Pos, int]:
    return min(items, key=lambda g: (_cheb(g[0], pos), g[0]))


def _step_toward(board: BoardState, species: Species, pos: Pos, count: int, target: Pos,
                 forbidden: Set[Pos]) -> Optional[Pos]:
    """Neighbour that gets closest to `target`; never wades into humans / enemies, avoids danger."""
    best = None
    for n in board.get_neighbors(pos):
        if n in forbidden:
            continue
        humans, _, enemy = _cell(board, species, n)
        if humans > 0 or enemy > 0:
            continue
        key = (_cheb(n, target), _danger(board, species, n, count), n)
        if best is None or key < best[0]:
            best = (key, n)
    return None if best is None else best[1]


def _fallback_turn(board: BoardState, species: Species, groups: List[Tuple[Pos, int]]) -> Turn:
    """One plain legal move: the biggest group steps to the least dangerous neighbour."""
    pos, count = max(groups, key=lambda g: (g[1], g[0]))
    best = None
    for n in board.get_neighbors(pos):
        humans, _, enemy = _cell(board, species, n)
        key = (humans > 0 or enemy > 0, _danger(board, species, n, count), n)
        if best is None or key < best[0]:
            best = (key, n)
    return [(pos[0], pos[1], count, best[1][0], best[1][1])]


class _PanelAgent:
    """Common wrapper: GameState -> BoardState, then `plan`, with a legal fallback."""

    def __init__(self, name: Optional[str] = None):
        self.name = name or type(self).__name__

    def compute_moves(self, state: GameState) -> Turn:
        board = board_from_state(state)
        species = state.our_species
        groups = board.get_species_groups(species)
        if not groups:
            return []
        self._home = state.home or groups[0][0]
        turn = self.plan(board, species, groups)
        return turn if turn else _fallback_turn(board, species, groups)

    def plan(self, board: BoardState, species: Species, groups: List[Tuple[Pos, int]]) -> Turn:
        raise NotImplementedError


class Grabber(_PanelAgent):
    """Converts every human group it is strong enough for; kills only when certain; never gambles."""

    def plan(self, board, species, groups):
        enemies = board.get_species_groups(_other(species))
        humans = board.get_humans()
        forbidden = {p for p, _ in groups}
        taken: Set[Pos] = set()
        turn: Turn = []
        for pos, count in sorted(groups, key=lambda g: (-g[1], g[0])):
            dest = None
            for ep, e in enemies:                                        # certain kill next to us
                if _cheb(ep, pos) == 1 and count >= 1.5 * e and ep not in taken:
                    dest = ep
                    break
            if dest is None:
                for hp, h in humans:                                     # convertible humans next to us
                    if _cheb(hp, pos) == 1 and count >= h and hp not in taken:
                        dest = hp
                        break
            if dest is None:
                reachable = [(hp, h) for hp, h in humans if h <= count and hp not in taken]
                if reachable:                                            # walk to the nearest one
                    target = _nearest(reachable, pos)[0]
                    dest = _step_toward(board, species, pos, count, target, forbidden | taken)
            if dest is None:
                weak = [(ep, e) for ep, e in enemies if count >= 1.5 * e]
                if weak:                                                 # hunt an enemy we surely beat
                    target = _nearest(weak, pos)[0]
                    dest = _step_toward(board, species, pos, count, target, forbidden | taken)
            if dest is not None:
                turn.append((pos[0], pos[1], count, dest[0], dest[1]))
                taken.add(dest)
        return turn


class Rusher(_PanelAgent):
    """Ignores humans. Charges the nearest enemy; attacks whenever it is at least as big (odds >= 50%)."""

    def plan(self, board, species, groups):
        enemies = board.get_species_groups(_other(species))
        if not enemies:
            return []
        forbidden = {p for p, _ in groups}
        taken: Set[Pos] = set()
        turn: Turn = []
        for pos, count in sorted(groups, key=lambda g: (-g[1], g[0])):
            ep, e = _nearest(enemies, pos)
            dest = None
            if _cheb(ep, pos) == 1:
                if count >= e and ep not in taken:
                    dest = ep                                            # attack
            else:
                dest = _step_toward(board, species, pos, count, ep, forbidden | taken)
            if dest is not None:
                turn.append((pos[0], pos[1], count, dest[0], dest[1]))
                taken.add(dest)
        return turn


class Turtle(_PanelAgent):
    """Grabs humans within RADIUS of its start (if strong enough), takes certain kills, else shuffles at home."""

    RADIUS = 6

    def plan(self, board, species, groups):
        home = self._home
        enemies = board.get_species_groups(_other(species))
        humans = [(p, h) for p, h in board.get_humans() if _cheb(p, home) <= self.RADIUS]
        forbidden = {p for p, _ in groups}
        taken: Set[Pos] = set()
        turn: Turn = []
        for pos, count in sorted(groups, key=lambda g: (-g[1], g[0])):
            dest = None
            for ep, e in enemies:
                if _cheb(ep, pos) == 1 and count >= 1.5 * e and ep not in taken:
                    dest = ep
                    break
            if dest is None:
                for hp, h in humans:
                    if _cheb(hp, pos) == 1 and count >= h and hp not in taken:
                        dest = hp
                        break
            if dest is None:
                reachable = [(hp, h) for hp, h in humans if h <= count and hp not in taken]
                if reachable:
                    dest = _step_toward(board, species, pos, count, _nearest(reachable, pos)[0],
                                        forbidden | taken)
            if dest is None:
                if pos != home:                                          # go back home
                    dest = _step_toward(board, species, pos, count, home, forbidden | taken)
                else:                                                    # shuffle one step, safest side
                    options = [n for n in board.get_neighbors(pos)
                               if n not in forbidden | taken
                               and _cell(board, species, n)[0] == 0 and _cell(board, species, n)[2] == 0]
                    if options:
                        def key(n):
                            far = min((_cheb(n, ep) for ep, _ in enemies), default=99)
                            return (_danger(board, species, n, count), -far, n)
                        dest = min(options, key=key)
            if dest is not None:
                turn.append((pos[0], pos[1], count, dest[0], dest[1]))
                taken.add(dest)
        return turn


PANEL: Dict[str, Callable[[], object]] = {
    "Random": lambda: RandomAgent(),
    "Starter": lambda: AIAgent("Starter"),
    "Grabber": lambda: Grabber(),
    "Rusher": lambda: Rusher(),
    "Turtle": lambda: Turtle(),
    "OnePly": lambda: SearchAgent("OnePly", depth=1),
}


def make_opponent(name: str):
    """Fresh instance of a panel opponent (agents keep no state between games)."""
    return PANEL[name]()
