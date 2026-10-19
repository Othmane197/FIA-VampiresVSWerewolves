"""
Stage-S1 report: how well does the opponent model observe and predict each bot?

    python -m arena.run --bot Splitter --maps all --games 1 --time 0.15 --save-all-logs
    python tools/opponent_report.py arena/results/traces/<run>      [--params default|trained]

For every bot found in the recorded games (each player is studied as "the opponent"):
  * reconstruction: agreement of the features rebuilt from boards (observe.reconstruct_flows)
    with the features of the TRUE moves, per feature;
  * next-cell prediction of every enemy group, top-1 / top-3 accuracy, against baselines:
    uniform, greedy (walk to the nearest convertible house, else to our nearest group) and our
    own planner's top plan for that bot;
  * style HMM: average log-likelihood gain of its feature predictions over the base rates,
    and the average style belief at the end of the games.
"""
import glob
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from arena.referee import state_from_dict
from splitter.observe import FEATURES, features_from_flows, reconstruct_flows
from splitter.opponent_model import EXPERTS, MODES, GoalRecognizer, PolicyHMM, StyleHMM, default_params, phase_of
from splitter.planner import generate_plans
from splitter.rules import cheb


def _main_dest(flows_from, pos, size):
    parts = list(flows_from.get(pos, []))
    stayed = size - sum(n for _, n in parts)
    if stayed > 0:
        parts.append((pos, stayed))
    return max(parts, key=lambda x: x[1])[0] if parts else pos


def _greedy_step(state, mover, pos, size):
    houses = [hp for hp, h in state.humans.items() if h <= size]
    targets = houses or list(state.groups[1 - mover])
    if not targets:
        return pos
    t = min(targets, key=lambda c: cheb(pos, c))
    return min([pos] + list(state.nbrs[pos]), key=lambda c: (cheb(c, t), c))


def _planner_steps(state, mover):
    plans = generate_plans(state, mover)
    if not plans:
        return {}
    steps = {}
    for x1, y1, n, x2, y2 in plans[0].moves:
        cur = steps.get((x1, y1))
        if cur is None or n > cur[1]:
            steps[(x1, y1)] = ((x2, y2), n)
    return {p: d for p, (d, _) in steps.items()}


def analyse(folder, params):
    agg = defaultdict(lambda: defaultdict(float))
    beliefs = defaultdict(lambda: [0.0] * len(MODES))
    experts = defaultdict(lambda: [0.0] * len(EXPERTS))
    for path in glob.glob(os.path.join(folder, "*.json")):
        with open(path) as f:
            rec = json.load(f)
        rows, cols, max_ply = rec["rows"], rec["cols"], rec["max_ply"]
        models = {}
        for s in (0, 1):
            g = GoalRecognizer()
            models[s] = (StyleHMM(params), g, PolicyHMM(g))
        for step in rec["trace"]:
            mover = step["side"]
            name = rec["names"][mover]
            a = agg[name]
            mid = state_from_dict(step["before"], rows, cols, max_ply)
            after = state_from_dict(step["after"], rows, cols, max_ply)
            moves = [tuple(m) for m in step["moves"]]
            true_flows = [((m[0], m[1]), (m[3], m[4]), m[2]) for m in moves]
            truth = features_from_flows(mid, mover, true_flows).vector()
            rflows = reconstruct_flows(mid, after, mover)
            recon = features_from_flows(mid, mover, rflows).vector()
            a["turns"] += 1
            for f, (fname, _) in enumerate(FEATURES):
                a["agree_" + fname] += truth[f] == recon[f]
            a["agree_all"] += truth == recon

            style, goals, policy = models[mover]
            # --- prediction BEFORE seeing this turn
            pred_feats = style.predict_features(phase_of(mid))
            gp = goals.predict(mid, mover)
            dists = policy.expert_dists(mid, mover)
            mix = policy.mixture(dists)
            actual_steps = {}
            plan_steps = _planner_steps(mid, mover) if a["turns"] % 3 == 0 else None
            flows_from = defaultdict(list)
            for s, d, n in true_flows:
                flows_from[s].append((d, n))
            for pos, size in mid.groups[mover].items():
                actual = _main_dest(flows_from, pos, size)
                actual_steps[pos] = actual
                mranked = sorted(mix[pos], key=lambda c: -mix[pos][c])
                a["mix_top1"] += mranked[0] == actual
                a["mix_top3"] += actual in mranked[:3]
                probs = gp[pos].step_probs
                ranked = sorted(probs, key=lambda c: -probs[c])
                a["groups"] += 1
                a["model_top1"] += ranked[0] == actual
                a["model_top3"] += actual in ranked[:3]
                a["uniform_top1"] += 1.0 / (1 + len(mid.nbrs[pos]))
                a["greedy_top1"] += _greedy_step(mid, mover, pos, size) == actual
                if plan_steps is not None:
                    a["planner_n"] += 1
                    a["planner_top1"] += plan_steps.get(pos, pos) == actual
            import math
            base = params.get("marginal", default_params()["marginal"])
            ll_m = sum(math.log(max(pred_feats[f][recon[f]], 1e-9)) for f in range(len(FEATURES)))
            ll_b = sum(math.log(max(base[f][recon[f]], 1e-9)) for f in range(len(FEATURES)))
            a["llr"] += ll_m - ll_b
            # --- learn from it (with the RECONSTRUCTED observation, as in a real game)
            style.update(recon, phase_of(mid))
            goals.update(mid, after, mover, rflows)
            policy.update(dists, actual_steps)
        for s in (0, 1):
            name = rec["names"][s]
            b = models[s][0].belief
            for e in range(len(EXPERTS)):
                experts[name][e] += models[s][2].belief[e]
            agg[name]["games"] += 1
            for z in range(len(MODES)):
                beliefs[name][z] += b[z]
    return agg, beliefs, experts


def main():
    folder = sys.argv[1]
    which = sys.argv[sys.argv.index("--params") + 1] if "--params" in sys.argv else "trained"
    if which == "default":
        params = default_params()
    else:
        from splitter.opponent_model import load_params
        params = load_params()
    agg, _beliefs, experts = analyse(folder, params)
    print(f"params: {which}")
    print(f"{'bot':18s} {'turns':>6s} {'recon all':>9s} split attack head conv | "
          f"{'goal top1':>9s} {'top3':>4s} | {'POLICY-HMM top1':>15s} top3 | greedy planner uniform | llr/turn | experts")
    for name in sorted(agg):
        a = agg[name]
        t, g = max(1, a["turns"]), max(1, a["groups"])
        ng = max(1, a["games"])
        ex = " ".join(f"{m[:4]}={experts[name][e] / ng:.2f}" for e, m in enumerate(EXPERTS))
        print(f"{name:18s} {int(a['turns']):6d} {100 * a['agree_all'] / t:8.1f}% "
              f"{100 * a['agree_split'] / t:5.0f} {100 * a['agree_attack'] / t:6.0f} "
              f"{100 * a['agree_heading'] / t:4.0f} {100 * a['agree_converted'] / t:4.0f} | "
              f"{100 * a['model_top1'] / g:8.1f}% {100 * a['model_top3'] / g:3.0f}% | "
              f"{100 * a['mix_top1'] / g:14.1f}% {100 * a['mix_top3'] / g:3.0f}% | "
              f"{100 * a['greedy_top1'] / g:5.1f}% {100 * a['planner_top1'] / max(1, a['planner_n']):6.1f}% "
              f"{100 * a['uniform_top1'] / g:6.1f}% | {a['llr'] / t:7.3f} | {ex}")


if __name__ == "__main__":
    main()
