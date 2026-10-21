"""
Headless stand-in for VampiresVSWerewolvesGameServer.exe, speaking the same binary protocol,
so main.py can be tested end-to-end without the Windows GUI (and on any OS).

Behaviour copied from the real server (docs/SERVER_FINDINGS.md):
  * player 0 = first to connect = Vampires = moves first;
  * on connection: NME is read, then SET, HUM, HME, MAP are sent;
  * each turn: UPD with every cell changed since that player's last UPD, then wait for MOV;
  * late reply (> move_timeout): the turn is skipped; leftover bytes are flushed next turn;
  * illegal moves (the server's CheckMoves) or a dropped connection: game over ("cheating");
  * end: wipe-out, max_ply plies in total, or (game_seconds) the game clock (MaxGameDuration,
    default 5 min on the real server); then END and BYE to both players.

    python tools/fake_server.py --map testmap.xml --port 5555 --max-ply 200 --timeout 2.0 --game-seconds 300
"""
import argparse
import os
import random
import select
import socket
import struct
import sys
import time
from typing import Dict, List, Optional, Set

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from splitter.rules import V, W, check_moves, other
from splitter.state import State


def _recv_exact(sock: socket.socket, n: int, deadline: Optional[float] = None) -> bytes:
    """Read exactly n bytes from the socket (optionally before a deadline)."""
    buf = b""
    while len(buf) < n:
        if deadline is not None:
            left = deadline - time.time()
            if left <= 0:
                raise TimeoutError
            sock.settimeout(left)
        else:
            sock.settimeout(None)
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("client closed the connection")
        buf += chunk
    return buf


