"""
map_loader.py  (our own file; it does not modify any shared repo file)

Reads a map .xml file (testmap.xml, thetrap.xml, ...) and builds a BoardState
(from game_engine.py) so we can simulate games locally, without the server.

Map format, as seen in the provided maps:
    <Map Rows="5" Columns="10">
      <Humans X="2" Y="2" Count="4"/>
      <Werewolves X="4" Y="1" Count="4"/>
      <Vampires X="4" Y="3" Count="4"/>
    </Map>
X is the column (0 = left), Y is the row (0 = top), like in the protocol.
"""
import warnings
import xml.etree.ElementTree as ET

from game_engine import BoardState

# Which slot of the (humans, vampires, werewolves) tuple each XML tag fills.
_SLOT = {"Humans": 0, "Vampires": 1, "Werewolves": 2}


def load_map(path: str, max_turns: int = 200) -> BoardState:
    """Read the XML file at `path` and return the starting BoardState."""
    root = ET.parse(path).getroot()
    rows = int(root.get("Rows"))
    cols = int(root.get("Columns"))
    board = BoardState(rows, cols, max_turns)

    for element in root:
        slot = _SLOT.get(element.tag)
        if slot is None:
            warnings.warn(f"{path}: ignoring unknown tag <{element.tag}>")
            continue

        x = int(element.get("X"))
        y = int(element.get("Y"))
        count = int(element.get("Count"))
        if not (0 <= x < cols and 0 <= y < rows):
            raise ValueError(f"{path}: <{element.tag}> at ({x},{y}) is outside the {rows}x{cols} grid")

        # Add to whatever is already on the cell (in case a map lists a cell twice).
        cell = list(board.get_cell((x, y)))
        cell[slot] += count
        board.set_cell((x, y), *cell)

    return board


def render_board(board: BoardState) -> str:
    """Plain-text picture of a BoardState (H = humans, V = vampires, W = werewolves)."""
    lines = ["    " + "".join(f"{x:>4}" for x in range(board.cols))]
    for y in range(board.rows):
        row = [f"{y:>3} "]
        for x in range(board.cols):
            h, v, w = board.get_cell((x, y))
            if v:
                label = f"V{v}"
            elif w:
                label = f"W{w}"
            elif h:
                label = f"H{h}"
            else:
                label = "."
            row.append(f"{label:>4}")
        lines.append("".join(row))
    return "\n".join(lines)
