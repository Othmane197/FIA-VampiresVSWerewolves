"""
SplitterAgent: the bot that main.py plays (through ai_agent.AIAgent).

Interfaces (so every teammate's tool can run it):
    compute_moves(game_state)                 -> moves     (repo / main.py / Dana's selfplay)
    compute_moves_board(board, species)       -> moves     (Othmane's / Ronita's arenas)
    choose(state, side, ply=None)             -> moves     (our arena, fastest)

Safety net (a failure on tournament day caps the grade at 10/20):
    * the search runs under a strict time budget (default 1.5 s for a 2 s server limit);
    * any exception falls back to the planner's best plan, then to a plain one-step move;
    * the final move list is ALWAYS checked with rules.check_moves (the server's cheating rules).

The two kept models (MODELS below; docs/strategy/16_splitter_r.md explains the choice):
    flagship   "Splitter"          SplitterAgent(**MODELS["flagship"]): "Splitter-R3", RaceMCTS-style
               rollouts and root plans + first strikes + the desperate-opponent model
               (what main.py plays by default)
    backup     "Splitter-Classic"  SplitterAgent() with all defaults: the campaign-2 flagship
               (main.py plays it with SPLITTER_MODEL=backup)
Other keyword arguments are tuning knobs (docs/strategy/10_parameters.md); any PlanConfig field
can also be passed (e.g. danger_strike_p=0.3), and evaluation constants as eval_<name>.
"""
import random
import time
from dataclasses import replace
from typing import List, Optional, Tuple

from .evaluate import EvalParams, evaluate, material_balance
from .mcts import MCTS
from .planner import PlanConfig, fallback_plan, generate_plans, race_plans
from .rules import V, W, check_moves
from .state import State, side_of_species

Move = Tuple[int, int, int, int, int]

# The only two configurations kept after campaign 3 (chapter 16.9)
MODELS = {
    # "Splitter-R3": the campaign-2 flagship merged with RaceMCTS's long dice-driven rollouts and
    # root plans, the anti-bait kill check, good-odds first strikes and the desperate-opponent
    # model; won the pre-registered final on fresh maps (+8.0 +- 3.9 over the campaign-2 flagship)
    "flagship": {"rollout_policy": "race", "rollout_strike": 0.45, "rollout_depth_contact": 6, "leaf_mix": 0.5,
                 "race_root": True, "bait_check": True, "strike_p": 0.6, "desperate_p": 0.1},
    # the campaign-2 flagship (all defaults, = the frozen v7): the most tested model, and it loses
    # differently (more draws, far fewer wipeouts), so it is a real fallback
    "backup": {},
}


