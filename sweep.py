"""Run several evaluation configurations on the same games and print one line each.
   python3 sweep.py out.txt seed0 games 'name:{json cfg}' ...   (see the __main__ block)"""
import json
import sys
from benchmark import run_benchmark


def main(out, seed0, games, specs):
    with open(out, "a") as f:
        for spec in specs:
            name, cfg = spec.split(":", 1)
            cfg = json.loads(cfg)
            r = run_benchmark(cfg, games_per_side=games, workers=2, seed0=seed0)
            p, se, n = r.score()
            per = {k: 100 * r.score(v)[0] for k, v in r.by(0).items()}
            draws = sum(1 for row in r.rows if row[3] == 0.5)
            line = (f"{name:<22} seed0={seed0} {100*p:5.1f}% (n={n}, draws {draws}, problems {r.problems}, "
                    f"slowest {1000*r.slowest:.0f} ms)  " + "  ".join(f"{k} {v:.0f}" for k, v in per.items()))
            print(line, flush=True)
            f.write(line + "\n")
            f.flush()


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4:])
