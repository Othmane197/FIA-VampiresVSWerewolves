"""
agents_baseline.py  (our own file)

Simple reference opponents for the self-play harness.
Every agent has the same interface as the repo's AIAgent:
    compute_moves(state: GameState) -> list of (src_x, src_y, count, dst_x, dst_y)
"""
import random


class RandomAgent:
    """Plays random LEGAL moves. The weakest sensible opponent: any real strategy must beat it."""

    def __init__(self, name: str = "Random"):
        self.name = name

    def compute_moves(self, state):
        groups = list(state.get_our_groups())
        if not groups:
            return []
        random.shuffle(groups)
        # Choose which groups move this turn (at least one, Rule 1).
        movers = [groups[0]] + [g for g in groups[1:] if random.random() < 0.5]
        sources = {pos for pos, _ in movers}

        moves = []
        for pos, count in movers:
            # Rule 5: never move INTO a cell that is also a source this turn.
            options = [c for c in state.get_legal_adjacent_cells(pos) if c not in sources]
            if not options:
                continue
            n = count if random.random() < 0.5 else random.randint(1, count)
            dst = random.choice(options)
            moves.append((pos[0], pos[1], n, dst[0], dst[1]))
        return moves
