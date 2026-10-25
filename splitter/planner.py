"""
Joint-plan generator of "The Splitter" (the macro-actions searched by MCTS).

Raw moves are hopeless to search (a group of n creatures has ~8^k * C(n, k) ways to split), so
each turn we only consider a SHORT list of sensible joint plans:

  * every group gets a ranked list of GOALS (candidate_goals): convert a house we win the race
    to, kill an enemy group we beat 1.5x, merge with a friend, flee from a threat, or gamble;
  * the BASE plan gives every group its best goal; VARIANTS change one group's goal;
  * SPLIT plans (the point of this bot): from a big group, send detachments of EXACTLY h
    creatures to houses of size h (a sure conversion, the detachment comes back with 2h), while
    the main body keeps the rest. A detachment is only allowed if detachment_safe() proves that
    no enemy can catch it before or right after it converts;
  * REGROUP, HUNT, FLEE and (when losing) GAMBLE plans give the search strategic alternatives;
    with the strike_p option, STRIKE plans also offer good-odds first strikes when not losing.

Each goal is turned into one step by safe_step(), which never walks into humans or enemies it
cannot beat for sure and avoids cells that an enemy could attack with good odds.
All plans are checked with rules.check_moves (the server's own cheating rules).
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .rules import MAX_CELL, Move, Pos, cheb, check_moves, win_probability
from .state import State

GAMMA = 0.9          # a house d moves away is worth GAMMA**d of a house next to us
PROTECTED = ("base", "flee", "regroup", "regroup+go", "hunt", "strike")


@dataclass
class PlanConfig:
    """Every tunable of the plan generator (the bot's variants are just different PlanConfigs)."""

    splits: bool = True            # allow detachments (False = "deathball" variant)
    max_detachments: int = 3       # per group and per turn
    split_groups: int = 2          # how many of our biggest groups may split in one plan
    alt_groups: int = 4            # how many groups get "alternative goal" variants
    safety_margin: int = 1         # extra moves of distance required from 1.5x-bigger enemies
    reserve_ratio: float = 1.0     # main body must stay >= ratio * nearby enemy groups
    reserve_radius: int = 6        # "nearby" for the reserve rule (3 lost close-start maps)
    gamble: str = "adaptive"       # "never" | "adaptive" (only when behind) | "always"
    max_plans: int = 18
    danger_weight: float = 3.0     # steps of detour accepted to avoid one expected creature loss / size
    danger_strike_p: float = 0.45  # safe_step: an adjacent enemy is assumed to strike above these odds
    commit_bonus: float = 0.35     # value bonus for keeping last turn's goal (stops oscillation)
    pincer: bool = True            # synchronized multi-group conversion of a house too big for one group
    hunt_bonus: float = 0.1        # prior bonus of the "hunt" plan (raised against splitting opponents)
    # ---- campaign-3 options (chapter 16), off by default; the flagship uses bait_check and strike_p
    bait_check: bool = False       # discount a kill whose victim cell sits next to another strong enemy
    strike_p: float = 0.0          # > 0: "strike" plans against adjacent enemies beaten with these odds,
                                   # even when not behind (0 = only gambles when behind, the flagship)
    gamble_p: float = 0.3          # gamble goals from these odds (lower for a desperate opponent)
    threat_p: float = 0.3          # an enemy within 2 that strikes with these odds is a threat (flee)


@dataclass
class Goal:
    """One candidate objective for one group: a target cell, a kind and an estimated value."""

    kind: str          # "house" | "kill" | "merge" | "flee" | "gamble" | "approach"
    target: Pos
    value: float
    need: int = 0      # creatures needed for a sure result (houses: h, kills: ceil(1.5 e))


@dataclass
class Plan:
    """A joint plan = one full turn (moves of all our groups), with its prior score and a tag."""

    moves: Tuple[Move, ...]
    prior: float
    tag: str
    intents: Tuple[Tuple[Pos, Pos], ...] = ()   # (cell a group ends on, goal it walks to)


# ---------------------------------------------------------------------------- helpers

def _step_dir(a: int, b: int) -> int:
    """-1, 0 or +1: the direction of one king step from coordinate a towards b."""
    return (b > a) - (b < a)


def straight_path(src: Pos, dst: Pos) -> List[Pos]:
    """Cells visited by a king walking diagonally first, then straight (excludes src)."""
    x, y = src
    path = []
    while (x, y) != dst:
        x += _step_dir(x, dst[0])
        y += _step_dir(y, dst[1])
        path.append((x, y))
    return path


def enemy_attack_loss(cell: Pos, count: int,
                      enemies: Dict[Pos, int], strike_p: float = 0.45) -> float:
    """Expected creatures we lose if we stand on `cell` with `count` and the best adjacent enemy
    group attacks us next turn (server rules: any attack is at least a random battle)."""
    worst = 0.0
    for ep, e in enemies.items():
        if cheb(ep, cell) == 1:
            p = win_probability(e, count, False)
            if p > strike_p or e >= count:      # odds at which an enemy is assumed to strike
                loss = p * count
                worst = max(worst, loss)
    return worst


def bait_factor(cell: Pos, count: int, enemies: Dict[Pos, int]) -> float:
    """
    bait_check option: after a sure kill on `cell` our `count` creatures stand there. Another enemy
    group next to that cell could then kill them for sure (x 0.1) or strike at 50%+ (x 0.4).
    """
    factor = 1.0
    for ep, e in enemies.items():
        if ep != cell and cheb(ep, cell) <= 1:
            if e >= 1.5 * count:
                return 0.1
            if e >= count:
                factor = 0.4
    return factor


def race_won(dist_us: int, target: Pos, need: int, enemies: Dict[Pos, int], we_move_first: bool = True) -> bool:
    """Do we reach `target` (a house needing `need`) no later than any enemy group that can take it?"""
    for ep, e in enemies.items():
        if e >= need:
            d = cheb(ep, target)
            if d < dist_us or (d == dist_us and not we_move_first):
                return False
    return True


def detachment_safe(src: Pos, k: int, target: Pos, h: int, enemies: Dict[Pos, int],
                    margin: int = 1) -> bool:
    """
    Can a detachment of k creatures walk from src to the house `target` (h humans, k >= h),
    convert it and survive?
      * on the way (after our t-th move, at cell c_t): any enemy with e >= k that can be
        adjacent by then (cheb(ep, c_t) <= t) could attack with >= 50% odds -> unsafe;
      * on arrival (move d, size k + h): enemies with e >= k + h must not reach it at move d;
        enemies with e >= 1.5 (k + h) must stay `margin` moves further, so that we keep one
        move to escape or rejoin.
    We move first (we are planning our own turn).
    """
    path = straight_path(src, target)
    d = len(path)
    after = k + h
    for ep, e in enemies.items():
        if e >= k:
            for t, c in enumerate(path[:-1], start=1):
                if cheb(ep, c) <= t:
                    return False
        dt = cheb(ep, target)
        if e >= after and dt <= d:
            return False
        if e >= 1.5 * after and dt <= d + margin:
            return False
    return True


def safe_step(state: State, side: int, src: Pos, count: int, goal: Pos, forbidden: Set[Pos],
              enemies: Dict[Pos, int], danger_weight: float, intend_battle: bool = False,
              loss_cache: Optional[dict] = None, strike_p: float = 0.45) -> Optional[Pos]:
    """
    Best neighbour of src to walk `count` creatures towards `goal`:
      * never a cell in `forbidden` (rule 5: cells that are sources this turn);
      * never into humans / enemies we cannot beat for sure, except the goal itself when
        `intend_battle` (a gamble);
      * free conversions / sure kills on the way are welcome;
      * score = distance to goal + danger_weight * (expected loss from an enemy attack) / count.
    """
    humans = state.humans
    best, best_key = None, None
    for n in state.nbrs[src]:
        if n in forbidden:
            continue
        arrive = count
        bonus = 0.0
        e = enemies.get(n, 0)
        if e:
            if count >= 1.5 * e:
                bonus = -0.5 - e / max(count, 1)
            elif not (intend_battle and n == goal):
                continue
        h = humans.get(n, 0)
        if h:
            if count >= h:
                arrive = count + h
                bonus = -0.5 - h / max(count, 1)
            elif not (intend_battle and n == goal):
                continue
        if state.groups[side].get(n, 0) + arrive > MAX_CELL:
            continue
        if e:
            danger = 0.0
        elif loss_cache is not None:
            danger = loss_cache.get((n, arrive))
            if danger is None:
                danger = loss_cache[(n, arrive)] = enemy_attack_loss(n, arrive, enemies, strike_p)
        else:
            danger = enemy_attack_loss(n, arrive, enemies, strike_p)
        dist = cheb(n, goal)
        key = (dist + bonus + danger_weight * danger / max(arrive, 1),
               abs(n[0] - goal[0]) + abs(n[1] - goal[1]))
        if best_key is None or key < best_key:
            best, best_key = n, key
    return best


def border_distance(state: State, p: Pos) -> int:
    """Number of cells between p and the nearest edge of the board (0 = on the edge)."""
    return min(p[0], p[1], state.cols - 1 - p[0], state.rows - 1 - p[1])


def flee_cell(state: State, pos: Pos, count: int, threats: List[Pos], friends: Dict[Pos, int],
              enemies: Dict[Pos, int]) -> Optional[Pos]:
    """
    Where to run: far from the threats FIRST, but into open space (a king chased along an edge or
    into a corner gets caught - a lesson from lost games) and towards friends to merge.
    """
    best, best_score = None, None
    fpos = min(friends, key=lambda f: cheb(pos, f)) if friends else None
    for n in state.nbrs[pos]:
        e = enemies.get(n, 0)
        h = state.humans.get(n, 0)
        if (e and count < 1.5 * e) or (h and count < h):
            continue
        score = 2.0 * min(cheb(n, t) for t in threats) + 0.7 * min(border_distance(state, n), 3)
        if fpos is not None:
            score += 0.6 * (cheb(pos, fpos) - cheb(n, fpos))
        if best_score is None or score > best_score:
            best, best_score = n, score
    return best


# ---------------------------------------------------------------------------- goals

def candidate_goals(state: State, pos: Pos, count: int, friends: Dict[Pos, int],
                    enemies: Dict[Pos, int], cfg: PlanConfig, behind: bool,
                    claimed: Optional[Set[Pos]] = None, committed: Optional[Pos] = None) -> List[Goal]:
    """Ranked goals for one group (best first). `committed` = the goal this group had last turn."""
    claimed = claimed or set()
    goals: List[Goal] = []
    for hp, h in state.humans.items():
        if count >= h and hp not in claimed:
            d = cheb(pos, hp)
            v = h * GAMMA ** d
            if not race_won(d, hp, h, enemies):
                v *= 0.15
            # arriving right next to a big enemy wipes the gain out
            after = count + h
            for ep, e in enemies.items():
                if cheb(ep, hp) <= d + 1:
                    if e >= 1.5 * after:
                        v *= 0.1
                        break
                    if e >= after:              # they would strike right after at >= 50%
                        v *= 0.4
            goals.append(Goal("house", hp, v, h))
    for ep, e in enemies.items():
        if count >= 1.5 * e and ep not in claimed:
            d = cheb(pos, ep)
            v = 1.3 * e * GAMMA ** max(d - 1, 0) + 0.5
            if cfg.bait_check:
                v *= bait_factor(ep, count, enemies)
            goals.append(Goal("kill", ep, v, int(1.5 * e + 0.999)))
    # threats: enemies that can kill us for sure soon, or strike with decent odds right now
    threat = 0.0
    threat_cells = []
    for ep, e in enemies.items():
        d = cheb(ep, pos)
        p = win_probability(e, count, False)
        if (e >= 1.5 * count and d <= 3) or (d <= 2 and p >= cfg.threat_p):
            threat = max(threat, p * count / d)
            threat_cells.append(ep)
    if threat_cells:
        flee = flee_cell(state, pos, count, threat_cells, friends, enemies)
        if flee is not None:
            goals.append(Goal("flee", flee, 0.8 * threat + 0.1))
    if friends:
        fpos, fcnt = min(friends.items(), key=lambda f: cheb(pos, f[0]))
        d = cheb(pos, fpos)
        urgency = 1.5 if threat_cells else (0.6 if not goals else 0.25)
        goals.append(Goal("merge", fpos, urgency * fcnt * GAMMA ** d * 0.5))
    if (behind or cfg.gamble == "always") and cfg.gamble != "never":
        for ep, e in enemies.items():
            if cheb(pos, ep) == 1 and count < 1.5 * e:
                p = win_probability(count, e, False)
                # striking first at >= 30% can beat waiting to be struck: let the search judge
                if p >= cfg.gamble_p:
                    goals.append(Goal("gamble", ep, max(0.05, p * e - (1 - p) * count)))
        for hp, h in state.humans.items():
            if cheb(pos, hp) == 1 and count < h:
                p = win_probability(count, h, True)
                if p >= cfg.gamble_p:
                    goals.append(Goal("gamble", hp, p * p * (count + h) - count))
    if not goals or all(g.value <= 0.05 for g in goals):
        # nothing to do: walk towards the closest enemy we are not afraid of, or the centre
        target = None
        if enemies:
            safe = [(ep, e) for ep, e in enemies.items() if e < count]
            pool = safe or list(enemies.items())
            ep, _ = min(pool, key=lambda g: cheb(pos, g[0]))
            target = ep if safe else None
        if target is None:
            target = (state.cols // 2, state.rows // 2)
        goals.append(Goal("approach", target, 0.01))
    if committed is not None:
        for g in goals:
            if g.target == committed and g.kind in ("house", "kill", "merge"):
                g.value *= 1.0 + cfg.commit_bonus
    goals.sort(key=lambda g: -g.value)
    return goals


# ---------------------------------------------------------------------------- plans

class _Builder:
    """Turns a set of orders (src, count, goal) into a legal list of moves."""

    def __init__(self, state: State, side: int, enemies: Dict[Pos, int], cfg: PlanConfig):
        """One builder per generate_plans call: its caches are only valid for this state."""
        self.state = state
        self.side = side
        self.enemies = enemies
        self.cfg = cfg
        self.step_cache: dict = {}      # (src, count, target, sources, gamble) -> step
        self.loss_cache: dict = {}      # (cell, count) -> expected loss if attacked there

    def build(self, orders: Sequence[Tuple[Pos, int, Goal]]):
        """-> (moves, intents). Orders whose goal is their own cell mean 'stay'."""
        orders = [o for o in orders if o[1] > 0 and o[2].target != o[0]]
        sources = {o[0] for o in orders}
        moves: Dict[Tuple[Pos, Pos], int] = {}
        intents = []
        for src, count, goal in orders:
            direct = goal.kind in ("gamble", "pincer")
            if direct and cheb(src, goal.target) == 1 and goal.target not in sources:
                dst = goal.target
            else:
                key = (src, count, goal.target, frozenset(sources), goal.kind == "gamble")
                dst = self.step_cache.get(key, 0)
                if dst == 0:
                    dst = self.step_cache[key] = safe_step(
                        self.state, self.side, src, count, goal.target, sources, self.enemies,
                        self.cfg.danger_weight, intend_battle=goal.kind == "gamble",
                        loss_cache=self.loss_cache, strike_p=self.cfg.danger_strike_p)
            if dst is None:
                continue
            moves[(src, dst)] = moves.get((src, dst), 0) + count
            if goal.kind in ("house", "kill", "merge", "pincer") and dst != goal.target:
                intents.append((dst, goal.target))
        out = tuple(sorted((s[0], s[1], n, d[0], d[1]) for (s, d), n in moves.items()))
        return out, tuple(intents)


def _orders_value(orders) -> float:
    """Prior score of a plan = sum of the values of the goals its orders pursue."""
    return sum(g.value for _, _, g in orders)


def generate_plans(state: State, side: int, cfg: Optional[PlanConfig] = None,
                   behind: bool = False, intents: Optional[Dict[Pos, Pos]] = None) -> List[Plan]:
    """
    The short list of joint plans for `side` to move. Never empty while `side` has creatures.
    `intents` = {group cell: goal} chosen last turn (commitment, see PlanConfig.commit_bonus).
    """
    intents = intents or {}
    cfg = cfg or PlanConfig()
    mine = state.groups[side]
    if not mine:
        return []
    enemies = state.groups[1 - side]
    groups = sorted(mine.items(), key=lambda g: (-g[1], g[0]))
    builder = _Builder(state, side, enemies, cfg)

    goals_of: Dict[Pos, List[Goal]] = {}
    for pos, cnt in groups:
        friends = {p: c for p, c in mine.items() if p != pos}
        goals_of[pos] = candidate_goals(state, pos, cnt, friends, enemies, cfg, behind,
                                        committed=intents.get(pos))

    plans: List[Plan] = []
    seen: Set[Tuple[Move, ...]] = set()

    def add(orders, tag: str, bonus: float = 0.0):
        moves, plan_intents = builder.build(orders)
        if not moves or moves in seen:
            return
        ok, _ = check_moves(state.rows, state.cols, mine, moves)
        if not ok:
            return
        seen.add(moves)
        plans.append(Plan(moves, _orders_value(orders) + bonus, tag, plan_intents))

    def assign(exclude: Set[Pos], fixed: Dict[Pos, Goal]):
        """Greedy: biggest group first, each takes its best goal not taken by someone else."""
        orders = []
        taken = set(exclude)
        # fixed goals reserve their target first, so nobody else walks to the same house/enemy
        taken |= {g.target for g in fixed.values() if g.kind in ("house", "kill")}
        for pos, cnt in groups:
            if pos in fixed:
                g = fixed[pos]
            else:
                g = next((g for g in goals_of[pos]
                          if g.kind not in ("house", "kill") or g.target not in taken), None)
            if g is None:
                continue
            if g.kind in ("house", "kill"):
                taken.add(g.target)
            orders.append((pos, cnt, g))
        return orders, taken

    # 1. base plan + one-group variants
    base, _ = assign(set(), {})
    add(base, "base")
    for pos, cnt in groups[:cfg.alt_groups]:
        for g in goals_of[pos][1:4]:
            orders, _ = assign(set(), {pos: g})
            add(orders, f"alt:{g.kind}")

    # 2. split plans
    if cfg.splits:
        for pos, cnt in groups[:cfg.split_groups]:
            for orders, tag, bonus in _split_orders(state, side, pos, cnt, enemies, cfg, assign):
                add(orders, tag, bonus)

    # 3. regroup on the biggest group
    if len(groups) > 1:
        big = groups[0][0]
        orders = [(pos, cnt, Goal("merge", big, 0.2)) for pos, cnt in groups[1:]]
        add(orders, "regroup")
        # the biggest also moves towards its best goal while the others come
        orders.append((big, groups[0][1], goals_of[big][0]))
        add(orders, "regroup+go")

    # 3b. pincer: several groups converge on a house none of them can take alone and enter it
    #     on the SAME turn (the server sums the arrivals, so the conversion is certain)
    if cfg.pincer and len(groups) > 1:
        for orders, tag in _pincer_orders(state, groups, enemies):
            add(orders, tag, 0.2)

    # 4. hunt: everybody that can kill an enemy group goes for it
    hunt_fixed = {}
    for pos, cnt in groups:
        kills = [g for g in goals_of[pos] if g.kind == "kill"
                 and (not cfg.bait_check or bait_factor(g.target, cnt, enemies) >= 0.5)]
        if kills:
            hunt_fixed[pos] = kills[0]
    if hunt_fixed:
        orders, _ = assign(set(), hunt_fixed)
        add(orders, "hunt", cfg.hunt_bonus)

    # 5. flee: threatened groups run, others play the base plan
    flee_fixed = {pos: next(g for g in goals_of[pos] if g.kind == "flee")
                  for pos, _ in groups if any(g.kind == "flee" for g in goals_of[pos])}
    if flee_fixed:
        orders, _ = assign(set(), flee_fixed)
        add(orders, "flee", sum(g.value for g in flee_fixed.values()))

    # 6. gambles (only generated when allowed)
    for pos, cnt in groups[:3]:
        for g in goals_of[pos]:
            if g.kind == "gamble":
                orders, _ = assign(set(), {pos: g})
                add(orders, "gamble")

    # 6b. first strikes (strike_p option): next to an enemy we beat with good but uncertain odds,
    #     striking first can beat waiting to be struck; the base plan is unchanged, the search judges
    gambles_on = (behind or cfg.gamble == "always") and cfg.gamble != "never"
    if cfg.strike_p > 0.0 and not gambles_on:
        for pos, cnt in groups[:3]:
            for ep, e in enemies.items():
                if cheb(pos, ep) == 1 and cnt < 1.5 * e:
                    p = win_probability(cnt, e, False)
                    if p >= cfg.strike_p:
                        orders, _ = assign(set(), {pos: Goal("gamble", ep, max(0.05, p * e - (1 - p) * cnt))})
                        add(orders, "strike")

    if not plans:
        plans.append(fallback_plan(state, side))
    plans.sort(key=lambda p: -p.prior)
    # strategic alternatives are never truncated away (a lost game taught us: with 6+ groups the
    # many split/alt variants used to push the only "flee" plan out of the list)
    protected = [p for p in plans if p.tag in PROTECTED or p.tag.startswith("pincer")]
    others = [p for p in plans if p not in protected]
    keep = protected + others[:max(0, cfg.max_plans - len(protected))]
    keep.sort(key=lambda p: -p.prior)
    return keep


def _split_orders(state, side, pos, cnt, enemies, cfg, assign):
    """Yield (orders, tag, bonus) for plans where the group at `pos` sends detachments."""
    if cnt < 2:
        return
    # main body reserve: stay bigger than nearby enemy groups
    reserve = 0
    for ep, e in enemies.items():
        if cheb(ep, pos) <= cfg.reserve_radius:
            reserve = max(reserve, int(cfg.reserve_ratio * e) + 1)
    options = []
    for hp, h in state.humans.items():
        if h > cnt - reserve or h <= 0:
            continue
        d = cheb(pos, hp)
        if not race_won(d, hp, h, enemies):
            continue
        k = h
        if not detachment_safe(pos, k, hp, h, enemies, cfg.safety_margin):
            # try with a bigger detachment (enough to deter attackers on the way)
            k = None
            for extra in (1, 2, h):
                kk = h + extra
                if kk <= cnt - reserve and detachment_safe(pos, kk, hp, h, enemies, cfg.safety_margin):
                    k = kk
                    break
            if k is None:
                continue
        options.append((h * GAMMA ** d / k, hp, h, k, d))
    if not options:
        return
    options.sort(key=lambda o: -o[0])
    options = options[:5]

    combos = []
    for i in range(len(options)):
        combos.append([options[i]])
    for i in range(len(options)):
        for j in range(i + 1, len(options)):
            combos.append([options[i], options[j]])
    if len(options) >= 3:
        combos.append(options[:3])
    if len(options) >= 4 and cfg.max_detachments >= 4:
        combos.append(options[:4])
    out = []
    for combo in combos:
        if len(combo) > cfg.max_detachments:
            continue
        used = sum(o[3] for o in combo)
        rest = cnt - used
        if rest < reserve or rest < 0:
            continue
        targets = {o[1] for o in combo}
        orders = [(pos, o[3], Goal("house", o[1], o[2] * GAMMA ** o[4], o[2])) for o in combo]
        fixed_rest = None
        if rest > 0:
            friends = {p: c for p, c in state.groups[side].items() if p != pos}
            main_goals = candidate_goals(state, pos, rest, friends, enemies, cfg, False, targets)
            fixed_rest = main_goals[0] if main_goals else None
        # other groups: greedy assignment, avoiding the detachments' houses
        others, _ = assign(targets, {})
        others = [o for o in others if o[0] != pos]
        value_bonus = 0.15 * len(combo)
        if fixed_rest is not None and fixed_rest.kind not in ("approach",):
            out.append((orders + [(pos, rest, fixed_rest)] + others, f"split{len(combo)}+go", value_bonus))
        out.append((orders + others, f"split{len(combo)}", value_bonus))
    yield from out


def _pincer_orders(state: State, groups, enemies):
    """Yield (orders, tag) converging groups on the best house that only their sum can convert."""
    biggest = groups[0][1]
    total = sum(c for _, c in groups)
    best = None
    for hp, h in state.humans.items():
        if biggest < h <= total:
            # closest groups first until their sum reaches h
            near = sorted(groups, key=lambda g: cheb(g[0], hp))
            team, acc = [], 0
            for g in near:
                team.append(g)
                acc += g[1]
                if acc >= h:
                    break
            if acc < h:
                continue
            d = max(cheb(p, hp) for p, _ in team)
            if not race_won(d, hp, h, enemies):
                continue
            v = h * GAMMA ** d
            if best is None or v > best[0]:
                best = (v, hp, h, team, d)
    if best is None:
        return
    v, hp, h, team, d = best
    if all(cheb(p, hp) == 1 for p, _ in team):
        # everybody is adjacent: enter together now (arrivals are summed by the server)
        yield [(p, c, Goal("pincer", hp, v, h)) for p, c in team], "pincer-go"
        return
    orders = []
    for p, c in team:
        if cheb(p, hp) > 1:
            orders.append((p, c, Goal("house", hp, v / len(team), h)))   # safe_step stops next to it
    if orders:
        yield orders, "pincer-gather"


def fallback_plan(state: State, side: int) -> Plan:
    """A plain legal move: the biggest group steps to its least dangerous empty/friendly neighbour."""
    mine = state.groups[side]
    enemies = state.groups[1 - side]
    pos, cnt = max(mine.items(), key=lambda g: (g[1], g[0]))
    best, best_key = None, None
    for n in state.nbrs[pos]:
        e = enemies.get(n, 0)
        h = state.humans.get(n, 0)
        blocked = (e and cnt < 1.5 * e) or (h and cnt < h)
        if mine.get(n, 0) + cnt > MAX_CELL:
            blocked = True
        key = (blocked, enemy_attack_loss(n, cnt, enemies), n)
        if best_key is None or key < best_key:
            best, best_key = n, key
    if best is None:                       # only possible on a 1x1 board (no neighbour at all)
        raise ValueError("no cell to move to")
    return Plan(((pos[0], pos[1], cnt, best[0], best[1]),), 0.0, "fallback")


def quick_plan(state: State, side: int) -> Tuple[Move, ...]:
    """Cheap greedy policy for rollouts: take what is adjacent, else walk to the best target."""
    mine = state.groups[side]
    if not mine:
        return ()
    enemies = state.groups[1 - side]
    humans = state.humans
    sources = set(mine)
    moves = []
    taken: Set[Pos] = set()
    for pos, cnt in sorted(mine.items(), key=lambda g: -g[1]):
        best, best_v = None, 0.0
        for hp, h in humans.items():
            if cnt >= h and hp not in taken:
                v = h * GAMMA ** cheb(pos, hp)
                if v > best_v:
                    best, best_v = hp, v
        for ep, e in enemies.items():
            if cnt >= 1.5 * e and ep not in taken:
                v = 1.3 * e * GAMMA ** max(cheb(pos, ep) - 1, 0)
                if v > best_v:
                    best, best_v = ep, v
        if best is None:
            continue
        taken.add(best)
        dst = safe_step(state, side, pos, cnt, best, sources, enemies, 3.0)
        if dst is not None:
            moves.append((pos[0], pos[1], cnt, dst[0], dst[1]))
    if not moves:
        return fallback_plan(state, side).moves
    merged: Dict[Tuple[int, int, int, int], int] = {}
    for x1, y1, n, x2, y2 in moves:
        merged[(x1, y1, x2, y2)] = merged.get((x1, y1, x2, y2), 0) + n
    return tuple((k[0], k[1], n, k[2], k[3]) for k, n in merged.items())


# ---------------------------------------------------------------------------- Splitter-R (campaign 3)
# RaceMCTS's ideas (Ronita's mcts_agent.py), re-implemented on our exact rules: its cheap goal
# scoring and step, used for long stochastic rollouts and as extra (aggressive) root plans.

def _race_goals(state: State, pos: Pos, cnt: int, mine: Dict[Pos, int],
                enemies: Dict[Pos, int]) -> List[Tuple[float, Pos]]:
    """RaceMCTS's goal list for one group, best first: convert, sure kill, regroup, flee, chase."""
    goals: List[Tuple[float, Pos]] = []
    for hp, h in state.humans.items():
        if cnt >= h:
            goals.append((h / (cheb(pos, hp) + 0.5), hp))
    for ep, e in enemies.items():
        if cnt >= 1.5 * e:
            goals.append((1.2 * e / (cheb(pos, ep) + 0.5), ep))
    friends = [(p, c) for p, c in mine.items() if p != pos]
    if friends:
        fpos, fcnt = min(friends, key=lambda f: cheb(pos, f[0]))
        goals.append((0.3 * fcnt / (cheb(pos, fpos) + 0.5), fpos))
    danger = [ep for ep, e in enemies.items() if e >= 1.5 * cnt and cheb(pos, ep) <= 3]
    if danger:
        flee = max(state.nbrs[pos], key=lambda n: min(cheb(n, ep) for ep in danger))
        goals.append((0.5 * cnt, flee))
    if not goals and enemies:
        goals.append((0.01, min(enemies, key=lambda ep: cheb(pos, ep))))
    if not goals:
        goals.append((0.0, (state.cols // 2, state.rows // 2)))
    goals.sort(key=lambda g: -g[0])
    return goals


def _race_step(state: State, side: int, src: Pos, cnt: int, goal: Pos, forbidden: Set[Pos],
               enemies: Dict[Pos, int]) -> Optional[Pos]:
    """One step towards goal: least danger from sure-killers, then closest; never into a fight we cannot win for sure."""
    best, best_key = None, None
    for n in state.nbrs[src]:
        if n in forbidden:
            continue
        e = enemies.get(n, 0)
        if e and cnt < 1.5 * e:
            continue
        h = state.humans.get(n, 0)
        if h and cnt < h:
            continue
        if state.groups[side].get(n, 0) + cnt > MAX_CELL:
            continue
        danger = 0
        if n != goal:
            for tp, te in enemies.items():
                if te >= 1.5 * cnt and cheb(n, tp) <= 1:
                    danger += te
        key = (danger, cheb(n, goal), abs(n[0] - goal[0]) + abs(n[1] - goal[1]))
        if best_key is None or key < best_key:
            best, best_key = n, key
    return best


def race_rollout_plan(state: State, side: int, rng, eps: float = 0.15, strike_p: float = 0.0) -> Tuple[Move, ...]:
    """
    Splitter-R rollout policy (RaceMCTS's, on our rules): every group takes its best goal, its
    second with probability eps; with strike_p > 0 a group adjacent to an enemy it beats with
    at least that probability strikes first (the tactic RaceMCTS wins games with).
    """
    # Same moves as _race_goals + _race_step (checked on 1,896 positions), 33% faster: only the
    # best two goals are kept (ties: first listed wins, like the stable sort), distances inlined,
    # and the sure-killers listed once per group instead of once per neighbour.
    mine = state.groups[side]
    if not mine:
        return ()
    enemies = state.groups[1 - side]
    humans = state.humans
    moves: Dict[Tuple[Pos, Pos], int] = {}
    for pos, cnt in sorted(mine.items(), key=lambda g: -g[1]):
        px, py = pos
        dst = None
        if strike_p > 0.0:
            best = None
            for ep, e in enemies.items():
                if cnt < 1.5 * e and max(abs(ep[0] - px), abs(ep[1] - py)) == 1:
                    p = win_probability(cnt, e, False)
                    if p >= strike_p and (best is None or p * e > best[0]):
                        best = (p * e, ep)
            if best is not None:
                dst = best[1]
        if dst is None:
            top = [None, None, None, None]          # best value, its cell, second value, its cell
            for hp, h in humans.items():
                if cnt >= h:
                    _offer(top, h / (max(abs(hp[0] - px), abs(hp[1] - py)) + 0.5), hp)
            killers = []
            for ep, e in enemies.items():
                d = max(abs(ep[0] - px), abs(ep[1] - py))
                if cnt >= 1.5 * e:
                    _offer(top, 1.2 * e / (d + 0.5), ep)
                if e >= 1.5 * cnt:
                    killers.append((ep, e, d))
            fpos, fd, fcnt = None, 0, 0
            for p, c in mine.items():
                if p != pos:
                    d = max(abs(p[0] - px), abs(p[1] - py))
                    if fpos is None or d < fd:
                        fpos, fd, fcnt = p, d, c
            if fpos is not None:
                _offer(top, 0.3 * fcnt / (fd + 0.5), fpos)
            danger = [k[0] for k in killers if k[2] <= 3]
            if danger:
                _offer(top, 0.5 * cnt, max(state.nbrs[pos], key=lambda n: min(cheb(n, q) for q in danger)))
            goal = top[1]
            if goal is None:
                goal = (min(enemies, key=lambda q: cheb(pos, q)) if enemies
                        else (state.cols // 2, state.rows // 2))
            elif top[3] is not None and rng.random() < eps:
                goal = top[3]
            dst = _race_step_fast(state, pos, cnt, goal, mine, enemies, killers)
        if dst is not None:
            moves[(pos, dst)] = moves.get((pos, dst), 0) + cnt
    out = tuple((s[0], s[1], n, d[0], d[1]) for (s, d), n in moves.items()
                if mine.get(d, 0) + n <= MAX_CELL)
    return out or fallback_plan(state, side).moves


def _offer(top: list, v: float, cell: Pos):
    """Keep the best two (value, cell) in top = [v1, cell1, v2, cell2]; a tie keeps the earlier one."""
    if top[0] is None or v > top[0]:
        top[2], top[3], top[0], top[1] = top[0], top[1], v, cell
    elif top[2] is None or v > top[2]:
        top[2], top[3] = v, cell


def _race_step_fast(state: State, src: Pos, cnt: int, goal: Pos, mine: Dict[Pos, int],
                    enemies: Dict[Pos, int], killers: List[Tuple[Pos, int, int]]) -> Optional[Pos]:
    """_race_step for rollouts: our own cells are the forbidden sources, `killers` = enemies >= 1.5 cnt."""
    best, best_key = None, None
    gx, gy = goal
    humans = state.humans
    for n in state.nbrs[src]:
        if n in mine or cnt > MAX_CELL:
            continue
        e = enemies.get(n, 0)
        if e and cnt < 1.5 * e:
            continue
        h = humans.get(n, 0)
        if h and cnt < h:
            continue
        danger = 0
        if n != goal:
            for tp, te, _ in killers:
                if max(abs(n[0] - tp[0]), abs(n[1] - tp[1])) <= 1:
                    danger += te
        dx, dy = abs(n[0] - gx), abs(n[1] - gy)
        key = (danger, max(dx, dy), dx + dy)
        if best_key is None or key < best_key:
            best, best_key = n, key
    return best


def race_plans(state: State, side: int, max_plans: int = 6) -> List[Plan]:
    """
    Splitter-R root plans (RaceMCTS's plan families, on our rules): every group to its best goal,
    whole-group splits to two houses, regroup on the biggest, one group on its second goal.
    No safety checks on purpose: they are the aggressive options our search then judges.
    """
    mine = state.groups[side]
    if not mine:
        return []
    enemies = state.groups[1 - side]
    groups = sorted(mine.items(), key=lambda g: (-g[1], g[0]))
    goals = {pos: _race_goals(state, pos, cnt, mine, enemies)[:3] for pos, cnt in groups}
    plans: List[Plan] = []
    seen: Set[Tuple[Move, ...]] = set()

    def turn(choice: Dict[Pos, Pos], skip: Set[Pos], forbidden: Set[Pos]) -> List[Move]:
        out = []
        for pos, cnt in groups:
            if pos in skip or pos not in choice:
                continue
            dst = _race_step(state, side, pos, cnt, choice[pos], forbidden, enemies)
            if dst is not None:
                out.append((pos[0], pos[1], cnt, dst[0], dst[1]))
        return out

    def add(moves: List[Move], tag: str):
        key = tuple(sorted(moves))
        if moves and key not in seen and check_moves(state.rows, state.cols, mine, key)[0]:
            seen.add(key)
            plans.append(Plan(key, 0.0, tag))

    sources = set(mine)
    default = {pos: g[0][1] for pos, g in goals.items()}
    add(turn(default, set(), sources), "race:base")
    humans = list(state.humans.items())
    for pos, cnt in groups[:2]:                       # whole-group splits to two houses
        options = []
        for i, (h1, c1) in enumerate(humans):
            for h2, c2 in humans[i + 1:]:
                for (ha, ca), (hb, cb) in (((h1, c1), (h2, c2)), ((h2, c2), (h1, c1))):
                    if ca <= cnt - cb and cb <= cnt - ca:
                        options.append(((ca + cb) / (cheb(pos, ha) + cheb(pos, hb) + 1.0), ha, ca, hb))
        options.sort(key=lambda o: -o[0])
        for _, ha, ca, hb in options[:2]:
            dst_a = _race_step(state, side, pos, ca, ha, sources, enemies)
            if dst_a is None:
                continue
            dst_b = _race_step(state, side, pos, cnt - ca, hb, sources | {dst_a}, enemies)
            if dst_b is None:
                continue
            rest = [m for m in turn(default, {pos}, sources) if (m[3], m[4]) not in (pos, dst_a, dst_b)]
            add([(pos[0], pos[1], ca, dst_a[0], dst_a[1]),
                 (pos[0], pos[1], cnt - ca, dst_b[0], dst_b[1])] + rest, "race:split")
    if len(groups) > 1:
        big = groups[0][0]
        add(turn({pos: big for pos, _ in groups[1:]}, {big}, sources), "race:regroup")
    for pos, g in goals.items():
        if len(g) > 1:
            choice = dict(default)
            choice[pos] = g[1][1]
            add(turn(choice, set(), sources), "race:alt")
    return plans[:max_plans]
