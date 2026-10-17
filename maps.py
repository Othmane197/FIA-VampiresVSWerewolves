"""
maps.py  (our own file; it does not modify any shared repo file)

Test maps, so that we do not tune the bot on only the three given maps.

 * make_symmetric_map(...) builds a random map with POINT SYMMETRY: the cell (x, y) is mirrored to
   (cols-1-x, rows-1-y). The vampires start on one cell, the werewolves on its mirror image,
   every human group has a twin of the same size. Nobody has a positional advantage (we also
   play both species on every map), so a win rate far from 50% between equal bots would point
   at the bots, not at the map.
 * build_suite() returns the fixed list of test maps: the 3 given maps + generated ones.
   It is deterministic, so everybody gets the same maps.
 * write_xml(board, path) saves a map in the same XML format as the given maps, so the same
   map can later be loaded by the real server's GUI.

The real tournament maps are unknown (the course provides MapGenerator.exe, which we could not run
here). These maps only approximate them.
"""
import random
from typing import List, Optional, Tuple

from game_engine import BoardState
from map_loader import load_map

Pos = Tuple[int, int]


def mirror(pos: Pos, rows: int, cols: int) -> Pos:
    return (cols - 1 - pos[0], rows - 1 - pos[1])


def _cheb(a: Pos, b: Pos) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def make_symmetric_map(seed: int, rows: int, cols: int, army: int, n_pairs: int, human_max: int,
                       center_group: Optional[int] = None, max_turns: int = 200) -> BoardState:
    """
    Random point-symmetric map.
      army          creatures each side starts with (one group)
      n_pairs       number of mirrored PAIRS of human groups
      human_max     each pair gets a size drawn from 1..human_max
      center_group  size of one extra human group on the centre cell (needs odd rows AND columns)
    """
    rng = random.Random(seed)
    board = BoardState(rows, cols, max_turns)
    min_gap = max(3, min(rows, cols) // 2)

    while True:                                                    # starting cells: far apart, mirrored
        v = (rng.randrange(cols), rng.randrange(rows))
        w = mirror(v, rows, cols)
        if _cheb(v, w) >= min_gap:
            break
    board.set_cell(v, 0, army, 0)
    board.set_cell(w, 0, 0, army)

    used = {v, w}
    placed = 0
    attempts = 0
    while placed < n_pairs and attempts < 1000:
        attempts += 1
        c = (rng.randrange(cols), rng.randrange(rows))
        m = mirror(c, rows, cols)
        if c == m or c in used or m in used:
            continue
        if min(_cheb(c, v), _cheb(c, w)) < 2:                      # not right on top of a start
            continue
        size = rng.randint(1, human_max)
        board.set_cell(c, size, 0, 0)
        board.set_cell(m, size, 0, 0)
        used |= {c, m}
        placed += 1

    if center_group:
        centre = ((cols - 1) // 2, (rows - 1) // 2)
        if cols % 2 == 1 and rows % 2 == 1 and centre not in used:
            board.set_cell(centre, center_group, 0, 0)
    return board


# (name, seed, rows, cols, army, pairs, human_max, center_group)
_GENERATED = [
    ("g5x10a", 1, 5, 10, 4, 3, 4, None),
    ("g5x10b", 2, 5, 10, 6, 3, 5, None),
    ("g9x15a", 3, 9, 15, 8, 5, 6, None),
    ("g9x15b", 4, 9, 15, 8, 4, 8, 12),
    ("g9x15c", 5, 9, 15, 6, 6, 5, None),
    ("g11x21a", 6, 11, 21, 10, 6, 6, None),
    ("g11x21b", 7, 11, 21, 12, 5, 8, 14),
    ("g15x29a", 8, 15, 29, 10, 6, 6, 20),
    ("g15x29b", 9, 15, 29, 14, 7, 8, None),
]
_GIVEN = ["thetrap.xml", "testmap.xml", "testmap2.xml"]

_cache = None


def build_suite() -> List[Tuple[str, BoardState]]:
    """[(name, board)] : the 3 given maps, then the generated ones. Boards must not be modified."""
    global _cache
    if _cache is None:
        suite = [(p.replace(".xml", ""), load_map(p)) for p in _GIVEN]
        for name, seed, rows, cols, army, pairs, hmax, centre in _GENERATED:
            suite.append((name, make_symmetric_map(seed, rows, cols, army, pairs, hmax, centre)))
        _cache = suite
    return _cache


def write_xml(board: BoardState, path: str) -> None:
    """Save `board` in the XML format of the given maps (X = column, Y = row)."""
    lines = ['<?xml version="1.0" encoding="utf-8" ?>',
             f'<Map Rows="{board.rows}" Columns="{board.cols}">']
    for (x, y), (h, v, w) in sorted(board.grid.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        if h:
            lines.append(f'  <Humans X="{x}" Y="{y}" Count="{h}"/>')
        if w:
            lines.append(f'  <Werewolves X="{x}" Y="{y}" Count="{w}"/>')
        if v:
            lines.append(f'  <Vampires X="{x}" Y="{y}" Count="{v}"/>')
    lines.append('</Map>')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
