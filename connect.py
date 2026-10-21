#!/usr/bin/env python3
"""
Quick Server Connector for Vampires VS Werewolves
Usage:
    python connect.py                       (Interactive mode)
    python connect.py <IP> <PORT>           (Quick competition mode, delay=0.0)
    python connect.py <IP> <PORT> --name <MyBot> --delay 0.1
"""

import subprocess
import sys


def main():
    args = sys.argv[1:]

    # Default values
    host = "127.0.0.1"
    port = "5555"
    name = "ApexChampion"
    delay = "0.0"  # 0.0s for competition / fastest response

    # If no arguments given, prompt interactively
    if len(args) == 0:
        print("=" * 60)
        print("  Vampires VS Werewolves - Quick Server Connection")
        print("=" * 60)
        
        in_host = input(f"Enter Server IP [{host}]: ").strip()
        if in_host:
            host = in_host

        in_port = input(f"Enter Server Port [{port}]: ").strip()
        if in_port:
            port = in_port

        in_name = input(f"Enter Bot / Team Name [{name}]: ").strip()
        if in_name:
            name = in_name

        in_delay = input(f"Turn Delay in seconds (0.0 for competition, 0.5 for GUI) [{delay}]: ").strip()
        if in_delay:
            delay = in_delay

        cmd = [sys.executable, "main.py", "--name", name, "--delay", delay, host, port]
    else:
        # Pass-through mode: if delay not specified, set competition default delay 0.0
        cmd = [sys.executable, "main.py"]
        if "--delay" not in args:
            cmd.extend(["--delay", "0.0"])
        cmd.extend(args)

    print(f"\n[Launcher] Launching: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        print("\n[Launcher] Connection closed by user.")

if __name__ == "__main__":
    main()
