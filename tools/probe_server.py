"""
probe_server.py - scripted clients that check rule details on the REAL game server.

Usage (server must already be running with the probe map loaded):
    python tools/probe_server.py <scenario> [host] [port]

Each scenario connects two clients (threads), plays a fixed script of moves and logs every
command received from the server with a timestamp. When a client's script runs out it keeps
playing a simple legal move so the game can continue. Findings are written by hand to
docs/SERVER_FINDINGS.md.
"""
import os
import socket
import struct
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

T0 = time.time()
LOCK = threading.Lock()


def log(who, msg):
    with LOCK:
        print(f"[{time.time() - T0:7.2f}s] {who:6s} {msg}", flush=True)


class ProbeClient:
    def __init__(self, name, host, port, script, late_turns=None, raw_turns=None):
        self.name = name
        self.host, self.port = host, port
        self.script = script              # {my_turn_index: [moves]}
        self.late_turns = late_turns or {}  # {my_turn_index: seconds to sleep before answering}
        self.raw_turns = raw_turns or {}  # {my_turn_index: raw bytes to send instead of MOV}
        self.board = {}
        self.home = None
        self.species = None               # 1 = vampires column, 2 = werewolves column
        self.rows = self.cols = 0
        self.turn = 0
        self.sock = None

    def recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("closed")
            buf += chunk
        return buf

    def send_moves(self, moves):
        payload = b"MOV" + bytes([len(moves)])
        for m in moves:
            payload += struct.pack("5B", *m)
        self.sock.sendall(payload)

    def fallback_move(self):
        ours = [(p, c[self.species]) for p, c in self.board.items() if c[self.species] > 0]
        srcs = {p for p, _ in ours}
        (x, y), n = max(ours, key=lambda g: g[1])
        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.cols and 0 <= ny < self.rows and (nx, ny) not in srcs:
                cell = self.board.get((nx, ny), (0, 0, 0))
                if cell == (0, 0, 0) or cell[self.species] > 0:
                    return [(x, y, n, nx, ny)]
        return [(x, y, n, x + 1 if x + 1 < self.cols else x - 1, y)]

    def run(self):
        self.sock = socket.create_connection((self.host, self.port))
        name = self.name.encode()
        self.sock.sendall(b"NME" + bytes([len(name)]) + name)
        log(self.name, "connected, sent NME")
        try:
            while True:
                cmd = self.recv_exact(3).decode(errors="replace")
                if cmd == "SET":
                    self.rows, self.cols = self.recv_exact(2)
                    log(self.name, f"SET rows={self.rows} cols={self.cols}")
                elif cmd == "HUM":
                    n = self.recv_exact(1)[0]
                    data = self.recv_exact(2 * n)
                    log(self.name, f"HUM {[(data[2*i], data[2*i+1]) for i in range(n)]}")
                elif cmd == "HME":
                    self.home = tuple(self.recv_exact(2))
                    log(self.name, f"HME {self.home}")
                elif cmd in ("MAP", "UPD"):
                    n = self.recv_exact(1)[0]
                    data = self.recv_exact(5 * n)
                    changes = [tuple(data[5*i:5*i+5]) for i in range(n)]
                    for x, y, h, v, w in changes:
                        if h == v == w == 0:
                            self.board.pop((x, y), None)
                        else:
                            self.board[(x, y)] = (h, v, w)
                    if self.species is None and self.home in self.board:
                        self.species = 1 if self.board[self.home][1] > 0 else 2
                        log(self.name, f"species = {'VAMPIRES' if self.species == 1 else 'WEREWOLVES'}")
                    log(self.name, f"{cmd} {changes}")
                    if cmd == "UPD":
                        self.play()
                elif cmd == "END":
                    log(self.name, "END")
                    self.board, self.species, self.turn = {}, None, 0
                elif cmd == "BYE":
                    log(self.name, "BYE")
                    break
                else:
                    log(self.name, f"UNKNOWN command {cmd!r}")
                    break
        except Exception as e:
            log(self.name, f"connection ended: {e!r}")
        finally:
            self.sock.close()

    def play(self):
        t = self.turn
        self.turn += 1
        if t in self.late_turns:
            log(self.name, f"turn {t}: sleeping {self.late_turns[t]}s before answering")
            time.sleep(self.late_turns[t])
        if t in self.raw_turns:
            log(self.name, f"turn {t}: sending RAW {self.raw_turns[t]!r}")
            self.sock.sendall(self.raw_turns[t])
            return
        moves = self.script.get(t) or self.fallback_move()
        log(self.name, f"turn {t}: MOV {moves}")
        self.send_moves(moves)


# Scenarios for tools/probe_maps/probe1.xml (V at (2,2)=10, W at (7,2)=10)
SCENARIOS = {
    # split from one cell, merged attack from two sources, random battle loss
    "rules": dict(
        V=dict(script={0: [(2, 2, 3, 1, 1), (2, 2, 3, 3, 1)],     # split 10 -> 3 + 3 + 4 kept
                       1: [(2, 2, 4, 1, 3)]}),                     # 4 attack 9 humans (random)
        W=dict(script={0: [(7, 2, 3, 6, 1), (7, 2, 3, 8, 1)],      # split
                       1: [(6, 1, 3, 7, 0), (8, 1, 3, 7, 0)]}),    # 3 + 3 into 5 humans
    ),
    # what happens when a player answers too late / sends an illegal move
    "late": dict(
        V=dict(script={}, late_turns={1: 7.0}),
        W=dict(script={}, raw_turns={2: b"MOV" + bytes([1]) + struct.pack("5B", 0, 0, 5, 1, 1)}),
    ),
    # rule 5: a cell both source and target in the same ply
    "rule5": dict(
        V=dict(script={0: [(2, 2, 5, 2, 3)], 1: [(2, 2, 5, 3, 2), (2, 3, 5, 2, 2)]}),
        W=dict(script={}),
    ),
    # exact 1.5x boundaries: p2.xml (V15 next to W10) and p3.xml (V6 next to W10)
    "thr15": dict(V=dict(script={0: [(2, 2, 15, 3, 2)]}), W=dict(script={})),
    "thr6": dict(V=dict(script={0: [(2, 2, 6, 3, 2)]}), W=dict(script={})),
    # many fallback moves, to see how / when the game ends
    "long": dict(V=dict(script={}), W=dict(script={})),
}


def main():
    scenario = sys.argv[1] if len(sys.argv) > 1 else "rules"
    host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 5555
    sc = SCENARIOS[scenario]
    # we don't know which client gets which species; both get the script keyed by species
    # after HME/MAP, so build clients lazily: a client picks its script once species is known.
    clients = []
    for name in ("ProbeA", "ProbeB"):
        c = ProbeClient(name, host, port, {})
        clients.append(c)

    orig_play = ProbeClient.play

    def play(self):
        if self.turn == 0 and not self.script and not self.late_turns and not self.raw_turns:
            cfg = sc["V" if self.species == 1 else "W"]
            self.script = cfg.get("script", {})
            self.late_turns = cfg.get("late_turns", {})
            self.raw_turns = cfg.get("raw_turns", {})
        orig_play(self)

    ProbeClient.play = play
    threads = []
    for c in clients:
        th = threading.Thread(target=c.run, daemon=True)
        th.start()
        threads.append(th)
        time.sleep(0.5)
    for th in threads:
        th.join(timeout=600)


if __name__ == "__main__":
    main()
