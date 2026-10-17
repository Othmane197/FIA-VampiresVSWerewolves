"""
move_generator.py  (our own file; it does not modify any shared repo file)

Answers: "for this board and this species, which TURNS should the bot consider?"
A turn is a list of moves (src_x, src_y, count, dst_x, dst_y), one move per group that moves.

Why restrict? All legal turns are astronomically many (see chat: ~10^13 with 4 groups).
We keep a short, ranked list built from these ideas (our design, not from the course):

 Per group, at most `max_directions` directions, taken in this priority order:
   1. neighbours that hold humans or enemy monsters (immediate battles),
   2. one "flee" neighbour if a nearby enemy group is at least as big as ours,
   3. one step toward each of the `nearest_goals` nearest goals (human or enemy groups).
 Per direction, up to two amounts:
   * the whole group, and
   * "just enough" = the smallest force that makes the battle certain
       humans:   as many as the humans (E1 >= E2 converts for sure)
       monsters: ceil(1.5 * defenders) (E1 >= 1.5 * E2 kills for sure)
     (only if that is smaller than the whole group, so a reserve stays behind).
 Plus the option "stay".

 Joint turns are enumerated best-first and filtered by these rules:
   * Rules 1-6 of the spec (at least one move; no cell is both source and target; ...),
   * SAFE ASSUMPTIONS, until verified on the real server:
       - at most ONE move per source cell,
       - no two moves into the same cell holding humans or enemy monsters.
 The result is capped at `max_candidates` turns and ordered so that promising turns come
 first (useful later for alpha-beta pruning).
"""
import heapq
from typing import Dict, List, Optional, Set, Tuple

from battle_model import expected_outcome
from game_engine import BoardState
from game_state import Species

Move = Tuple[int, int, int, int, int]
Turn = List[Move]
Pos = Tuple[int, int]


def _cheb(a: Pos, b: Pos) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _sign(v: int) -> int:
    return (v > 0) - (v < 0)


def needed_force(defenders: int, defenders_are_humans: bool) -> int:
    """Smallest attacking force that makes the battle certain."""
    if defenders_are_humans:
        return defenders
    return (3 * defenders + 1) // 2          # ceil(1.5 * defenders), in integers


def _group_options(board: BoardState, pos: Pos, count: int, species: Species,
                   goals: List[Tuple[Pos, int, bool]], enemy_groups: List[Tuple[Pos, int]],
                   max_directions: int, nearest_goals: int) -> List[Tuple[tuple, Optional[Move]]]:
    """Ranked options for ONE group: list of (rank_key, move); move None means 'stay'."""
    x, y = pos
    en = 2 if species == Species.VAMPIRE else 1          # index of enemy monsters in a cell tuple
    neighbors = board.get_neighbors(pos)

    # direction -> (kind, defenders_are_humans, size of what is there / being approached)
    directions: Dict[Pos, tuple] = {}
    for n in neighbors:                                  # 1. immediate battles
        cell = board.get_cell(n)
        if cell[0] > 0:
            directions[n] = ("attack", True, cell[0])
        elif cell[en] > 0:
            directions[n] = ("attack", False, cell[en])

    threats = [(p, c) for p, c in enemy_groups if _cheb(pos, p) <= 2 and c >= count]
    if threats:                                          # 2. flee from a strong enemy nearby
        quiet = [n for n in neighbors
                 if n not in directions]
        if quiet:
            def safety(n):
                return (min(_cheb(n, p) for p, _ in threats),
                        sum((n[0] - p[0]) ** 2 + (n[1] - p[1]) ** 2 for p, _ in threats))
            directions[max(quiet, key=safety)] = ("flee", None, 0)

    for g_pos, g_size, g_humans in sorted(goals, key=lambda g: (_cheb(pos, g[0]), g[0]))[:nearest_goals]:
        step = (_sign(g_pos[0] - x), _sign(g_pos[1] - y))      # 3. straight step toward the goal
        if step == (0, 0):
            continue
        dst = (x + step[0], y + step[1])
        if dst not in directions:
            directions[dst] = ("approach", g_humans, g_size)

    options: List[Tuple[tuple, Optional[Move]]] = []
    for dst, (kind, is_humans, size) in list(directions.items())[:max_directions]:
        amounts = [count]
        if kind != "flee":
            need = needed_force(size, is_humans)
            if 0 < need < count:
                amounts.append(need)
        for a in amounts:
            move = (x, y, a, dst[0], dst[1])
            if kind == "attack":                         # expected change in material (ours - theirs)
                o = expected_outcome(a, size, is_humans)
                delta = (o.friendly - a) + (0 if is_humans else size - o.enemy)
                key = (0, -delta) if delta > 0 else (4, -delta)
            elif kind == "flee":
                key = (1, 0)
            else:
                key = (2, 0)
            options.append((key, move))
    options.append(((3, 0), None))                       # stay
    options.sort(key=lambda o: o[0])                     # stable: ties keep creation order
    return options


def _compatible(moves: Turn, occupied: Set[Pos]) -> bool:
    sources = {(m[0], m[1]) for m in moves}
    seen: Set[Pos] = set()
    for m in moves:
        dst = (m[3], m[4])
        if dst in sources:                               # Rule 5
            return False
        if dst in occupied:                              # safe assumption: no double attack
            if dst in seen:
                return False
            seen.add(dst)
    return True


def generate_turns(board: BoardState, species: Species, max_candidates: int = 100,
                   max_directions: int = 3, nearest_goals: int = 3,
                   max_expansions: int = 5000) -> List[Turn]:
    """Ranked list of candidate turns for `species` on `board` (the board is not modified)."""
    ours = board.get_species_groups(species)
    if not ours:
        return []
    enemy = Species.WEREWOLF if species == Species.VAMPIRE else Species.VAMPIRE
    enemy_groups = board.get_species_groups(enemy)
    goals = [(p, c, True) for p, c in board.get_humans()] + [(p, c, False) for p, c in enemy_groups]
    occupied = {p for p, _ in board.get_humans()} | {p for p, _ in enemy_groups}

    per_group = [_group_options(board, pos, cnt, species, goals, enemy_groups,
                                max_directions, nearest_goals) for pos, cnt in ours]

    # Best-first enumeration of joint choices: cost = sum of option ranks (0 = best).
    start = (0,) * len(per_group)
    heap = [(0, start)]
    seen = {start}
    turns: List[Turn] = []
    expansions = 0
    while heap and len(turns) < max_candidates and expansions < max_expansions:
        cost, idx = heapq.heappop(heap)
        expansions += 1
        moves = [opts[i][1] for opts, i in zip(per_group, idx) if opts[i][1] is not None]
        if moves and _compatible(moves, occupied):
            turns.append(moves)
        for j in range(len(idx)):
            if idx[j] + 1 < len(per_group[j]):
                nxt = idx[:j] + (idx[j] + 1,) + idx[j + 1:]
                if nxt not in seen:
                    seen.add(nxt)
                    heapq.heappush(heap, (cost + 1, nxt))

    if not turns:                                        # safety net: one plain legal move
        (x, y), cnt = ours[0]
        nx, ny = board.get_neighbors((x, y))[0]
        turns = [[(x, y, cnt, nx, ny)]]
    return turns


if __name__ == "__main__":
    from map_loader import load_map, render_board
    board = load_map("thetrap.xml")
    print(render_board(board))
    for sp in (Species.VAMPIRE, Species.WEREWOLF):
        turns = generate_turns(board, sp)
        print(f"\n{sp.value}: {len(turns)} candidate turns")
        for t in turns:
            print("  ", t)
