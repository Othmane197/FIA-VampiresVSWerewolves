"""
Faster benchmarks: keep only the game slots that can tell configurations apart.

A paired comparison learns nothing from a game that every configuration wins (or loses) the same
way: against TacticalSplitter we always win, on big village maps Apex always loses. This tool
reads a stored multi-configuration run (arena.run --bot A B C ...), measures for every
(opponent, map) slot how often configurations DISAGREE with the first one on the same game, and
keeps the slots with the most disagreement per ply of play until `--coverage` of the total
disagreement is reached.

    python tools/informative_slots.py arena/results/<run>.csv [more.csv] --coverage 0.9 --out arena/slots/tuning.json
    python -m arena.run --bot Splitter "Splitter:c=0.8" --slots arena/slots/tuning.json --time 0.25

Caveats (chapter 07.8): the result then describes CONTESTED games, not the full panel (use the full
panel to report absolute win rates); and the slot list must be regenerated when the bot changes a
lot (a slot that was always won may become contested).
"""
import argparse
import csv
import json
import os
from collections import defaultdict


def slot_information(paths):
    """{(opp, map): [games, disagreement sum, plies sum]} from stored runs (first bot = reference)."""
    slot = defaultdict(lambda: [0, 0.0, 0.0])
    for path in paths:
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            continue
        ref = rows[0]["bot"]
        by_game = defaultdict(list)
        for r in rows:
            if int(r["our_timeouts"]) or int(r["opp_problems"]):
                continue                        # a sleep or a crash, not a game result
            by_game[(r["opp"], r["map"], r["side"], r["first"], r["seed"])].append(r)
        for (opp, mp, *_), rs in by_game.items():
            base = [float(r["score"]) for r in rs if r["bot"] == ref]
            if not base or len(rs) < 2:
                continue
            s = slot[(opp, mp)]
            s[0] += 1
            s[1] += sum(1 for r in rs if float(r["score"]) != base[0]) / len(rs)
            s[2] += sum(int(r["plies"]) for r in rs) / len(rs)
    return slot


def select(slot, coverage: float):
    """Slots sorted by disagreement per ply, kept until `coverage` of the disagreement is reached."""
    total_info = sum(v[1] for v in slot.values()) or 1.0
    total_cost = sum(v[2] for v in slot.values()) or 1.0
    ranked = sorted(slot.items(), key=lambda kv: -(kv[1][1] / max(kv[1][2], 1.0)))
    keep, info, cost = [], 0.0, 0.0
    for (opp, mp), (_, dis, plies) in ranked:
        if info / total_info >= coverage:
            break
        keep.append([opp, mp])
        info += dis
        cost += plies
    return keep, info / total_info, cost / total_cost


def main():
    """Command line: write the informative slots of the given runs as JSON."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="+", help="stored arena runs with several bots (arena/results/*.csv)")
    ap.add_argument("--coverage", type=float, default=0.9, help="share of the disagreement to keep")
    ap.add_argument("--out", required=True, help="output JSON (e.g. arena/slots/tuning.json)")
    a = ap.parse_args()
    keep, info, cost = select(slot_information(a.csv), a.coverage)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump({"source": [os.path.basename(p) for p in a.csv], "coverage": round(info, 3),
                   "cost_share": round(cost, 3), "slots": keep}, f, indent=1)
    print(f"{len(keep)} slots keep {100 * info:.0f}% of the disagreement for {100 * cost:.0f}% of the plies "
          f"-> {a.out}")


if __name__ == "__main__":
    main()
