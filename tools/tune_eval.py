"""
Fit the evaluation's constants to game outcomes (Texel-style tuning, as in chess engines).

    python -m arena.run --bot Splitter --maps all --games 1 --time 0.15 --save-all-logs      # train games
    python -m arena.run --bot Splitter --maps holdout --games 1 --time 0.15 --save-all-logs  # check games
    python tools/tune_eval.py --train arena/results/traces/<run1> [...] --check arena/results/traces/<run2>

Every recorded position (before each move) becomes one sample: x = evaluate(position, mover,
mover, plies left), y = 1 / 0.5 / 0 if the mover eventually won / drew / lost. The constants of
splitter.evaluate.EvalParams are fitted by coordinate descent on the mean log-loss of the TRAIN
games; the CHECK games (other maps, other seeds) tell whether the fit generalizes. Also prints a
calibration table (predicted vs observed win rate per decile).

The output is an arena spec ("Splitter:eval_discount=...") to test the fitted evaluation in
games, which is what decides (a better log-loss does not guarantee a stronger bot).
"""
import argparse
import glob
import json
import math
import os
import sys
from dataclasses import asdict, replace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from arena.referee import state_from_dict
from splitter.evaluate import DEFAULT_EVAL, EvalParams, evaluate

# coordinate-descent search space: (field, step, lower bound, upper bound)
# Only the calibration constants are fitted: fitting the risk terms too (contest discount,
# coin-flip exposure, domination bonus) improved the log-loss but LOST games (chapter 14: the
# recorded games come from a bot that avoids those risks, so the data cannot value them).
SPACE = [("discount", 0.02, 0.8, 0.99), ("k0", 1.0, 1.0, 15.0), ("k1", 2.0, 0.0, 30.0)]


def load_samples(folders, every: int = 2):
    """[(State, mover, result for the mover)] from recorded games (every `every`-th position)."""
    out = []
    for folder in folders:
        for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
            with open(path) as f:
                rec = json.load(f)
            winner = rec["winner"]
            for i, step in enumerate(rec["trace"]):
                if i % every:
                    continue
                st = state_from_dict(step["before"], rec["rows"], rec["cols"], rec["max_ply"])
                mover = step["side"]
                y = 0.5 if winner is None else (1.0 if winner == mover else 0.0)
                out.append((st, mover, y))
    return out


def log_loss(samples, ev: EvalParams) -> float:
    """Mean cross-entropy of evaluate() against the game results."""
    total = 0.0
    for st, mover, y in samples:
        p = min(max(evaluate(st, mover, mover, st.max_ply - st.ply, ev), 1e-4), 1 - 1e-4)
        total -= y * math.log(p) + (1 - y) * math.log(1 - p)
    return total / max(1, len(samples))


def calibration(samples, ev: EvalParams, bins: int = 10):
    """[(predicted mean, observed mean, count)] per probability decile."""
    cells = [[0.0, 0.0, 0] for _ in range(bins)]
    for st, mover, y in samples:
        p = evaluate(st, mover, mover, st.max_ply - st.ply, ev)
        c = cells[min(bins - 1, int(p * bins))]
        c[0] += p
        c[1] += y
        c[2] += 1
    return [(c[0] / c[2], c[1] / c[2], c[2]) for c in cells if c[2]]


def fit(samples, ev: EvalParams, rounds: int = 4, log=print) -> EvalParams:
    """Coordinate descent: try +-step on each constant, keep improvements, halve steps each round."""
    best = log_loss(samples, ev)
    steps = {name: step for name, step, _, _ in SPACE}
    for r in range(rounds):
        for name, _, lo, hi in SPACE:
            improved = True
            while improved:
                improved = False
                for sign in (1, -1):
                    v = getattr(ev, name) + sign * steps[name]
                    if not lo <= v <= hi:
                        continue
                    cand = replace(ev, **{name: round(v, 4)})
                    loss = log_loss(samples, cand)
                    if loss < best - 1e-5:
                        ev, best, improved = cand, loss, True
                        break
        log(f"  round {r + 1}: train log-loss {best:.4f}  {asdict(ev)}")
        steps = {k: v / 2 for k, v in steps.items()}
    return ev


def main():
    """Command line: fit on --train, report on --check, print the arena spec."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train", nargs="+", required=True, help="trace folders used for fitting")
    ap.add_argument("--check", nargs="*", default=[], help="trace folders used only for checking")
    ap.add_argument("--every", type=int, default=2, help="use every n-th position")
    ap.add_argument("--rounds", type=int, default=4)
    a = ap.parse_args()
    train = load_samples(a.train, a.every)
    check = load_samples(a.check, a.every) if a.check else []
    print(f"{len(train)} train positions, {len(check)} check positions")
    print(f"default: train {log_loss(train, DEFAULT_EVAL):.4f}"
          + (f"  check {log_loss(check, DEFAULT_EVAL):.4f}" if check else ""))
    ev = fit(train, DEFAULT_EVAL, a.rounds)
    print(f"fitted:  train {log_loss(train, ev):.4f}" + (f"  check {log_loss(check, ev):.4f}" if check else ""))
    for name, params in (("default", DEFAULT_EVAL), ("fitted", ev)):
        print(f"calibration ({name}, {'check' if check else 'train'} positions): predicted -> observed (n)")
        for p, y, n in calibration(check or train, params):
            print(f"   {p:5.2f} -> {y:5.2f}  ({n})")
    changed = {k: v for k, v in asdict(ev).items() if v != asdict(DEFAULT_EVAL)[k]}
    print("arena spec: Splitter:" + ",".join(f"eval_{k}={v}" for k, v in changed.items()))


if __name__ == "__main__":
    main()
