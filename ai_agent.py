"""
Starter AI Agent Template for Vampires VS Werewolves
FIA - CentraleSupélec / Centrale Casablanca

Instructions for developers:
- Implement your decision-making algorithm inside `compute_moves()`.
- You can create helper methods, heuristics, tree search (Minimax, Alpha-Beta, MCTS, etc.).
- Respect the protocol constraints:
    * Respond within 2.0 seconds per turn.
    * Return a list of tuples: (src_x, src_y, count, dst_x, dst_y)
    * Destination must be Chebyshev distance 1 (adjacent 8 directions).
    * Rule 5: A cell cannot be both a source and a destination in the same turn.
"""

import os
import random
from typing import List, Optional, Tuple

from game_state import GameState


class AIAgent:
    """
    The tournament bot: "The Splitter" (splitter/agent.py, MCTS over joint plans with safe
    detachments). Any failure falls back to the original starter logic below.

    Environment knobs (optional): SPLITTER_TIME (seconds per move, default 1.5),
    SPLITTER_MODEL=backup (play the backup model, the campaign-2 flagship, instead of the
    flagship, splitter.agent.MODELS),
    SPLITTER_OPTIONS="key=value,..." (testing only: extra options on top of the model, e.g. a
    candidate under real conditions; ignored, with a warning, if they do not build an engine),
    SPLITTER_VERBOSE=1 (print the search statistics every turn).
    """

    def __init__(self, name: str = "CentraleBot", time_limit: Optional[float] = None, **kwargs):
        """Create the Splitter engine (time budget from SPLITTER_TIME) and the starter fallback."""
        self.name = name
        self.starter = StarterAgent(name)
        if time_limit is None:
            time_limit = float(os.environ.get("SPLITTER_TIME", "1.5"))
        self.engine = None
        try:
            from splitter.agent import MODELS, SplitterAgent
            model = os.environ.get("SPLITTER_MODEL", "flagship")
            options = {**MODELS.get(model, MODELS["flagship"]), **kwargs}
            extra = _parse_options(os.environ.get("SPLITTER_OPTIONS", ""))
            verbose = os.environ.get("SPLITTER_VERBOSE") == "1"
            for opts in ([{**options, **extra}, options] if extra else [options]):
                try:
                    self.engine = SplitterAgent(name=name, time_limit=time_limit, verbose=verbose, **opts)
                    break
                except TypeError as e:               # a bad SPLITTER_OPTIONS never costs the engine
                    print(f"[AIAgent] SPLITTER_OPTIONS ignored ({e})")
        except Exception as e:                       # e.g. a file missing on the CTI machine
            print(f"[AIAgent] Splitter unavailable ({e!r}), using the starter strategy")
            self.engine = None

    def reset(self):
        """Forget the previous game (called by main.py on END)."""
        if self.engine is not None:
            self.engine.reset()

    def compute_moves(self, state: GameState) -> List[Tuple[int, int, int, int, int]]:
        """Splitter's moves for this turn; the starter strategy if the Splitter fails."""
        if self.engine is not None:
            try:
                moves = self.engine.compute_moves(state)
                if moves:
                    return moves
            except Exception as e:
                print(f"[AIAgent] Splitter error {e!r}, using the starter strategy this turn")
        return self.starter.compute_moves(state)

    def anytime_moves(self) -> Optional[List[Tuple[int, int, int, int, int]]]:
        """For main.py's watchdog when compute_moves is late: the search's best plan so far, or None."""
        try:
            return self.engine.anytime_moves() if self.engine is not None else None
        except Exception:                       # never let the late answer cost the turn
            return None


def _parse_options(text: str) -> dict:
    """'a=1,b=0.5,c=true' -> {'a': 1, 'b': 0.5, 'c': True}; malformed entries are skipped."""
    out = {}
    for item in text.split(","):
        key, sep, value = item.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not key:
            continue
        low = value.lower()
        if low in ("true", "false"):
            out[key] = low == "true"
            continue
        for cast in (int, float):
            try:
                out[key] = cast(value)
                break
            except ValueError:
                pass
        else:
            out[key] = value
    return out


class StarterAgent:
    """The original starter-kit strategy (walk to the nearest target). Kept as fallback/baseline."""

    def __init__(self, name: str = "CentraleBot"):
        """Original starter-kit agent (kept as last-resort fallback and as a baseline opponent)."""
        self.name = name

    def compute_moves(self, state: GameState) -> List[Tuple[int, int, int, int, int]]:
        """
        Computes the list of moves for the current turn.

        Args:
            state (GameState): The current game state containing:
                - state.rows, state.cols : Dimensions of the grid
                - state.our_species      : Species.VAMPIRE or Species.WEREWOLF
                - state.enemy_species    : Species.WEREWOLF or Species.VAMPIRE
                - state.get_our_groups() : List of [((x, y), count), ...]
                - state.get_enemy_groups(): List of [((x, y), count), ...]
                - state.get_human_groups(): List of [((x, y), count), ...]
                - state.get_legal_adjacent_cells((x, y)) : 8-neighborhood cells within board bounds

        Returns:
            List[Tuple[int, int, int, int, int]]:
                A list of moves formatted as:
                [(src_x, src_y, count, dst_x, dst_y), ...]
        """
        our_groups = state.get_our_groups()
        if not our_groups:
            return []

        # =========================================================================
        # TODO: IMPLEMENT YOUR AI STRATEGY HERE!
        #
        # Suggestions:
        # 1. State evaluation heuristic (Material count, territory, distance to humans)
        # 2. Minimax with Alpha-Beta pruning
        # 3. Iterative deepening with a time limit (e.g., 1.5 - 1.8 seconds)
        # 4. Monte Carlo Tree Search (MCTS) or Potential Fields
        # =========================================================================

        # DEFAULT STARTER BEHAVIOR:
        # A simple legal move generator that moves your groups towards the closest humans or enemies.
        moves: List[Tuple[int, int, int, int, int]] = []
        sources = {pos for pos, _ in our_groups}
        chosen_destinations = set()

        human_groups = state.get_human_groups()
        enemy_groups = state.get_enemy_groups()
        targets = [pos for pos, _ in human_groups] or [pos for pos, _ in enemy_groups]

        for (src_x, src_y), count in our_groups:
            src = (src_x, src_y)
            neighbors = state.get_legal_adjacent_cells(src)
            
            # Rule 5: Destination cannot be one of our sources or another group's target
            valid_destinations = [n for n in neighbors if n not in sources and n not in chosen_destinations]
            if not valid_destinations:
                valid_destinations = [n for n in neighbors if n not in sources] or neighbors

            # Move towards the closest target if available
            if targets:
                best_dst = min(valid_destinations, key=lambda n: min(state.chebyshev_dist(n, t) for t in targets))
            else:
                best_dst = random.choice(valid_destinations)

            chosen_destinations.add(best_dst)
            moves.append((src_x, src_y, count, best_dst[0], best_dst[1]))

        return moves