class FakeServer:
    """One-game headless server with the real protocol, rules, time limit and cheating checks."""
    def __init__(self, state: State, port: int = 0, move_timeout: float = 2.0, seed: Optional[int] = None,
                 log=print, game_seconds: Optional[float] = None):
        """Listen on 127.0.0.1:port (0 = any free port) for a game on `state`; game_seconds = game clock."""
        self.initial = state
        self.move_timeout = move_timeout
        self.game_seconds = game_seconds
        self.rng = random.Random(seed)
        self.log = log
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", port))
        self.listener.listen(2)
        self.port = self.listener.getsockname()[1]
        self.result: dict = {}
        self.connected = 0            # players that have connected and sent NME (connection order = player order)

    # ------------------------------------------------------------------ protocol
    def _cells(self, state: State, coords) -> bytes:
        """Encode cells as the protocol's 5-byte tuples (x, y, humans, vampires, werewolves)."""
        out = bytearray()
        for (x, y) in coords:
            out += struct.pack("5B", x, y, state.humans.get((x, y), 0),
                               state.groups[V].get((x, y), 0), state.groups[W].get((x, y), 0))
        return bytes(out)

    def _send_upd(self, sock, cmd: str, state: State, coords) -> None:
        """Send a MAP or UPD message with the given cells."""
        coords = list(coords)
        sock.sendall(cmd.encode() + bytes([len(coords)]) + self._cells(state, coords))

    def run(self) -> dict:
        """Accept 2 players, play the whole game, send END and BYE, return the result."""
        state = self.initial.copy()
        state.ply = 0
        homes = {V: next(iter(state.groups[V])), W: next(iter(state.groups[W]))}
        socks: List[socket.socket] = []
        names: List[str] = []
        for player in (0, 1):
            conn, _ = self.listener.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            hdr = _recv_exact(conn, 4, time.time() + 10)
            if hdr[:3] != b"NME":
                raise ValueError(f"expected NME, got {hdr!r}")
            name = _recv_exact(conn, hdr[3], time.time() + 10).decode("ascii", "replace")
            names.append(name)
            self.connected = len(names)
            side = V if player == 0 else W
            conn.sendall(b"SET" + bytes([state.rows, state.cols]))
            houses = sorted(state.humans)
            conn.sendall(b"HUM" + bytes([len(houses)]) + b"".join(bytes(h) for h in houses))
            conn.sendall(b"HME" + bytes(homes[side]))
            every = set(state.humans) | set(state.groups[V]) | set(state.groups[W])
            self._send_upd(conn, "MAP", state, sorted(every))
            socks.append(conn)
            self.log(f"[fake-server] player {player} = {name} ({'VW'[side]})")
        dirty: Dict[int, Set] = {0: set(), 1: set()}
        stats = {"timeouts": [0, 0], "cheat": None, "plies": 0, "names": names}
        player = 0
        winner = None
        reason = "plies"
        started = time.time()
        while True:
            if self.game_seconds is not None and time.time() - started >= self.game_seconds:
                reason = "clock"                   # MaxGameDuration: the larger total wins
                break
            if not state.groups[V] or not state.groups[W]:
                reason = "wipeout"
                break
            if state.ply >= state.max_ply:
                break
            side = V if player == 0 else W
            sock = socks[player]
            # flush leftovers from an earlier (late) reply, like the real server
            while True:
                r, _, _ = select.select([sock], [], [], 0)
                if not r:
                    break
                if not sock.recv(65536):
                    break
            try:
                self._send_upd(sock, "UPD", state, sorted(dirty[player]))
                dirty[player].clear()
                deadline = time.time() + self.move_timeout
                hdr = _recv_exact(sock, 4, deadline)
                if hdr[:3] != b"MOV":
                    raise ValueError(f"expected MOV, got {hdr!r}")
                raw = _recv_exact(sock, 5 * hdr[3], deadline)
            except TimeoutError:
                stats["timeouts"][player] += 1
                self.log(f"[fake-server] {names[player]} timed out at ply {state.ply}")
                state = state.copy()
                state.ply += 1
                player = 1 - player
                continue
            except (ConnectionError, OSError, ValueError) as e:
                stats["cheat"] = (names[player], f"connection/protocol: {e!r}")
                winner, reason = other(side), "cheat"
                break
            moves = [struct.unpack_from("5B", raw, 5 * i) for i in range(hdr[3])]
            moves = [(a, b, c, d, e) for a, b, c, d, e in moves]
            ok, why = check_moves(state.rows, state.cols, state.groups[side], moves)
            if not ok:
                stats["cheat"] = (names[player], why)
                self.log(f"[fake-server] {names[player]} CHEATED: {why} {moves}")
                winner, reason = other(side), "cheat"
                break
            changed = {(m[0], m[1]) for m in moves} | {(m[3], m[4]) for m in moves}
            state = state.apply(side, moves, self.rng)
            dirty[0] |= changed
            dirty[1] |= changed
            player = 1 - player
        if reason != "cheat":
            winner = state.winner()
        time.sleep(0.05)
        for s in socks:
            try:
                s.sendall(b"END")
                s.sendall(b"BYE")
            except OSError:
                pass
        time.sleep(0.2)
        for s in socks:
            s.close()
        self.listener.close()
        stats.update(winner=winner, reason=reason, plies=state.ply,
                     totals=(state.total(V), state.total(W)))
        self.result = stats
        self.log(f"[fake-server] game over: {reason}, winner "
                 f"{'VW'[winner] if winner is not None else 'none'}, totals V/W {stats['totals']}, plies {state.ply}")
        return stats


def main():
    """Command line: run the fake server on a map file."""
    from arena.maps import load_xml
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="testmap.xml")
    ap.add_argument("--port", type=int, default=5555)
    ap.add_argument("--max-ply", type=int, default=200)
    ap.add_argument("--timeout", type=float, default=2.0)
    ap.add_argument("--game-seconds", type=float, default=None, help="game clock (real server: 300)")
    a = ap.parse_args()
    srv = FakeServer(load_xml(a.map, a.max_ply), a.port, a.timeout, game_seconds=a.game_seconds)
    print(f"[fake-server] listening on 127.0.0.1:{srv.port}")
    srv.run()


if __name__ == "__main__":
    main()