class SplitterAgent:
    """The tournament bot: planner + MCTS under a strict time budget, with a legal-move guarantee."""

    def __init__(self, name: str = "Splitter", time_limit: float = 1.5, splits: bool = True,
                 search: str = "mcts", gamble: str = "adaptive", c: float = 0.6,
                 rollout_depth: int = 2, prior_bias: float = 0.6, widen_k: float = 2.0,
                 safety_margin: int = 1, max_detachments: int = 3, reserve_ratio: float = 1.0,
                 reserve_radius: int = 6, max_ply: int = 200, game_seconds: Optional[float] = 300.0,
                 rollout_policy: str = "quick", rollout_strike: float = 0.0, rollout_depth_contact: int = 0,
                 leaf_mix: float = 1.0, race_root: bool = False, desperate_p: float = 0.0,
                 keep_away: bool = False, race_root_safe: bool = False,
                 seed: Optional[int] = None, verbose: bool = False, **extra):
        """Build the plan config (variants via keyword arguments), the evaluation and the MCTS engine."""
        self.name = name
        self.time_limit = time_limit
        self.search_mode = search
        self.max_ply = max_ply
        self.game_seconds = game_seconds
        self.verbose = verbose
        self.cfg = PlanConfig(splits=splits, gamble=gamble, safety_margin=safety_margin,
                              max_detachments=max_detachments, reserve_ratio=reserve_ratio,
                              reserve_radius=reserve_radius)
        ev = {}
        for k, v in extra.items():
            if k.startswith("eval_") and k[5:] in EvalParams.__dataclass_fields__:
                ev[k[5:]] = float(v)           # evaluation constant, e.g. eval_discount=0.845
            elif hasattr(self.cfg, k):
                setattr(self.cfg, k, v)        # any other PlanConfig field, e.g. danger_strike_p=0.3
            else:
                raise TypeError(f"unknown Splitter option {k!r}")
        self.ev = EvalParams(**ev)
        self.race_root = race_root             # RaceMCTS-style plans added at the root (the flagship)
        self.race_root_safe = race_root_safe   # ... whose steps avoid enemies as big as the group, when not behind
        self.desperate_p = desperate_p         # > 0: a losing opponent is expected to strike from these odds
        self.keep_away = keep_away             # ... and then, with no humans left, we never step into its reach
        self.mcts = MCTS(self.cfg, c=c, rollout_depth=rollout_depth, prior_bias=prior_bias,
                         widen_k=widen_k, rng=random.Random(seed), ev=self.ev,
                         rollout_policy=rollout_policy, rollout_strike=rollout_strike,
                         rollout_depth_contact=rollout_depth_contact, leaf_mix=leaf_mix)
        self.last_error: Optional[str] = None
        self.last_info: dict = {}
        self.reset()

    def reset(self):
        """Call between games (main.py does it on END)."""
        self.turns = 0
        self.first_call: Optional[float] = None
        self.intents = {}                      # {cell: goal} of the plan we played last turn
        self._deciding = None                  # (state, side) while a decision is in progress
        self._top_plan = None                  # the planner's top plan for that decision

    # ------------------------------------------------------------------ interfaces
    def compute_moves(self, game_state) -> List[Move]:
        """main.py interface: moves for the GameState kept from the server messages."""
        start = time.perf_counter()
        if self.first_call is None:
            self.first_call = start
        side = side_of_species(game_state.our_species) if game_state.our_species else None
        state = State.from_game_state(game_state, max_ply=self.max_ply)
        if side is None:                       # species unknown: whoever owns the home cell
            home = getattr(game_state, "home", None)
            side = V if home in state.groups[V] else W
        # we do not get the ply from the server: estimate it from our own turn counter
        ply = 2 * self.turns
        self.turns += 1
        return self._safe_choose(state, side, ply, start)

    def compute_moves_board(self, board, species) -> List[Move]:
        """Othmane's / Ronita's interface: moves for a BoardState and a Species."""
        start = time.perf_counter()
        state = State.from_board(board)
        self.turns += 1
        return self._safe_choose(state, side_of_species(species), state.ply, start)

    def choose(self, state: State, side: int, ply: Optional[int] = None) -> List[Move]:
        """Arena interface: moves for a splitter State (fastest, true ply known)."""
        start = time.perf_counter()
        if self.first_call is None:
            self.first_call = start
        self.turns += 1
        return self._safe_choose(state, side, state.ply if ply is None else ply, start)

    def anytime_moves(self) -> Optional[List[Move]]:
        """
        main.py's watchdog, when the decision in progress is late: the search's best plan so far
        (or the planner's top plan before the search starts), if it is legal; else None.
        Called from another thread: it only reads references set by the deciding thread.
        """
        deciding = self._deciding
        if deciding is None:
            return None
        state, side = deciding
        plan = self.mcts.best_so_far or self._top_plan
        if plan is None or not check_moves(state.rows, state.cols, state.groups[side], plan.moves)[0]:
            return None
        return [(int(a), int(b), int(c), int(d), int(e)) for a, b, c, d, e in plan.moves]

    # ------------------------------------------------------------------ core
    def _remaining_plies(self, ply: int, now: float) -> float:
        """Plies left, from the ply cap and from the game clock (whichever ends first)."""
        remaining = self.max_ply - ply
        if self.game_seconds and self.first_call is not None and ply >= 10:
            elapsed = now - self.first_call
            per_ply = elapsed / ply
            if per_ply > 0:
                remaining = min(remaining, (self.game_seconds - elapsed) / per_ply)
        return max(1.0, remaining)

    def _safe_choose(self, state: State, side: int, ply: int, start: float) -> List[Move]:
        """Never-fail wrapper: search, then validate, then fallbacks; always returns legal moves."""
        state.ply = ply
        mine = state.groups[side]
        if not mine:
            return []
        self.mcts.best_so_far = self._top_plan = None
        self._deciding = (state, side)
        try:
            return self._decide(state, side, ply, start)
        finally:
            self._deciding = None

    def _decide(self, state: State, side: int, ply: int, start: float) -> List[Move]:
        """_safe_choose's body: search, then validate, then the fallbacks."""
        mine = state.groups[side]
        moves = None
        try:
            moves = self._choose(state, side, ply, start)
        except Exception as e:                       # never let a bug drop the connection
            self.last_error = repr(e)
            if self.verbose:
                import traceback
                traceback.print_exc()
        if moves:
            ok, why = check_moves(state.rows, state.cols, mine, moves)
            if not ok:
                self.last_error = f"illegal plan rejected: {why} {moves}"
                moves = None
        if not moves:
            try:
                moves = list(fallback_plan(state, side).moves)
            except Exception as e:
                self.last_error = f"{self.last_error} / fallback: {e!r}"
                moves = _emergency_move(state, side)
        return [(int(a), int(b), int(c), int(d), int(e)) for a, b, c, d, e in moves]

    def _choose(self, state: State, side: int, ply: int, start: float) -> List[Move]:
        """Decide: evaluate, generate plans (with last turn's intents), search, remember intents."""
        remaining = self._remaining_plies(ply, start)
        value_now = evaluate(state, side, side, remaining, ev=self.ev)
        behind = value_now < 0.35 or (remaining < 20 and material_balance(state, side) < 0)
        cfg, opp_gamble_p = self.cfg, None
        if self.desperate_p > 0.0 and (value_now >= 0.65 or (remaining < 20 and material_balance(state, side) > 0)):
            # the opponent is losing: like us when behind, it gambles, and from low odds (a lost
            # strike costs it nothing, a won one can wipe out our lead): stay out of its reach
            opp_gamble_p = self.desperate_p
            cfg = replace(self.cfg, danger_strike_p=min(self.cfg.danger_strike_p, self.desperate_p),
                          threat_p=min(self.cfg.threat_p, self.desperate_p),
                          keep_away_p=self.desperate_p if self.keep_away else 0.0)
        # keep only intents of groups that still exist where we left them
        intents = {p: t for p, t in self.intents.items() if p in state.groups[side]}
        plans = generate_plans(state, side, cfg, behind=behind, intents=intents)
        if not plans:
            return []
        self._top_plan = plans[0]
        if self.race_root:                     # aggressive whole-group options; the search judges them
            seen = {p.moves for p in plans}
            half = 0.5 * (max(p.prior for p in plans) or 1.0)
            for p in race_plans(state, side, safe=self.race_root_safe and not behind):
                if p.moves not in seen:
                    p.prior = half
                    plans.append(p)
        if self.search_mode == "greedy" or len(plans) == 1:
            best = plans[0]
            self.intents = dict(best.intents)
            self.last_info = {"mode": "greedy", "plans": len(plans), "tag": best.tag}
            return list(best.moves)
        budget = self.time_limit - (time.perf_counter() - start) - 0.02
        if budget <= 0.01:
            self.intents = dict(plans[0].intents)
            return list(plans[0].moves)
        top = max(p.prior for p in plans) or 1.0
        for p in plans:
            p.prior = max(0.0, p.prior / top) if top > 0 else 0.0
        best = self.mcts.search(state, side, budget, remaining, behind, root_plans=list(plans),
                                cfg_us=cfg, opp_gamble_p=opp_gamble_p) or plans[0]
        self.last_info = {"mode": "mcts", "plans": len(plans), "iterations": self.mcts.iterations,
                          "tag": best.tag, "value": value_now, "behind": behind,
                          "opp_desperate": opp_gamble_p is not None}
        if self.verbose:
            print(f"[{self.name}] ply {ply} value {value_now:.2f} iters {self.mcts.iterations} "
                  f"-> {best.tag} {best.moves}")
            for row in self.mcts.root_stats()[:5]:
                print(f"     {row[0]:5d} visits  {row[1]:.3f}  {row[2]:12s} {row[3]}")
        self.intents = dict(best.intents)
        return list(best.moves)


def _emergency_move(state: State, side: int) -> List[Move]:
    """Last resort: any legal one-step move of the biggest group to a non-hostile cell."""
    mine = state.groups[side]
    pos, cnt = max(mine.items(), key=lambda g: g[1])
    for n in state.nbrs[pos]:
        if n not in state.humans and n not in state.groups[1 - side]:
            return [(pos[0], pos[1], cnt, n[0], n[1])]
    n = state.nbrs[pos][0]
    return [(pos[0], pos[1], cnt, n[0], n[1])]
