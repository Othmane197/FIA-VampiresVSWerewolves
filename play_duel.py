"""
Launch a live duel between ApexChampion and a chosen Rival AI on the server GUI.
If the server is not running, launches VampiresVSWerewolvesGameServer.exe automatically.
Usage:
    python play_duel.py --rival PotentialFieldAI --delay 0.05
    python play_duel.py --rival GreedyReflexAI --delay 0.05
    python play_duel.py --rival ShallowMinimaxAI --delay 0.05
    python play_duel.py --rival RandomAI --delay 0.05
"""

import os
import subprocess
import sys
import time

def is_server_running():
    try:
        out = subprocess.check_output('tasklist /FI "IMAGENAME eq VampiresVSWerewolvesGameServer.exe"', shell=True)
        return b"VampiresVSWerewolvesGameServer.exe" in out
    except Exception:
        return False

def main():
    host = "127.0.0.1"
    port = 5555
    rival_ai = "PotentialFieldAI"
    delay = 0.05

    args = sys.argv[1:]
    if "--rival" in args:
        idx = args.index("--rival")
        if idx + 1 < len(args):
            rival_ai = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    if "--delay" in args:
        idx = args.index("--delay")
        if idx + 1 < len(args):
            delay = float(args[idx + 1])
            args = args[:idx] + args[idx + 2:]

    if len(args) >= 2:
        host = args[-2]
        port = int(args[-1])

    server_proc = None
    if not is_server_running():
        exe_path = os.path.abspath("VampiresVSWerewolvesGameServer.exe")
        if os.path.exists(exe_path):
            print(f"[Launcher] Starting Game Server: {exe_path} ...")
            server_proc = subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
            time.sleep(1.5)

    print(f"=== Starting Live Server Duel: ApexChampion VS {rival_ai} ({host}:{port}) ===")
    print("[Launcher] Connecting Player 1: ApexChampion (Alpha-Beta Minimax) ...")
    p1 = subprocess.Popen([sys.executable, "main.py", "--name", "ApexChampion", "--delay", str(delay), host, str(port)])
    time.sleep(0.5)

    print(f"[Launcher] Connecting Player 2: {rival_ai} ...")
    p2 = subprocess.Popen([sys.executable, "rival_bot.py", "--ai", rival_ai, "--delay", str(delay), host, str(port)])

    p1.wait()
    p2.wait()

    if server_proc:
        try:
            server_proc.terminate()
        except Exception:
            pass

    print("=== Duel concluded ===")

if __name__ == "__main__":
    main()
