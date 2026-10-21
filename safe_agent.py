"""
safe_agent.py  (our own file; it does not modify any shared repo file)

SafeAgent = the agent we connect to the real server with.

Why it exists: on the OFFICIAL server an illegal turn or an EMPTY turn ends the game at once and the
opponent wins ("the player cheated"), and an exception in main.py's loop stops us playing. So the
search agent is not trusted blindly. Every turn goes through a gate (server_rules.check_moves) and
there are three tiers, tried in this order:

  1. "search"     the turn chosen by SearchAgent (expectiminimax), if the gate accepts it
  2. "candidate"  the first turn of the move generator's ranked list that the gate accepts
  3. "fallback"   the best single legal move found by brute force (any group, any neighbour)

It returns [] only when we have no creature at all (the game is over anyway) or when the species is
unknown. It never raises. `last_source` and `last_problem` say what happened on the last call, and
`counts` totals how often each tier was used (useful to see in the logs if tier 1 ever fails).
"""
import time
from typing import Dict, List, Optional, Tuple

from game_engine import BoardState
from game_state import GameState, Species
from move_generator import generate_turns
from search_agent import SearchAgent
from server_rules import check_moves, is_certain_win, win_probability
from state_converter import board_from_state

Move = Tuple[int, int, int, int, int]
Turn = List[Move]


def any_legal_turn(board: BoardState, species: Species) -> Turn:
    """Best single legal move by brute force (every group x every neighbour x whole group).
    Preference: a certain win (convert humans / kill monsters) > an empty cell or merging with our own
    group > a random battle, the likelier win first. Returns [] only if we have no creatures."""
    best = None
    is_vamp = species == Species.VAMPIRE
    for pos, count in sorted(board.get_species_groups(species), key=lambda g: (-g[1], g[0])):
        for n in board.get_neighbors(pos):
            move = (pos[0], pos[1], count, n[0], n[1])
            if check_moves(board, species, [move]) is not None:
                continue
            h, v, w = board.get_cell(n)
            own, enemy = (v, w) if is_vamp else (w, v)
            if h > 0:
                tier = 3.0 if is_certain_win(count, h, True) else 1.0 + win_probability(count, h, True)
            elif enemy > 0:
                tier = 3.0 if is_certain_win(count, enemy, False) else 1.0 + win_probability(count, enemy, False)
            else:
                tier = 2.0                                  # empty cell or our own group
            key = (tier, move[::-1])                        # deterministic tie-break
            if best is None or key > best[0]:
                best = (key, move)
    return [] if best is None else [best[1]]


class SafeAgent:
    """Same interface as the repo's AIAgent: compute_moves(GameState) -> list of moves."""

    def __init__(self, name: str = "ExpectiBot", inner=None, depth: int = 2, time_limit: float = 1.2,
                 **search_kwargs):
        self.name = name
        self.inner = inner if inner is not None else SearchAgent(name, depth=depth, time_limit=time_limit,
                                                                 **search_kwargs)
        self.last_source: Optional[str] = None
        self.last_problem: Optional[str] = None
        self.last_seconds: float = 0.0
        self.counts: Dict[str, int] = {"search": 0, "candidate": 0, "fallback": 0, "none": 0}

    def _note(self, problem: str) -> None:
        self.last_problem = problem if self.last_problem is None else self.last_problem + " | " + problem

    def compute_moves(self, state: GameState) -> Turn:
        start = time.perf_counter()
        self.last_source = None
        self.last_problem = None
        try:
            return self._compute(state)
        except Exception as e:                                # absolutely nothing may escape
            self._note(f"unexpected {e!r}")
            self.last_source = "none"
            self.counts["none"] += 1
            return []
        finally:
            self.last_seconds = time.perf_counter() - start

    def _compute(self, state: GameState) -> Turn:
        species = state.our_species
        if species is None:
            self._note("our species is unknown")
            self.last_source = "none"
            self.counts["none"] += 1
            return []
        board = board_from_state(state)
        if not board.get_species_groups(species):
            self._note("we have no creature")
            self.last_source = "none"
            self.counts["none"] += 1
            return []

        # Tier 1: the search agent's turn, if the server would accept it
        try:
            turn = list(self.inner.compute_moves(state))
            reason = check_moves(board, species, turn)
            if reason is None:
                return self._done("search", turn)
            self._note(f"search turn rejected: {reason}")
        except Exception as e:
            self._note(f"search failed: {e!r}")

        # Tier 2: the first accepted turn of the generator's ranked list
        try:
            for turn in generate_turns(board, species):
                if check_moves(board, species, turn) is None:
                    return self._done("candidate", list(turn))
            self._note("no generator candidate accepted")
        except Exception as e:
            self._note(f"generator failed: {e!r}")

        # Tier 3: brute-force single move
        turn = any_legal_turn(board, species)
        if turn and check_moves(board, species, turn) is None:
            return self._done("fallback", turn)
        self._note("no legal move found")
        self.last_source = "none"
        self.counts["none"] += 1
        return []

    def _done(self, source: str, turn: Turn) -> Turn:
        self.last_source = source
        self.counts[source] += 1
        return turn
