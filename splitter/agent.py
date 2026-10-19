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
from dataclasses import replace
from typing import List, Optional, Tuple

from .evaluate import evaluate, material_balance
from .mcts import MCTS
from .opponent_model import OpponentModel
from .planner import PlanConfig, fallback_plan, generate_plans
from .rules import V, W, check_moves
from .state import State, side_of_species

Move = Tuple[int, int, int, int, int]


class SplitterAgent:
    """The tournament bot: planner + MCTS under a strict time budget, with a legal-move guarantee."""
    def __init__(self, name: str = "Splitter", time_limit: float = 1.5, splits: bool = True,
                 search: str = "mcts", gamble: str = "adaptive", c: float = 0.6,
                 rollout_depth: int = 2, safety_margin: int = 1, max_detachments: int = 3,
                 reserve_ratio: float = 1.0, reserve_radius: int = 6, max_ply: int = 200, game_seconds: Optional[float] = 300.0,
                 seed: Optional[int] = None, verbose: bool = False, light_tree: bool = False,
                 opponent_model: bool = False, opp_selection: str = "puct", adapt: bool = True,
                 map_aware: bool = False, first_move_time: float = 0.0, prior_bias: float = 0.6,
                 widen_k: float = 2.0, opp_priors: bool = True, opp_eval: bool = True, kite: bool = False,
                 **extra):
        """Build the plan config (variants via keyword arguments) and the MCTS engine."""
        self.name = name
        self.time_limit = time_limit
        self.search_mode = search
        self.max_ply = max_ply
        self.game_seconds = game_seconds
        self.verbose = verbose
        self.cfg = PlanConfig(splits=splits, gamble=gamble, safety_margin=safety_margin,
                              max_detachments=max_detachments, reserve_ratio=reserve_ratio,
                              reserve_radius=reserve_radius)
        for k, v in extra.items():             # any other PlanConfig field, e.g. prize_lock=True
            if hasattr(self.cfg, k):
                setattr(self.cfg, k, v)
        # opponent model (HMMs, splitter/opponent_model.py): observes the opponent every turn
        self.opp_model = OpponentModel() if opponent_model else None
        self.adapt = adapt and opponent_model         # I5: risk settings follow the opponent's style
        self.map_aware = map_aware                    # deathball on maps dominated by one prize
        self.first_move_time = first_move_time        # longer budget for our first turn (arena test of I6)
        self.pregame_cache = None                     # (board key, moves) computed by pregame()
        self.base_cfg = replace(self.cfg)
        self.mcts = MCTS(self.cfg, c=c, rollout_depth=rollout_depth, rng=random.Random(seed),
                         light_tree=light_tree, opp_model=self.opp_model, opp_selection=opp_selection,
                         prior_bias=prior_bias, widen_k=widen_k, opp_priors=opp_priors, opp_eval=opp_eval,
                         kite=kite)
        self.last_error: Optional[str] = None
        self.last_info: dict = {}
        self.reset()

    def reset(self):
        """Call between games (main.py does it on END)."""
        self.turns = 0
        self.first_call: Optional[float] = None
        self.intents = {}                      # {cell: goal} of the plan we played last turn
        self.map_checked = False
        if getattr(self, "base_cfg", None) is not None:
            self.cfg.splits = self.base_cfg.splits
        if getattr(self, "opp_model", None) is not None:
            self.opp_model.reset()

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
        self.turns += 1
        return self._safe_choose(state, side, state.ply if ply is None else ply, start)

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
        moves = None
        if self.opp_model is not None:
            try:
                self.opp_model.observe(state)      # learn from the opponent's last move
            except Exception as e:
                self.last_error = f"opponent model: {e!r}"
        try:
            cached = self.pregame_cache
            self.pregame_cache = None
            if cached is not None and cached[0] == state.key():
                moves = list(cached[1])            # I6: decided before the game started
            else:
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
        final = [(int(a), int(b), int(c), int(d), int(e)) for a, b, c, d, e in moves]
        if self.opp_model is not None:
            try:
                self.opp_model.note_our_move(state, side, final)
            except Exception as e:
                self.last_error = f"opponent model: {e!r}"
        return final

    def _choose(self, state: State, side: int, ply: int, start: float) -> List[Move]:
        """Decide: evaluate, generate plans (with last turn's intents), search, remember intents."""
        remaining = self._remaining_plies(ply, start)
        if self.map_aware and not self.map_checked:
            self.map_checked = True
            if prize_dominated(state, side):
                self.cfg.splits = False
        if self.adapt:
            self._adapt_settings(state)
        value_now = evaluate(state, side, side, remaining)
        behind = value_now < 0.35 or (remaining < 20 and material_balance(state, side) < 0)
        # keep only intents of groups that still exist where we left them
        intents = {p: t for p, t in self.intents.items() if p in state.groups[side]}
        predictions = None
        if self.opp_model is not None and self.opp_model.history:
            predictions = self.opp_model.predictions(state, side)
        plans = generate_plans(state, side, self.cfg, behind=behind, intents=intents, predictions=predictions)
        if not plans:
            return []
        if self.search_mode == "greedy" or len(plans) == 1:
            best = plans[0]
            self.intents = dict(best.intents)
            self.last_info = {"mode": "greedy", "plans": len(plans), "tag": best.tag}
            return list(best.moves)
        limit = self.time_limit
        if self.first_move_time and self.turns == 1:
            limit = max(limit, self.first_move_time)
        budget = limit - (time.perf_counter() - start) - 0.02
        if budget <= 0.01:
            self.intents = dict(plans[0].intents)
            return list(plans[0].moves)
        top = max(p.prior for p in plans) or 1.0
        for p in plans:
            p.prior = max(0.0, p.prior / top) if top > 0 else 0.0
        best = self.mcts.search(state, side, budget, remaining, behind, root_plans=list(plans)) or plans[0]
        self.last_info = {"mode": "mcts", "plans": len(plans), "iterations": self.mcts.iterations,
                          "tag": best.tag, "value": value_now, "behind": behind}
        if self.verbose:
            print(f"[{self.name}] ply {ply} value {value_now:.2f} iters {self.mcts.iterations} "
                  f"-> {best.tag} {best.moves}")
            for row in self.mcts.root_stats()[:5]:
                print(f"     {row[0]:5d} visits  {row[1]:.3f}  {row[2]:12s} {row[3]}")
        self.intents = dict(best.intents)
        return list(best.moves)


    def pregame(self, game_state, budget: float = 2.5) -> None:
        """
        I6 (flag --pregame, off by default): use the idle time between MAP and the first UPD.
        Decide the first move on the starting board with a long budget; if our first turn sees
        exactly that board (we move first) the cached move is played at once.
        """
        start = time.perf_counter()
        side = side_of_species(game_state.our_species) if game_state.our_species else V
        state = State.from_game_state(game_state, max_ply=self.max_ply)
        saved = self.time_limit
        self.time_limit = budget
        try:
            moves = self._choose(state, side, 0, start)
            if moves and check_moves(state.rows, state.cols, state.groups[side], moves)[0]:
                self.pregame_cache = (state.key(), moves)
        finally:
            self.time_limit = saved

    def _adapt_settings(self, state: State) -> None:
        """
        I5: adjust risk settings to the observed opponent (after 8 observed turns):
        passive non-gambler -> bolder splits; aggressive or long-shot gambler -> more caution;
        an opponent that splits -> hunt its splinters.
        """
        cfg, base = self.cfg, self.base_cfg
        cfg.reserve_radius, cfg.safety_margin, cfg.hunt_bonus = (base.reserve_radius, base.safety_margin,
                                                                 base.hunt_bonus)
        t = self.opp_model.tendencies(state)
        if t["turns"] < 8:
            return
        if t["aggression"] < 0.3 and t["longshot"] < 0.05:
            cfg.reserve_radius = max(3, base.reserve_radius - 2)
        elif t["aggression"] > 0.5 or t["longshot"] > 0.2:
            cfg.reserve_radius = base.reserve_radius + 1
            cfg.safety_margin = base.safety_margin + 1
        if t["split"] > 0.08:
            cfg.hunt_bonus = base.hunt_bonus + 0.3


def prize_dominated(state: State, side: int, share: float = 0.45) -> bool:
    """
    Map-aware strategy (chapter 08): when one house holds >= `share` of all humans and is bigger
    than our army, concentrating to take it beats splitting (no-split won testmap and the prize maps).
    """
    total = state.humans_total()
    if not total:
        return False
    biggest = max(state.humans.values())
    return biggest >= share * total and biggest > state.total(side)


def _emergency_move(state: State, side: int) -> List[Move]:
    """Last resort: any legal one-step move of the biggest group to a non-hostile cell."""
    mine = state.groups[side]
    pos, cnt = max(mine.items(), key=lambda g: g[1])
    for n in state.nbrs[pos]:
        if n not in state.humans and n not in state.groups[1 - side]:
            return [(pos[0], pos[1], cnt, n[0], n[1])]
    n = state.nbrs[pos][0]
    return [(pos[0], pos[1], cnt, n[0], n[1])]
