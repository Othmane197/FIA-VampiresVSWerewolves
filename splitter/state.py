"""
Compact, fast game state used by the Splitter's search and by the local arena referee.

    State.humans          {pos: count}
    State.groups[side]    {pos: count}   side = V (0) or W (1), see rules.py
    State.ply             plies already played (both players together)
    State.max_ply         the server's MaxPlays (200 by default: 100 moves each)

State.apply(side, moves) resolves a turn exactly like Board.PerformMoves on the real server:
creatures leave their sources, moves are grouped by destination and summed, then each
destination is resolved (merge / convert / kill / random battle).
"""
from typing import Dict, Optional, Sequence, Tuple

from .rules import MAX_CELL, Move, Pos, V, W, resolve_battle

_NEIGHBORS: Dict[Tuple[int, int], Dict[Pos, Tuple[Pos, ...]]] = {}
_DIRS = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))


def neighbors_table(rows: int, cols: int) -> Dict[Pos, Tuple[Pos, ...]]:
    """{cell: (adjacent cells inside the board)}; built once per board size."""
    key = (rows, cols)
    table = _NEIGHBORS.get(key)
    if table is None:
        table = {}
        for x in range(cols):
            for y in range(rows):
                table[(x, y)] = tuple((x + dx, y + dy) for dx, dy in _DIRS
                                      if 0 <= x + dx < cols and 0 <= y + dy < rows)
        _NEIGHBORS[key] = table
    return table


