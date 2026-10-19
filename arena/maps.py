"""
Test maps for the arena. Every generated map is POINT-SYMMETRIC: (x, y) is mirrored to
(cols-1-x, rows-1-y), both species start on mirrored cells with the same army and every house
has a twin of the same size. Combined with playing both species, no bot gets a map advantage.

Families (the real tournament maps are unknown, so we cover several styles):
    given      the 3 XML maps shipped with the server
    sym        random houses, Dana-style (various sizes)
    villages   MANY small houses (1-4): where splitting should shine
    prize      one big central prize + a few small houses: tests greed vs safety
    close      starts close together: tests early fights / rushing
    sparse     few, medium houses far apart: tests whether splitting is wasteful

build_suite(name) returns a fixed, deterministic list [(map_name, State)].
write_xml(state, path) saves a map that the real server GUI can load.
"""
import os
import random
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from splitter.state import State

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GIVEN = ["thetrap.xml", "testmap.xml"]          # testmap2.xml is identical to testmap.xml


def load_xml(path: str, max_ply: int = 200) -> State:
    """Read a server map file (XML) into a State."""
    if not os.path.isabs(path):
        path = os.path.join(ROOT, path)
    root = ET.parse(path).getroot()
    h: Dict = {}
    v: Dict = {}
    w: Dict = {}
    for e in root:
        pos = (int(e.attrib["X"]), int(e.attrib["Y"]))
        n = int(e.attrib["Count"])
        {"Humans": h, "Vampires": v, "Werewolves": w}[e.tag][pos] = n
    return State(int(root.attrib["Rows"]), int(root.attrib["Columns"]), h, v, w, 0, max_ply)


def write_xml(state: State, path: str) -> None:
    """Save a State as a server map file, so the real GUI can load it."""
    lines = ['<?xml version="1.0" encoding="utf-8" ?>',
             f'<Map Rows="{state.rows}" Columns="{state.cols}">']
    for pos, n in sorted(state.humans.items()):
        lines.append(f'  <Humans X="{pos[0]}" Y="{pos[1]}" Count="{n}"/>')
    for (pos, n) in state.groups[0].items():
        lines.append(f'  <Vampires X="{pos[0]}" Y="{pos[1]}" Count="{n}"/>')
    for (pos, n) in state.groups[1].items():
        lines.append(f'  <Werewolves X="{pos[0]}" Y="{pos[1]}" Count="{n}"/>')
    lines.append("</Map>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _cheb(a, b):
    """King-move distance (local copy, keeps this module independent)."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def symmetric_map(seed: int, rows: int, cols: int, army: int, n_pairs: int, hmin: int, hmax: int,
                  center: Optional[int] = None, start_gap: Optional[int] = None,
                  max_ply: int = 200) -> State:
    """Random point-symmetric map: mirrored starts and mirrored houses of equal size."""
    rng = random.Random(seed)
    mirror = lambda p: (cols - 1 - p[0], rows - 1 - p[1])
    gap = start_gap if start_gap is not None else max(3, (min(rows, cols) * 2) // 3)
    v, w = (0, 0), mirror((0, 0))
    for _ in range(10000):
        v = (rng.randrange(cols), rng.randrange(rows))
        w = mirror(v)
        # (on even-sized boards mirrored cells are always an odd distance apart: allow +-1)
        if v != w and (_cheb(v, w) >= gap if start_gap is None else abs(_cheb(v, w) - gap) <= 1):
            break
    h: Dict = {}
    used = {v, w}
    placed = attempts = 0
    while placed < n_pairs and attempts < 5000:
        attempts += 1
        c = (rng.randrange(cols), rng.randrange(rows))
        m = mirror(c)
        if c == m or c in used or m in used or min(_cheb(c, v), _cheb(c, w)) < 2:
            continue
        n = rng.randint(hmin, hmax)
        h[c] = n
        h[m] = n
        used |= {c, m}
        placed += 1
    if center:
        ctr = ((cols - 1) // 2, (rows - 1) // 2)
        if cols % 2 == 1 and rows % 2 == 1 and ctr not in used:
            h[ctr] = center
    return State(rows, cols, h, {v: army}, {w: army}, 0, max_ply)


# (name, seed, rows, cols, army, pairs, hmin, hmax, center, start_gap)
_SPECS = {
    "sym": [
        ("sym_9x15a", 3, 9, 15, 8, 5, 1, 6, None, None),
        ("sym_9x15b", 4, 9, 15, 8, 4, 2, 8, 12, None),
        ("sym_11x21", 6, 11, 21, 10, 6, 1, 6, None, None),
        ("sym_15x29", 8, 15, 29, 10, 6, 1, 6, 20, None),
    ],
    "villages": [
        ("vil_10x16", 11, 10, 16, 10, 9, 1, 4, None, None),
        ("vil_13x21", 12, 13, 21, 12, 12, 1, 4, None, None),
        ("vil_15x25", 13, 15, 25, 14, 14, 1, 5, 9, None),
    ],
    "prize": [
        ("prize_11x17", 21, 11, 17, 10, 3, 2, 5, 18, None),
        ("prize_13x23", 22, 13, 23, 12, 4, 2, 6, 24, None),
    ],
    "close": [
        ("close_8x12", 31, 8, 12, 8, 4, 1, 5, None, 4),
        ("close_11x15", 32, 11, 15, 12, 6, 1, 6, 9, 5),
    ],
    "sparse": [
        ("sparse_12x20", 41, 12, 20, 10, 3, 4, 9, None, None),
    ],
}

_cache: Dict[str, List[Tuple[str, State]]] = {}


def build_suite(name: str = "all", max_ply: int = 200) -> List[Tuple[str, State]]:
    """name: 'all', 'given', a family name, or a comma-separated list of map names/families."""
    key = f"{name}:{max_ply}"
    if key in _cache:
        return _cache[key]
    every: List[Tuple[str, State]] = [(p.replace(".xml", ""), load_xml(p, max_ply)) for p in GIVEN]
    families = {"given": [m[0] for m in every]}
    for fam, specs in _SPECS.items():
        families[fam] = []
        for nm, seed, rows, cols, army, pairs, hmin, hmax, center, gap in specs:
            every.append((nm, symmetric_map(seed, rows, cols, army, pairs, hmin, hmax, center, gap, max_ply)))
            families[fam].append(nm)
    if name == "all":
        out = every
    else:
        wanted = []
        for part in name.split(","):
            part = part.strip()
            wanted += families.get(part, [part])
        out = [m for m in every if m[0] in wanted]
        if not out:
            raise ValueError(f"unknown map/family {name!r}; families: {sorted(families)}")
    _cache[key] = out
    return out


def render(state: State) -> str:
    """ASCII board: V12 / W7 / H4, '.' empty."""
    out = ["    " + "".join(f"{x % 100:3d}" for x in range(state.cols))]
    for y in range(state.rows):
        row = [f"{y:3d} "]
        for x in range(state.cols):
            p = (x, y)
            if p in state.groups[0]:
                row.append(f"V{state.groups[0][p]:<2d}"[:3])
            elif p in state.groups[1]:
                row.append(f"W{state.groups[1][p]:<2d}"[:3])
            elif p in state.humans:
                row.append(f"H{state.humans[p]:<2d}"[:3])
            else:
                row.append(" . ")
        out.append("".join(row))
    out.append(f"    V={state.total(0)}  W={state.total(1)}  H={state.humans_total()}  ply={state.ply}")
    return "\n".join(out)
