"""
Copy the teammates' CURRENT bots from their git branches into arena/vendor/<branch>/ (gitignored),
without touching their branches.

    python -m arena.fetch_opponents            (uses the local origin/* refs, no network)
    python -m arena.fetch_opponents --fetch    (git fetch first: their latest pushed code)

Every top-level .py file of the branch is copied, so a teammate who adds or renames a helper module
is picked up automatically, and files they deleted are removed from the copy. Not copied:
  * the starter-kit files we all share (SHARED): the vendored bots use the repo's copies, so they
    all agree on the same Species enum and board classes;
  * their unit tests (test_*.py).
arena/vendor/<branch>/REVISION records the commit that was copied (also returned by fetch()).
"""
import os
import subprocess
import sys
from typing import Dict, Iterable, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(ROOT, "arena", "vendor")

BRANCHES = ("Othmane", "Ronita", "Dana")
SHARED = {"game_state.py", "game_engine.py", "network.py", "main.py", "connect.py"}
# the files arena/opponents.py imports from each branch (a missing one is reported)
REQUIRED = {
    "Othmane": ["apex_agent.py", "rival_agents.py"],
    "Ronita": ["mcts_agent.py"],
    "Dana": ["search_agent.py", "sparring_agents.py"],
}


def _git(*args, timeout: Optional[float] = None) -> subprocess.CompletedProcess:
    """Run a git command in the repo (never raises, never prompts; check returncode)."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False,
                              env=env, timeout=timeout)
    except subprocess.TimeoutExpired:            # a half-working network: give up, use the last download
        return subprocess.CompletedProcess(["git", *args], 1, "", f"timed out after {timeout:.0f} s")


def fetch(do_git_fetch: bool = False, branches: Optional[Iterable[str]] = None, log=print) -> Dict[str, dict]:
    """
    Copy the teammates' bots from origin/<branch> into arena/vendor/<branch>/.
    do_git_fetch: download their latest pushes first (needs the network).
    Returns {branch: {"commit", "date", "subject", "files", "updated", "missing"}}, where
    updated = True if `git fetch` succeeded (False = the last version downloaded earlier was used).
    """
    branches = list(branches or BRANCHES)
    updated = False
    if do_git_fetch and branches:
        res = _git("fetch", "origin", *branches, "-q", timeout=120)
        updated = res.returncode == 0
        if not updated:
            log(f"  !! git fetch failed ({res.stderr.strip() or 'no network?'}): "
                f"using the version downloaded last time")
    versions = {}
    for branch in branches:
        ref = f"origin/{branch}"
        listing = _git("ls-tree", "--name-only", ref)
        if listing.returncode != 0:
            log(f"  !! branch {ref} not found: {listing.stderr.strip()}")
            continue
        files = sorted(f for f in listing.stdout.split()
                       if f.endswith(".py") and f not in SHARED and not f.startswith("test_"))
        dst_dir = os.path.join(VENDOR, branch)
        os.makedirs(dst_dir, exist_ok=True)
        for old in os.listdir(dst_dir):             # files the teammate deleted since last time
            if old.endswith(".py") and old not in files:
                os.remove(os.path.join(dst_dir, old))
        for f in files:
            res = subprocess.run(["git", "show", f"{ref}:{f}"], cwd=ROOT, capture_output=True, check=False)
            if res.returncode == 0:
                with open(os.path.join(dst_dir, f), "wb") as out:
                    out.write(res.stdout)
        info = _git("log", "-1", "--format=%h%n%ci%n%s", ref).stdout.splitlines() + ["", "", ""]
        version = {"commit": info[0], "date": info[1][:16], "subject": info[2], "files": files,
                   "updated": updated, "missing": [f for f in REQUIRED.get(branch, []) if f not in files]}
        with open(os.path.join(dst_dir, "REVISION"), "w") as out:
            out.write(f"{version['commit']} {version['date']} {version['subject']}\n")
        versions[branch] = version
        warn = f"  !! missing {', '.join(version['missing'])}" if version["missing"] else ""
        log(f"  {branch:8s} @ {version['commit']} ({version['date']}) {version['subject'][:60]}{warn}")
    return versions


if __name__ == "__main__":
    fetch("--fetch" in sys.argv)
