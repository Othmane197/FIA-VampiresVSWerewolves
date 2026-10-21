from enum import Enum
from typing import Dict, List, Optional, Tuple


class Species(Enum):
    VAMPIRE = "VAMPIRE"
    WEREWOLF = "WEREWOLF"

class Cell:
    __slots__ = ("humans", "vampires", "werewolves")
    def __init__(self, humans: int = 0, vampires: int = 0, werewolves: int = 0):
        self.humans = humans
        self.vampires = vampires
        self.werewolves = werewolves

    def is_empty(self) -> bool:
        return self.humans == 0 and self.vampires == 0 and self.werewolves == 0

    def copy(self) -> 'Cell':
        return Cell(self.humans, self.vampires, self.werewolves)

class GameState:
    def __init__(self):
        self.rows: int = 0
        self.cols: int = 0
        self.houses: List[Tuple[int, int]] = []
        self.home: Optional[Tuple[int, int]] = None
        self.our_species: Optional[Species] = None
        self.enemy_species: Optional[Species] = None
        # Board stored as dict (x, y) -> Cell
        self.board: Dict[Tuple[int, int], Cell] = {}

    def set_grid(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        self.board.clear()

    def set_houses(self, houses: List[Tuple[int, int]]):
        self.houses = houses

    def set_home(self, home: Tuple[int, int]):
        self.home = home

    def apply_updates(self, changes: List[dict]):
        for c in changes:
            pos = (c["x"], c["y"])
            hum, vmp, wrw = c["humans"], c["vampires"], c["werewolves"]
            if hum == 0 and vmp == 0 and wrw == 0:
                self.board.pop(pos, None)
            else:
                self.board[pos] = Cell(hum, vmp, wrw)

        # Detect our species if not yet determined
        if self.our_species is None and self.home is not None:
            home_cell = self.board.get(self.home)
            if home_cell:
                if home_cell.vampires > 0:
                    self.our_species = Species.VAMPIRE
                    self.enemy_species = Species.WEREWOLF
                    print("[GameState] Identified species: We are VAMPIRES")
                elif home_cell.werewolves > 0:
                    self.our_species = Species.WEREWOLF
                    self.enemy_species = Species.VAMPIRE
                    print("[GameState] Identified species: We are WEREWOLVES")

    def get_our_groups(self) -> List[Tuple[Tuple[int, int], int]]:
        groups = []
        for pos, cell in self.board.items():
            count = cell.vampires if self.our_species == Species.VAMPIRE else cell.werewolves
            if count > 0:
                groups.append((pos, count))
        return groups

    def get_enemy_groups(self) -> List[Tuple[Tuple[int, int], int]]:
        groups = []
        for pos, cell in self.board.items():
            count = cell.werewolves if self.our_species == Species.VAMPIRE else cell.vampires
            if count > 0:
                groups.append((pos, count))
        return groups

    def get_human_groups(self) -> List[Tuple[Tuple[int, int], int]]:
        groups = []
        for pos, cell in self.board.items():
            if cell.humans > 0:
                groups.append((pos, cell.humans))
        return groups

    def chebyshev_dist(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> int:
        return max(abs(pos1[0] - pos2[0]), abs(pos1[1] - pos2[1]))

    def get_legal_adjacent_cells(self, pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        x, y = pos
        neighbors = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.cols and 0 <= ny < self.rows:
                    neighbors.append((nx, ny))
        return neighbors

    def reset_for_new_game(self):
        self.our_species = None
        self.enemy_species = None
        self.home = None
        self.board.clear()
        print("[GameState] State reset for new game.")

    def render_board(self) -> str:
        """
        Renders a clean ASCII board representation with colors.
        """
        lines = []
        header = "   " + "".join(f"{x%10} " for x in range(self.cols))
        lines.append(header)
        lines.append("  +" + "--" * self.cols + "+")

        for y in range(self.rows):
            row_str = [f"{y:2d}|"]
            for x in range(self.cols):
                cell = self.board.get((x, y))
                if cell is None or cell.is_empty():
                    row_str.append(" .")
                elif cell.vampires > 0:
                    cnt = min(cell.vampires, 99)
                    row_str.append(f"\033[91mV{cnt}\033[0m" if cnt < 10 else f"\033[91m{cnt}\033[0m")
                elif cell.werewolves > 0:
                    cnt = min(cell.werewolves, 99)
                    row_str.append(f"\033[94mW{cnt}\033[0m" if cnt < 10 else f"\033[94m{cnt}\033[0m")
                elif cell.humans > 0:
                    cnt = min(cell.humans, 99)
                    row_str.append(f"\033[93mH{cnt}\033[0m" if cnt < 10 else f"\033[93m{cnt}\033[0m")
            row_str.append("|")
            lines.append("".join(row_str))

        lines.append("  +" + "--" * self.cols + "+")

        # Summary line
        our_cnt = sum(c for _, c in self.get_our_groups())
        ene_cnt = sum(c for _, c in self.get_enemy_groups())
        hum_cnt = sum(c for _, c in self.get_human_groups())
        our_name = self.our_species.value if self.our_species else "US"
        ene_name = self.enemy_species.value if self.enemy_species else "ENEMY"
        summary = f"[{our_name}: {our_cnt}] | [{ene_name}: {ene_cnt}] | [Humans left: {hum_cnt}]"
        lines.append(summary)
        return "\n".join(lines)
