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

Variants (for testing ideas against each other), all keyword arguments:
    splits=True/False         detachments on/off ("deathball" ablation)
    search="mcts"/"greedy"    tree search, or just play the planner's top plan
    gamble="adaptive"/"never"/"always"
    c, rollout_depth, safety_margin, max_detachments, reserve_ratio
"""
import random
import time
from typing import List, Optional, Tuple

from .evaluate import evaluate, material_balance
from .mcts import MCTS
from .planner import PlanConfig, fallback_plan, generate_plans
from .rules import V, W, check_moves
from .state import State, side_of_species

Move = Tuple[int, int, int, int, int]


class SplitterAgent:
    def __init__(self, name: str = "Splitter", time_limit: float = 1.5, splits: bool = True,
                 search: str = "mcts", gamble: str = "adaptive", c: float = 0.6,
                 rollout_depth: int = 2, safety_margin: int = 1, max_detachments: int = 3,
                 reserve_ratio: float = 1.0, reserve_radius: int = 6, max_ply: int = 200, game_seconds: Optional[float] = 300.0,
                 seed: Optional[int] = None, verbose: bool = False, light_tree: bool = False, **extra):
        self.name = name
        self.time_limit = time_limit
        self.search_mode = search
        self.max_ply = max_ply
        self.game_seconds = game_seconds
        self.verbose = verbose
        self.cfg = PlanConfig(splits=splits, gamble=gamble, safety_margin=safety_margin,
                              max_detachments=max_detachments, reserve_ratio=reserve_ratio,
                              reserve_radius=reserve_radius)
        self.mcts = MCTS(self.cfg, c=c, rollout_depth=rollout_depth, rng=random.Random(seed),
                         light_tree=light_tree)
        self.last_error: Optional[str] = None
        self.last_info: dict = {}
        self.reset()

    def reset(self):
        """Call between games (main.py does it on END)."""
        self.turns = 0
        self.first_call: Optional[float] = None
        self.intents = {}                      # {cell: goal} of the plan we played last turn

    # ------------------------------------------------------------------ interfaces
    def compute_moves(self, game_state) -> List[Move]:
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
        start = time.perf_counter()
        state = State.from_board(board)
        self.turns += 1
        return self._safe_choose(state, side_of_species(species), state.ply, start)

    def choose(self, state: State, side: int, ply: Optional[int] = None) -> List[Move]:
        start = time.perf_counter()
        self.turns += 1
        return self._safe_choose(state, side, state.ply if ply is None else ply, start)

    # ------------------------------------------------------------------ core
    def _remaining_plies(self, ply: int, now: float) -> float:
        remaining = self.max_ply - ply
        if self.game_seconds and self.first_call is not None and ply >= 10:
            elapsed = now - self.first_call
            per_ply = elapsed / ply
            if per_ply > 0:
                remaining = min(remaining, (self.game_seconds - elapsed) / per_ply)
        return max(1.0, remaining)

    def _safe_choose(self, state: State, side: int, ply: int, start: float) -> List[Move]:
        state.ply = ply
        mine = state.groups[side]
        if not mine:
            return []
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
        return [tuple(int(v) for v in m) for m in moves]

    def _choose(self, state: State, side: int, ply: int, start: float) -> List[Move]:
        remaining = self._remaining_plies(ply, start)
        value_now = evaluate(state, side, side, remaining)
        behind = value_now < 0.35 or (remaining < 20 and material_balance(state, side) < 0)
        # keep only intents of groups that still exist where we left them
        intents = {p: t for p, t in self.intents.items() if p in state.groups[side]}
        plans = generate_plans(state, side, self.cfg, behind=behind, intents=intents)
        if not plans:
            return []
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
        best = self.mcts.search(state, side, budget, remaining, behind, root_plans=list(plans))
        self.last_info = {"mode": "mcts", "plans": len(plans), "iterations": self.mcts.iterations,
                          "tag": best.tag if best else None, "value": value_now, "behind": behind}
        if self.verbose:
            print(f"[{self.name}] ply {ply} value {value_now:.2f} iters {self.mcts.iterations} "
                  f"-> {best.tag} {best.moves}")
            for row in self.mcts.root_stats()[:5]:
                print(f"     {row[0]:5d} visits  {row[1]:.3f}  {row[2]:12s} {row[3]}")
        best = best or plans[0]
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
