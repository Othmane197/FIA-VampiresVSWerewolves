import socket
import struct
from typing import List, Tuple, Optional

class NetworkClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        print(f"[Network] Connected to {self.host}:{self.port}")

    def _recv_exact(self, num_bytes: int) -> bytes:
        buf = bytearray()
        while len(buf) < num_bytes:
            chunk = self.sock.recv(num_bytes - len(buf))
            if not chunk:
                raise ConnectionError("Socket connection closed by server")
            buf.extend(chunk)
        return bytes(buf)

    def send_name(self, name: str):
        ascii_name = name.encode('ascii')
        payload = b"NME" + struct.pack("B", len(ascii_name)) + ascii_name
        self.sock.sendall(payload)
        print(f"[Network] Sent AI name: {name}")

    def send_moves(self, moves: List[Tuple[int, int, int, int, int]]):
        """
        moves: list of (x_src, y_src, count, x_dst, y_dst)
        """
        payload = bytearray(b"MOV")
        payload.append(len(moves))
        for x1, y1, count, x2, y2 in moves:
            payload.extend(struct.pack("5B", x1, y1, count, x2, y2))
        self.sock.sendall(payload)
        print(f"[Network] Sent {len(moves)} moves: {moves}")

    def receive_command(self) -> Tuple[str, dict]:
        cmd_bytes = self._recv_exact(3)
        cmd = cmd_bytes.decode('ascii', errors='ignore')

        if cmd == "SET":
            rows, cols = struct.unpack("2B", self._recv_exact(2))
            return cmd, {"rows": rows, "cols": cols}

        elif cmd == "HUM":
            n = struct.unpack("B", self._recv_exact(1))[0]
            houses = []
            if n > 0:
                coords = self._recv_exact(n * 2)
                for i in range(n):
                    x, y = struct.unpack_from("2B", coords, i * 2)
                    houses.append((x, y))
            return cmd, {"houses": houses}

        elif cmd == "HME":
            x, y = struct.unpack("2B", self._recv_exact(2))
            return cmd, {"home": (x, y)}

        elif cmd in ("MAP", "UPD"):
            n = struct.unpack("B", self._recv_exact(1))[0]
            changes = []
            if n > 0:
                raw_data = self._recv_exact(n * 5)
                for i in range(n):
                    x, y, hum, vmp, wrw = struct.unpack_from("5B", raw_data, i * 5)
                    changes.append({
                        "x": x,
                        "y": y,
                        "humans": hum,
                        "vampires": vmp,
                        "werewolves": wrw
                    })
            return cmd, {"changes": changes}

        elif cmd == "END":
            return cmd, {}

        elif cmd == "BYE":
            return cmd, {}

        else:
            raise ValueError(f"Unknown command received: {cmd}")

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            print("[Network] Connection closed.")
