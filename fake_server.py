"""
fake_server.py  (our own file; it does not modify any shared repo file)

A small stand-in for the official game server, so we can test main.py + network.py + SafeAgent
end to end on a laptop (the official server is Windows only).

It speaks the protocol exactly as network.py reads/writes it:
    server -> client : SET rows cols | HUM n (x y)*n | HME x y | MAP n (x y h v w)*n |
                       UPD n (x y h v w)*n | END | BYE
    client -> server : NME len name | MOV n (x1 y1 count x2 y2)*n
and applies the OFFICIAL rules through server_rules.py (validation, pooled attacks, battles).

Assumptions (not verified on the real server; see the open-questions list):
  * the client's turn is triggered by a UPD message; when the client moves first, the server sends
    an empty UPD right after MAP;
  * UPD lists every cell that changed since the last UPD sent to this client;
  * an invalid or empty MOV ends the game immediately and the other side wins (what the DLL does);
  * a missing answer is a skipped turn (the server waits `answer_timeout` seconds).
"""
import random
import socket
import struct
import threading
import time
from typing import Callable, List, Optional, Tuple

from game_engine import BoardState
from game_state import Species
from server_rules import check_moves, perform_moves
from state_converter import state_from_board


class FakeServer:
    def __init__(self, board: BoardState, our_species: Species, opponent, max_plies: int = 200,
                 answer_timeout: float = 5.0, seed: int = 0, sabotage: Optional[str] = None):
        self.start_board = board
        self.our_species = our_species
        self.opp_species = Species.WEREWOLF if our_species == Species.VAMPIRE else Species.VAMPIRE
        self.opponent = opponent
        self.max_plies = max_plies
        self.answer_timeout = answer_timeout
        self.rng = random.Random(seed)
        self.sabotage = sabotage            # None | "unknown_command" | "hangup"
        # results the tests look at
        self.name_received: Optional[str] = None
        self.replies = 0                    # MOV messages received
        self.silent_turns = 0               # turns where the client sent nothing in time
        self.invalid: List[str] = []        # reasons for every illegal MOV we received
        self.answer_times: List[float] = []
        self.plies = 0
        self.final_board: Optional[BoardState] = None
        self.error: Optional[str] = None

        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> "FakeServer":
        self.thread.start()
        return self

    def join(self, timeout: float = 120.0) -> None:
        self.thread.join(timeout)
        assert not self.thread.is_alive(), "fake server did not finish"

    # ------------------------------------------------------------------ helpers
    def _recv(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.conn.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("client closed the connection")
            buf.extend(chunk)
        return bytes(buf)

    def _cells(self, board: BoardState, positions) -> bytes:
        out = bytearray()
        for (x, y) in positions:
            h, v, w = board.get_cell((x, y))
            out += struct.pack("5B", x, y, h, v, w)
        return bytes(out)

    def _send_cells(self, tag: bytes, board: BoardState, positions) -> None:
        positions = list(positions)
        self.conn.sendall(tag + struct.pack("B", len(positions)) + self._cells(board, positions))

    def _home(self, board: BoardState, species: Species) -> Tuple[int, int]:
        idx = 1 if species == Species.VAMPIRE else 2
        return next(p for p, c in sorted(board.grid.items()) if c[idx] > 0)

    @staticmethod
    def _diff(old: BoardState, new: BoardState):
        keys = set(old.grid) | set(new.grid)
        return sorted(p for p in keys if old.get_cell(p) != new.get_cell(p))

    def _read_mov(self):
        """Returns the list of moves, or None when nothing arrived in time."""
        self.conn.settimeout(self.answer_timeout)
        t0 = time.perf_counter()
        try:
            tag = self._recv(3)
            n = self._recv(1)[0]
            raw = self._recv(5 * n)
        except socket.timeout:
            return None
        finally:
            self.conn.settimeout(None)
        assert tag == b"MOV", tag
        self.answer_times.append(time.perf_counter() - t0)
        return [struct.unpack_from("5B", raw, 5 * i) for i in range(n)]

    # ------------------------------------------------------------------ the game
    def _run(self) -> None:
        try:
            self.conn, _ = self.listener.accept()
            self._game()
        except Exception as e:                       # noqa: BLE001  (the test prints it)
            self.error = repr(e)
        finally:
            try:
                self.conn.close()
            except Exception:                        # noqa: BLE001
                pass
            self.listener.close()

    def _game(self) -> None:
        # handshake: NME
        assert self._recv(3) == b"NME"
        ln = self._recv(1)[0]
        self.name_received = self._recv(ln).decode("ascii")

        board = self.start_board.clone()
        houses = sorted(p for p, c in board.grid.items() if c[0] > 0)
        self.conn.sendall(b"SET" + struct.pack("2B", board.rows, board.cols))
        self.conn.sendall(b"HUM" + struct.pack("B", len(houses)) + b"".join(struct.pack("2B", *p) for p in houses))
        self.conn.sendall(b"HME" + struct.pack("2B", *self._home(board, self.our_species)))
        self._send_cells(b"MAP", board, sorted(p for p, c in board.grid.items() if c != (0, 0, 0)))

        if self.sabotage == "unknown_command":
            self.conn.sendall(b"XYZ")
            time.sleep(0.3)
            return
        if self.sabotage == "hangup":
            return

        opp_home = self._home(board, self.opp_species)
        order = [Species.VAMPIRE, Species.WEREWOLF]       # vampires always move first
        pending_for_client = []                           # cells that changed since the client's last UPD
        over = False
        while self.plies < self.max_plies and not over:
            mover = order[self.plies % 2]
            if mover == self.our_species:
                self._send_cells(b"UPD", board, pending_for_client)
                pending_for_client = []
                moves = self._read_mov()
                if moves is None:
                    self.silent_turns += 1                # skipped turn, game goes on
                else:
                    self.replies += 1
                    reason = check_moves(board, mover, moves)
                    if reason is not None:
                        self.invalid.append(reason)
                        break                             # official server: illegal turn loses the game
                    new = perform_moves(board, mover, moves, self.rng)
                    pending_for_client = sorted(set(pending_for_client) | set(self._diff(board, new)))
                    board = new
            else:
                state = state_from_board(board, mover, home=opp_home)
                moves = self.opponent.compute_moves(state)
                if not moves or check_moves(board, mover, moves) is not None:
                    break                                 # a broken opponent: stop the test game
                new = perform_moves(board, mover, moves, self.rng)
                pending_for_client = sorted(set(pending_for_client) | set(self._diff(board, new)))
                board = new
            self.plies += 1
            over = board.is_game_over()[0]

        self.final_board = board
        self.conn.sendall(b"END")
        time.sleep(0.05)
        self.conn.sendall(b"BYE")
