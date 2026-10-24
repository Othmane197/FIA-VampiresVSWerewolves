"""
Banc de Validation Multi-Générations : Apex V2 vs Apex V1 vs Apex V0
Mesure l'évolution des performances et de la récolte sur grandes cartes.
"""

import sys
import os
import time
from typing import Dict, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from game_state import Species
from game_engine import BoardState
from apex_agent import ApexAlphaBetaAgent as ApexV2
from apex_agent_v1 import ApexAlphaBetaAgent as ApexV1
from apex_agent_v0 import ApexAlphaBetaAgent as ApexV0
from splitter.agent import SplitterAgent
from face_mohamed_agent import MohamedAgentAdapter
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

def run_duel(agent_a, agent_b, map_name, map_cat, base_state):
    """Joue Aller et Retour."""
    # Aller
    agent_a.transposition_table.clear()
    agent_b.transposition_table.clear()
    t0 = time.time()
    w1, t1, a_cnt, b_cnt = play_match_visual(agent_a, agent_b, base_state, visualize=False)
    d1 = time.time() - t0
    res1 = (map_name, map_cat, "Aller", w1, t1, a_cnt, b_cnt, d1)

    # Retour
    agent_a.transposition_table.clear()
    agent_b.transposition_table.clear()
    t0 = time.time()
    w2, t2, b_cnt2, a_cnt2 = play_match_visual(agent_b, agent_a, base_state, visualize=False)
    d2 = time.time() - t0
    res2 = (map_name, map_cat, "Retour", w2, t2, a_cnt2, b_cnt2, d2)

    return res1, res2

def main():
    time_budget = 0.45

    v2 = ApexV2(name="Apex_V2", max_time_seconds=time_budget, enable_voronoi=True, enable_quiescence=True)
    v1 = ApexV1(name="Apex_V1", max_time_seconds=time_budget, enable_voronoi=True, enable_quiescence=True)
    v0 = ApexV0(name="Apex_V0", max_time_seconds=time_budget, enable_voronoi=True, enable_quiescence=True)

    maps = []
    maps.append(("Carree_10x10", "Moyenne", generate_random_symmetric_map(rows=10, cols=10, start_units=8, num_pairs=3, seed=202)))
    if os.path.exists("testmap.xml"):
        maps.append(("Officielle_15x29", "Grande", load_map_from_xml("testmap.xml")))
    else:
        maps.append(("Grande_15x29", "Grande", generate_random_symmetric_map(rows=15, cols=29, start_units=10, num_pairs=5, seed=303)))
    maps.append(("Geante_25x25", "Très Grande", generate_random_symmetric_map(rows=25, cols=25, start_units=12, num_pairs=7, seed=404)))

    # --- SÉRIE 1 : V2 VS V1 ---
    print("=" * 85, flush=True)
    print(f"{COLOR_BOLD}🏆 SÉRIE 1 : APEX V2 (Longue Portée & Pression) VS APEX V1 (Split Initial) 🏆{COLOR_RESET}", flush=True)
    print("=" * 85, flush=True)
    v2_v1_results = []
    for m_name, m_cat, state in maps:
        r1, r2 = run_duel(v2, v1, m_name, m_cat, state)
        for r in (r1, r2):
            v2_v1_results.append(r)
            col = COLOR_RED if r[3] == "Apex_V2" else (COLOR_BLUE if r[3] == "Apex_V1" else COLOR_YELLOW)
            print(f"  [{r[1]:<11}] {r[0]:<16} | {r[2]:<6} : {col}{r[3]:<10}{COLOR_RESET} | {r[4]:2d} tours ({r[7]:.1f}s) | V2={r[5]} vs V1={r[6]}", flush=True)

    v2_wins = sum(1 for r in v2_v1_results if r[3] == "Apex_V2")
    v1_wins = sum(1 for r in v2_v1_results if r[3] == "Apex_V1")
    draws1 = sum(1 for r in v2_v1_results if r[3] == "NUL")
    print(f"--> Score V2 vs V1 : V2={v2_wins}V | V1={v1_wins}V | Nuls={draws1}", flush=True)

    # --- SÉRIE 2 : V2 VS V0 ---
    print("\n" + "=" * 85, flush=True)
    print(f"{COLOR_BOLD}🏆 SÉRIE 2 : APEX V2 (Nouvelle Génération) VS APEX V0 (Baseline Début) 🏆{COLOR_RESET}", flush=True)
    print("=" * 85, flush=True)
    v2_v0_results = []
    for m_name, m_cat, state in maps:
        r1, r2 = run_duel(v2, v0, m_name, m_cat, state)
        for r in (r1, r2):
            v2_v0_results.append(r)
            col = COLOR_RED if r[3] == "Apex_V2" else (COLOR_BLUE if r[3] == "Apex_V0" else COLOR_YELLOW)
            print(f"  [{r[1]:<11}] {r[0]:<16} | {r[2]:<6} : {col}{r[3]:<10}{COLOR_RESET} | {r[4]:2d} tours ({r[7]:.1f}s) | V2={r[5]} vs V0={r[6]}", flush=True)

    v2_wins_v0 = sum(1 for r in v2_v0_results if r[3] == "Apex_V2")
    v0_wins = sum(1 for r in v2_v0_results if r[3] == "Apex_V0")
    draws2 = sum(1 for r in v2_v0_results if r[3] == "NUL")
    print(f"--> Score V2 vs V0 : V2={v2_wins_v0}V | V0={v0_wins}V | Nuls={draws2}", flush=True)

if __name__ == "__main__":
    main()
