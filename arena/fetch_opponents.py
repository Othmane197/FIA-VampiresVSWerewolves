"""
Copy the teammates' bots from their git branches into arena/vendor/<branch>/ (gitignored),
so the arena always tests against their latest pushed code without touching their branches.

    python -m arena.fetch_opponents            (uses the local origin/* refs)
    python -m arena.fetch_opponents --fetch    (git fetch first)

Only the agent files are copied: game_state.py / game_engine.py are NOT copied, so the vendored
bots use the repo's copies (they are identical) and share the same Species enum.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(ROOT, "arena", "vendor")

FILES = {
    "Othmane": ["apex_agent.py", "rival_agents.py"],
    "Ronita": ["mcts_agent.py"],
    "Dana": ["agents_baseline.py", "ai_agent.py", "battle_model.py", "evaluation.py",
             "map_loader.py", "move_generator.py", "search_agent.py", "sparring_agents.py",
             "state_converter.py", "transition.py"],
}


def fetch(do_git_fetch: bool = False) -> None:
    """Copy the teammates' agent files from their origin/<branch> into arena/vendor/<branch>/."""
    if do_git_fetch:
        subprocess.run(["git", "fetch", "--all", "-q"], cwd=ROOT, check=False)
    for branch, files in FILES.items():
        dst_dir = os.path.join(VENDOR, branch)
        os.makedirs(dst_dir, exist_ok=True)
        for f in files:
            res = subprocess.run(["git", "show", f"origin/{branch}:{f}"], cwd=ROOT,
                                 capture_output=True, check=False)
            if res.returncode != 0:
                print(f"  !! {branch}:{f} not found ({res.stderr.decode(errors='replace').strip()})")
                continue
            with open(os.path.join(dst_dir, f), "wb") as out:
                out.write(res.stdout)
        rev = subprocess.run(["git", "rev-parse", "--short", f"origin/{branch}"], cwd=ROOT,
                             capture_output=True, text=True, check=False).stdout.strip()
        with open(os.path.join(dst_dir, "REVISION"), "w") as out:
            out.write(rev + "\n")
        print(f"  {branch:8s} @ {rev}: {', '.join(files)}")


if __name__ == "__main__":
    fetch("--fetch" in sys.argv)
