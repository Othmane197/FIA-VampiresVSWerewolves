"""
move_generator.py  (our own file; it does not modify any shared repo file)

Answers: "for this board and this species, which TURNS should the bot consider?"
A turn is a list of moves (src_x, src_y, count, dst_x, dst_y), one move per group that moves.

Why restrict? All legal turns are astronomically many (see chat: ~10^13 with 4 groups).
We keep a short, ranked list built from these ideas (our design, not from the course):

 Per group, at most `max_directions` directions, taken in this priority order:
   1. neighbours that hold humans or enemy monsters (immediate battles),
   2. one "flee" neighbour if a nearby enemy group is at least as big as ours,
   3. one step toward each of the `nearest_goals` nearest goals (human or enemy groups),
      considering only goals this group is strong enough for (size <= our count) when any exist,
   4. if every kept direction is an attack, one quiet sidestep ("wait") so that a bad gamble
      is never forced (a lone group cannot stay put: Rule 1).
 Per direction, up to two amounts:
   * the whole group, and
   * "just enough" = the smallest force that makes the battle certain
       humans:   as many as the humans (E1 >= E2 converts for sure)
       monsters: ceil(1.5 * defenders) (E1 >= 1.5 * E2 kills for sure)
     (only if that is smaller than the whole group, so a reserve stays behind).
 Plus the option "stay", and SPLIT options: "just enough" to a certain attack and the rest of the
 group to another kept direction (the official server allows several moves from one cell as long
 as the total does not exceed the creatures there).

 Joint turns are enumerated best-first and filtered by the rules of the official server
 (read from VVSW.Model.dll, see server_rules.py):
   * at least one move; no cell is both source and target; per-source total <= creatures there,
   * several groups MAY attack the same cell: they are pooled into one attacking force, so two
     groups that are each too weak can together reach the certain-win threshold.
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
                   max_directions: int, nearest_goals: int) -> List[Tuple[tuple, List[Move]]]:
    """Ranked options for ONE group: list of (rank_key, moves); an empty list means 'stay'."""
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

    # Only approach goals this group is strong enough for (humans we can convert, enemies we are
    # not weaker than); if there is none, fall back to all goals.
    usable = [g for g in goals if g[1] <= count]
    pool = usable or goals
    for g_pos, g_size, g_humans in sorted(pool, key=lambda g: (_cheb(pos, g[0]), g[0]))[:nearest_goals]:
        step = (_sign(g_pos[0] - x), _sign(g_pos[1] - y))      # 3. straight step toward the goal
        if step == (0, 0):
            continue
        dst = (x + step[0], y + step[1])
        if dst not in directions:
            directions[dst] = ("approach", g_humans, g_size)

    chosen = list(directions.items())[:max_directions]

    # 4. Always keep one quiet option: if every kept direction is an attack, add a sidestep to a
    #    free neighbouring cell, away from the enemy and close to a usable goal. Without it a lone
    #    group (which cannot "stay": Rule 1) would be forced into a bad gamble.
    if not any(info[0] != "attack" for _, info in chosen):
        quiet = [n for n in neighbors if n not in directions]

        def sidestep_key(n):
            d_enemy = min((_cheb(n, p) for p, _ in enemy_groups), default=99)
            d_goal = min((_cheb(n, g[0]) for g in pool), default=0)
            return (-min(d_enemy, 3), d_goal, n)
        if quiet:
            chosen.append((min(quiet, key=sidestep_key), ("wait", None, 0)))

    options: List[Tuple[tuple, List[Move]]] = []
    certain_attacks = []                                 # (key, dst, need) for the split options
    for dst, (kind, is_humans, size) in chosen:
        amounts = [count]
        if kind not in ("flee", "wait"):
            need = needed_force(size, is_humans)
            if 0 < need < count:
                amounts.append(need)
        for a in amounts:
            move = (x, y, a, dst[0], dst[1])
            if kind == "attack":                         # expected change in material (ours - theirs)
                o = expected_outcome(a, size, is_humans)
                delta = (o.friendly - a) + (0 if is_humans else size - o.enemy)
                key = (0, -delta) if delta > 0 else (4, -delta)
                if a < count and a >= needed_force(size, is_humans):
                    certain_attacks.append((key, dst, a))
            elif kind == "flee":
                key = (1, 0)
            elif kind == "wait":
                key = (3, 1)
            else:
                key = (2, 0)
            options.append((key, [move]))

    # SPLIT: the smallest certain attack on one target, the rest of the group to another direction.
    for key, atk_dst, a in certain_attacks:
        if key[0] != 0:
            continue
        for dst, (kind, _, _) in chosen:
            if dst == atk_dst or kind == "attack":
                continue                                 # the rest goes somewhere quiet or toward a goal
            options.append(((key[0], key[1] + 0.01),
                            [(x, y, a, atk_dst[0], atk_dst[1]), (x, y, count - a, dst[0], dst[1])]))
    options.append(((3, 0), []))                         # stay
    options.sort(key=lambda o: o[0])                     # stable: ties keep creation order
    return options


def _compatible(moves: Turn) -> bool:
    """Rule 5: no cell is both a source and a target. (Pooled attacks and merges are allowed.)"""
    sources = {(m[0], m[1]) for m in moves}
    return all((m[3], m[4]) not in sources for m in moves)


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
        moves = [m for opts, i in zip(per_group, idx) for m in opts[i][1]]
        if moves and _compatible(moves):
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
