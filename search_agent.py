"""
search_agent.py  (our own file; it does not modify any shared repo file)

Depth-limited EXPECTIMINIMAX agent (version 1: plain search, no pruning yet).

Course concept: expectiminimax = minimax + CHANCE nodes whose value is the probability-weighted
average of their children (the course notes list it among the algorithms studied).
Everything else (restricted move generator, two-outcome battle model, evaluation terms,
time control) is our own design.

Tree, for depth = 2 (a "ply" = one player's whole turn):

    MAX node  (our turn)            : we pick the turn with the highest value
      CHANCE node (our battles)     : average over the possible boards of that turn
        MIN node  (enemy reply)     : the enemy picks the turn with the lowest value
          CHANCE node (its battles) : average again
            leaf                    : evaluation.evaluate(board, us)

Assumptions to remember (they are choices, not facts about the real opponent):
  * the enemy chooses among the SAME restricted list of turns that we generate for ourselves
    (move_generator.generate_turns) and plays to minimise OUR score (zero-sum);
  * battles use the two-outcome model (win / lose) from battle_model.py;
  * the board built from GameState starts at turn 0 (GameState does not track plies).

Time control: a deadline is checked at every node. If it passes, the search stops and we play
the best turn finished so far (the generator ranks turns best-first, so the first one is a
reasonable default). compute_moves never raises and never returns an illegal empty turn
unless we have no creatures at all.
"""
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from evaluation import DEFAULT_RACE_WEIGHT, evaluate
from game_engine import BoardState
from game_state import GameState, Species
from move_generator import generate_turns
from state_converter import board_from_state
from transition import turn_outcomes

Turn = List[Tuple[int, int, int, int, int]]
INF = float("inf")


class _Timeout(Exception):
    pass


def _other(species: Species) -> Species:
    return Species.WEREWOLF if species == Species.VAMPIRE else Species.VAMPIRE


@dataclass
class SearchInfo:
    depth: int = 0
    nodes: int = 0                     # max/min nodes visited
    root_turns: int = 0                # turns generated at the root
    root_turns_done: int = 0           # turns fully evaluated before the deadline
    best_value: float = 0.0
    seconds: float = 0.0
    timed_out: bool = False
    values: List[Tuple[float, Turn]] = field(default_factory=list)   # value of each finished root turn


class _Context:
    def __init__(self, root: Species, deadline: float, race_weight: float, max_chance_battles: int,
                 progress_weight: float = 0.0):
        self.root = root
        self.deadline = deadline
        self.race_weight = race_weight
        self.progress_weight = progress_weight
        self.max_chance_battles = max_chance_battles
        self.nodes = 0


def _chance_value(board: BoardState, turn: Turn, mover: Species, depth: int, ctx: _Context) -> float:
    """Average value over the boards that `mover` playing `turn` can produce."""
    total = 0.0
    for prob, child in turn_outcomes(board, turn, mover, ctx.max_chance_battles):
        total += prob * _value(child, _other(mover), depth - 1, ctx)
    return total


def _value(board: BoardState, to_move: Species, depth: int, ctx: _Context) -> float:
    """Value (from the root player's point of view) of a MAX or MIN node."""
    ctx.nodes += 1
    if time.perf_counter() > ctx.deadline:
        raise _Timeout()
    if depth == 0 or board.is_game_over()[0]:
        return evaluate(board, ctx.root, ctx.race_weight, ctx.progress_weight)
    turns = generate_turns(board, to_move)
    if not turns:                                    # the player to move has no creatures
        return evaluate(board, ctx.root, ctx.race_weight, ctx.progress_weight)
    maximizing = to_move == ctx.root
    best = -INF if maximizing else INF
    for turn in turns:
        v = _chance_value(board, turn, to_move, depth, ctx)
        best = max(best, v) if maximizing else min(best, v)
    return best


def choose_turn(board: BoardState, species: Species, depth: int = 2, time_limit: float = 1.5,
                race_weight: float = DEFAULT_RACE_WEIGHT, max_chance_battles: int = 2,
                progress_weight: float = 0.0) -> Tuple[Optional[Turn], SearchInfo]:
    """Best turn for `species` on `board` and some statistics. Returns (None, info) if no creatures."""
    start = time.perf_counter()
    ctx = _Context(species, start + time_limit, race_weight, max_chance_battles, progress_weight)
    info = SearchInfo(depth=depth)
    turns = generate_turns(board, species)
    info.root_turns = len(turns)
    if not turns:
        return None, info

    best_turn, best_value = turns[0], -INF
    try:
        for turn in turns:
            v = _chance_value(board, turn, species, depth, ctx)
            info.values.append((v, turn))
            info.root_turns_done += 1
            if v > best_value:                       # strict: ties keep the better-ranked turn
                best_value, best_turn = v, turn
    except _Timeout:
        info.timed_out = True
    info.nodes = ctx.nodes
    info.best_value = best_value if best_value > -INF else 0.0
    info.seconds = time.perf_counter() - start
    return best_turn, info


class SearchAgent:
    """Same interface as the repo's AIAgent: compute_moves(GameState) -> list of moves."""

    def __init__(self, name: str = "ExpectiBot", depth: int = 2, time_limit: float = 1.5,
                 race_weight: float = DEFAULT_RACE_WEIGHT, max_chance_battles: int = 2,
                 progress_weight: float = 0.0):
        self.name = name
        self.depth = depth
        self.time_limit = time_limit
        self.race_weight = race_weight
        self.progress_weight = progress_weight
        self.max_chance_battles = max_chance_battles
        self.last_info: Optional[SearchInfo] = None
        self.last_error: Optional[str] = None

    def compute_moves(self, state: GameState) -> Turn:
        board = None
        try:
            board = board_from_state(state)
            turn, info = choose_turn(board, state.our_species, self.depth, self.time_limit,
                                     self.race_weight, self.max_chance_battles, self.progress_weight)
            self.last_info = info
            return turn or []
        except Exception as e:                       # never crash the connection loop
            self.last_error = repr(e)
        try:                                         # fallback: the generator's top-ranked turn
            return generate_turns(board, state.our_species)[0]
        except Exception as e:
            self.last_error += f" / fallback: {e!r}"
            return []


if __name__ == "__main__":
    import sys
    from agents_baseline import RandomAgent
    from ai_agent import AIAgent
    from selfplay import print_summary, run_match

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    maps = ["thetrap.xml", "testmap.xml"]
    for label, make_b in (("Random", lambda: RandomAgent()), ("Starter", lambda: AIAgent("Starter"))):
        result = run_match(lambda: SearchAgent("Expecti"), make_b, maps, games_per_side=n)
        print_summary(result, "Expecti", label)
