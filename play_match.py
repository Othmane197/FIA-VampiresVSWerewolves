import subprocess
import sys
import time

def main():
    host = "127.0.0.1"
    port = 5555
    delay = 0.5  # 500ms delay between moves

    args = sys.argv[1:]
    if "--delay" in args:
        idx = args.index("--delay")
        if idx + 1 < len(args):
            delay = float(args[idx + 1])
            args = args[:idx] + args[idx + 2:]

    if len(args) >= 2:
        host = args[-2]
        port = int(args[-1])

    print(f"=== Launching 2 AI Bots against {host}:{port} ({delay}s delay per turn) ===")
    print("[Launcher] Starting Bot 1: VampireBot ...")
    p1 = subprocess.Popen([sys.executable, "main.py", "--name", "VampireBot", "--delay", str(delay), host, str(port)])
    time.sleep(0.5)

    print("[Launcher] Starting Bot 2: WerewolfBot ...")
    p2 = subprocess.Popen([sys.executable, "main.py", "--name", "WerewolfBot", "--delay", str(delay), host, str(port)])

    p1.wait()
    p2.wait()
    print("=== Match ended ===")

if __name__ == "__main__":
    main()
