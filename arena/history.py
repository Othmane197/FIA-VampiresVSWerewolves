"""
Browse the stored results of every arena run and server match.

    python -m arena.history                 # last 20 runs (arena/results/history.csv)
    python -m arena.history --bot Splitter  # only rows whose bot contains "Splitter"
    python -m arena.history --comparisons   # paired comparisons (arena/results/comparisons.csv)
    python -m arena.history --last 50
"""
import argparse
import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY = os.path.join(ROOT, "arena", "results", "history.csv")
COMPARISONS = os.path.join(ROOT, "arena", "results", "comparisons.csv")


def main():
    """Command line: print the selected stored results as a table."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bot", default="")
    ap.add_argument("--last", type=int, default=20)
    ap.add_argument("--comparisons", action="store_true")
    a = ap.parse_args()
    path = COMPARISONS if a.comparisons else HISTORY
    if not os.path.exists(path):
        print(f"no results yet ({path})")
        return
    with open(path, newline="") as f:
        rows = [r for r in csv.DictReader(f) if a.bot in r.get("bot", "")]
    rows = rows[-a.last:]
    if a.comparisons:
        print(f"{'run':24s} {'bot':38s} {'vs':16s} {'scope':18s} {'delta':>7s} {'se':>5s} {'n':>5s}")
        for r in rows:
            print(f"{r['run'][:24]:24s} {r['bot'][:38]:38s} {r['reference'][:16]:16s} {r['scope'][:18]:18s} "
                  f"{float(r['delta']):+7.1f} {float(r['se']):5.1f} {r['games']:>5s}")
    else:
        print(f"{'run':24s} {'bot':38s} {'score':>6s} {'se':>5s} {'games':>6s} {'time':>5s} {'prob':>4s}  opponents / maps")
        for r in rows:
            print(f"{r['run'][:24]:24s} {r['bot'][:38]:38s} {float(r['score']):6.1f} {float(r['se']):5.1f} "
                  f"{r['games_played']:>6s} {r['time']:>5s} {r['problems']:>4s}  {r['opponents'][:40]} / {r['maps']}")


if __name__ == "__main__":
    main()