class State:
    """Board position: humans, both species' groups, ply counter. Cheap to copy, exact to update."""
    __slots__ = ("cols", "groups", "humans", "max_ply", "nbrs", "ply", "rows")

    def __init__(self, rows: int, cols: int, humans: Optional[Dict[Pos, int]] = None,
                 vampires: Optional[Dict[Pos, int]] = None, werewolves: Optional[Dict[Pos, int]] = None,
                 ply: int = 0, max_ply: int = 200):
        """Build a state from {pos: count} dictionaries."""
        self.rows = rows
        self.cols = cols
        self.humans = dict(humans or {})
        self.groups = (dict(vampires or {}), dict(werewolves or {}))
        self.ply = ply
        self.max_ply = max_ply
        self.nbrs = neighbors_table(rows, cols)

    # ------------------------------------------------------------------ basics
    def copy(self) -> "State":
        """Independent copy (the dictionaries are copied, the neighbour table is shared)."""
        s = State.__new__(State)
        s.rows = self.rows
        s.cols = self.cols
        s.humans = dict(self.humans)
        s.groups = (dict(self.groups[0]), dict(self.groups[1]))
        s.ply = self.ply
        s.max_ply = self.max_ply
        s.nbrs = self.nbrs
        return s

    def total(self, side: int) -> int:
        """Total number of creatures of one side."""
        return sum(self.groups[side].values())

    def humans_total(self) -> int:
        """Total number of humans left on the board."""
        return sum(self.humans.values())

    def is_terminal(self) -> bool:
        """Game over: a species is wiped out or the ply limit is reached."""
        return (not self.groups[V]) or (not self.groups[W]) or self.ply >= self.max_ply

    def winner(self) -> Optional[int]:
        """Side with more creatures (the server's rule at the end), None if equal."""
        v, w = self.total(V), self.total(W)
        if v > w:
            return V
        if w > v:
            return W
        return None

    def key(self) -> tuple:
        """Hashable snapshot of the position (used in tests to compare states)."""
        return (tuple(sorted(self.humans.items())), tuple(sorted(self.groups[0].items())),
                tuple(sorted(self.groups[1].items())))

    def __repr__(self) -> str:
        """Readable one-line description for debugging."""
        return (f"State({self.rows}x{self.cols} ply={self.ply} H={self.humans} "
                f"V={self.groups[V]} W={self.groups[W]})")

    # ------------------------------------------------------------------ rules
    def apply(self, side: int, moves: Sequence[Move], rng=None, mode: str = "sample") -> "State":
        """New state after `side` plays `moves` (assumed legal: see rules.check_moves)."""
        s = self.copy()
        s.ply += 1
        mine = s.groups[side]
        theirs = s.groups[1 - side]
        humans = s.humans
        arriving: Dict[Pos, int] = {}
        for x1, y1, n, x2, y2 in moves:
            src = (x1, y1)
            left = mine[src] - n
            if left > 0:
                mine[src] = left
            else:
                del mine[src]
            dst = (x2, y2)
            arriving[dst] = arriving.get(dst, 0) + n
        for dst, n in arriving.items():
            e = theirs.get(dst)
            if e:
                win, survivors = resolve_battle(n, e, False, mode, rng)
                if win:
                    del theirs[dst]
                    if survivors:
                        mine[dst] = min(MAX_CELL, survivors)
                elif survivors:
                    theirs[dst] = survivors
                else:
                    del theirs[dst]
                continue
            h = humans.get(dst)
            if h:
                win, survivors = resolve_battle(n, h, True, mode, rng)
                if win:
                    del humans[dst]
                    if survivors:
                        mine[dst] = min(MAX_CELL, survivors)
                elif survivors:
                    humans[dst] = survivors
                else:
                    del humans[dst]
                continue
            mine[dst] = min(MAX_CELL, mine.get(dst, 0) + n)
        return s

    # ------------------------------------------------------------------ conversions
    @staticmethod
    def from_cells(rows: int, cols: int, cells, ply: int = 0, max_ply: int = 200) -> "State":
        """cells: iterable of ((x, y), humans, vampires, werewolves)."""
        h, v, w = {}, {}, {}
        for pos, hu, va, we in cells:
            if hu:
                h[pos] = hu
            if va:
                v[pos] = va
            if we:
                w[pos] = we
        return State(rows, cols, h, v, w, ply, max_ply)

    @staticmethod
    def from_game_state(gs, ply: int = 0, max_ply: int = 200) -> "State":
        """From the repo's game_state.GameState (what main.py maintains)."""
        return State.from_cells(gs.rows, gs.cols,
                                ((p, c.humans, c.vampires, c.werewolves) for p, c in gs.board.items()),
                                ply, max_ply)

    @staticmethod
    def from_board(board, ply: Optional[int] = None) -> "State":
        """From game_engine.BoardState (the teammates' search board)."""
        return State.from_cells(board.rows, board.cols,
                                ((p, c[0], c[1], c[2]) for p, c in board.grid.items()),
                                board.turn_count if ply is None else ply, board.max_turns)

    def to_board(self):
        """Convert to game_engine.BoardState (the teammates' search board)."""
        from game_engine import BoardState
        b = BoardState(self.rows, self.cols, self.max_ply)
        b.turn_count = self.ply
        for pos in set(self.humans) | set(self.groups[V]) | set(self.groups[W]):
            b.set_cell(pos, self.humans.get(pos, 0), self.groups[V].get(pos, 0),
                       self.groups[W].get(pos, 0))
        return b

    def to_game_state(self, side: int, home: Optional[Pos] = None):
        """Convert to game_state.GameState, as main.py would hold it for `side`."""
        from game_state import Cell, GameState, Species
        gs = GameState()
        gs.set_grid(self.rows, self.cols)
        gs.our_species = Species.VAMPIRE if side == V else Species.WEREWOLF
        gs.enemy_species = Species.WEREWOLF if side == V else Species.VAMPIRE
        if home is not None:
            gs.set_home(home)
        for pos in set(self.humans) | set(self.groups[V]) | set(self.groups[W]):
            gs.board[pos] = Cell(self.humans.get(pos, 0), self.groups[V].get(pos, 0),
                                 self.groups[W].get(pos, 0))
        return gs


def side_of_species(species) -> int:
    """game_state.Species -> V / W."""
    return V if getattr(species, "value", species) == "VAMPIRE" else W
