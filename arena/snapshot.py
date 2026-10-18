"""
Freeze the current splitter/ package as a named version, to A/B test changes on the same seeds:

    python -m arena.snapshot v3                # copies splitter/ -> arena/snapshots/splitter_v3/
    python -m arena.run --bot Splitter --opp Snap:v3 Apex ...   # new code vs frozen v3
    python -m arena.run --bot Snap:v3 ...                         # the frozen version alone
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    name = sys.argv[1]
    dst = os.path.join(ROOT, "arena", "snapshots", f"splitter_{name}")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(os.path.join(ROOT, "splitter"), dst, ignore=shutil.ignore_patterns("__pycache__"))
    print(f"snapshot saved: {dst}")
