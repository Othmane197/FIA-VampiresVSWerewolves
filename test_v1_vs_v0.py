"""
Validation Expérimentale : Apex V1 (Split Intelligent & Autonomie) VS Apex V0 (Baseline)
Teste directement le gain de performance sur 4 cartes clés (Aller & Retour).
"""

import sys
import os
import time
import json
from typing import Dict, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from game_state import Species
from game_engine import BoardState
from apex_agent import ApexAlphaBetaAgent as ApexV1
from apex_agent_v0 import ApexAlphaBetaAgent as ApexV0
from tournament_arena import (
    load_map_from_xml,
    generate_random_symmetric_map,
    play_match_visual,
    COLOR_RESET,
    COLOR_RED,
    COLOR_BLUE,
    COLOR_BOLD,
    COLOR_CYAN,
    COLOR_YELLOW
)

def run_match_pair(name_v1, agent_v1, name_v0, agent_v0, map_name, map_cat, base_state):
    """Joue un match Aller et un match Retour."""
    results = []

    # Match Aller: V1 = Vampires, V0 = Werewolves
    agent_v1.transposition_table.clear()
    agent_v0.transposition_table.clear()
    t0 = time.time()
    w1, t1, v1_cnt, v0_cnt = play_match_visual(agent_v1, agent_v0, base_state, visualize=False)
    d1 = time.time() - t0
    results.append({
        "map": map_name,
        "cat": map_cat,
        "side": "Aller (V1=V)",
        "winner": w1,
        "turns": t1,
        "v1_units": v1_cnt,
        "v0_units": v0_cnt,
        "duration": d1
    })

    # Match Retour: V0 = Vampires, V1 = Werewolves
    agent_v1.transposition_table.clear()
    agent_v0.transposition_table.clear()
    t0 = time.time()
    w2, t2, v0_cnt2, v1_cnt2 = play_match_visual(agent_v0, agent_v1, base_state, visualize=False)
    d2 = time.time() - t0
    results.append({
        "map": map_name,
        "cat": map_cat,
        "side": "Retour (V1=W)",
        "winner": w2,
        "turns": t2,
        "v1_units": v1_cnt2,
        "v0_units": v0_cnt2,
        "duration": d2
    })

    return results

def main():
    time_budget = 0.45

    v1 = ApexV1(name="Apex_V1", max_time_seconds=time_budget, enable_voronoi=True, enable_quiescence=True)
    v0 = ApexV0(name="Apex_V0", max_time_seconds=time_budget, enable_voronoi=True, enable_quiescence=True)

    maps = []
    maps.append(("Petite_6x9", "Petite", generate_random_symmetric_map(rows=6, cols=9, start_units=6, num_pairs=2, seed=101)))
    maps.append(("Carree_10x10", "Moyenne", generate_random_symmetric_map(rows=10, cols=10, start_units=8, num_pairs=3, seed=202)))
    if os.path.exists("testmap.xml"):
        maps.append(("Officielle_15x29", "Grande", load_map_from_xml("testmap.xml")))
    else:
        maps.append(("Grande_15x29", "Grande", generate_random_symmetric_map(rows=15, cols=29, start_units=10, num_pairs=5, seed=303)))
    maps.append(("Geante_25x25", "Très Grande", generate_random_symmetric_map(rows=25, cols=25, start_units=12, num_pairs=7, seed=404)))

    print("=" * 85, flush=True)
    print(f"{COLOR_BOLD}⚔️  DUEL DIRECT : APEX V1 (Nouvelle Version) VS APEX V0 (Baseline) ⚔️{COLOR_RESET}", flush=True)
    print(f"Budget par coup : {time_budget}s | Cartes : {[m[0] for m in maps]}", flush=True)
    print("=" * 85, flush=True)

    all_res = []
    for map_name, map_cat, base_state in maps:
        res = run_match_pair("Apex_V1", v1, "Apex_V0", v0, map_name, map_cat, base_state)
        for r in res:
            all_res.append(r)
            win_color = COLOR_RED if r["winner"] == "Apex_V1" else (COLOR_BLUE if r["winner"] == "Apex_V0" else COLOR_YELLOW)
            print(f"  [{r['cat']:<11}] {r['map']:<16} | {r['side']:<14} : {win_color}{r['winner']:<10}{COLOR_RESET} | {r['turns']:2d} tours ({r['duration']:.1f}s) | V1={r['v1_units']} vs V0={r['v0_units']}", flush=True)

    v1_wins = sum(1 for r in all_res if r["winner"] == "Apex_V1")
    v0_wins = sum(1 for r in all_res if r["winner"] == "Apex_V0")
    draws = sum(1 for r in all_res if r["winner"] == "NUL")

    print("\n" + "=" * 85, flush=True)
    print(f"{COLOR_BOLD}BILAN V1 vs V0 : Victoires V1 = {v1_wins} | Victoires V0 = {v0_wins} | Nuls = {draws}{COLOR_RESET}", flush=True)
    print("=" * 85, flush=True)

if __name__ == "__main__":
    main()
