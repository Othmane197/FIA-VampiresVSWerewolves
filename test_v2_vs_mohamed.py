"""
Duel Élite : Apex V2 (Amélioré) VS Mohamed Splitter (MCTS)
Vérification des progrès contre l'algorithme adverse de référence.
"""

import sys
import os
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from game_state import Species
from game_engine import BoardState
from apex_agent import ApexAlphaBetaAgent as ApexV2
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

def run_match_pair(agent_apex, agent_mohamed, map_name, map_cat, base_state):
    results = []

    # Aller: Apex = Vampires, Mohamed = Werewolves
    agent_apex.transposition_table.clear()
    agent_mohamed.reset()
    t0 = time.time()
    w1, t1, v_cnt, w_cnt = play_match_visual(agent_apex, agent_mohamed, base_state, visualize=False)
    d1 = time.time() - t0
    results.append((map_name, map_cat, "Aller (Apex=V)", w1, t1, v_cnt, w_cnt, d1))

    # Retour: Mohamed = Vampires, Apex = Werewolves
    agent_apex.transposition_table.clear()
    agent_mohamed.reset()
    t0 = time.time()
    w2, t2, v_cnt2, w_cnt2 = play_match_visual(agent_mohamed, agent_apex, base_state, visualize=False)
    d2 = time.time() - t0
    results.append((map_name, map_cat, "Retour (Apex=W)", w2, t2, w_cnt2, v_cnt2, d2))

    return results

def main():
    time_budget = 0.45

    apex = ApexV2(name="Apex_V2", max_time_seconds=time_budget, enable_voronoi=True, enable_quiescence=True)
    mohamed = MohamedAgentAdapter(name="Mohamed_Splitter", time_limit=time_budget)

    maps = []
    maps.append(("Carree_10x10", "Moyenne", generate_random_symmetric_map(rows=10, cols=10, start_units=8, num_pairs=3, seed=202)))
    if os.path.exists("testmap.xml"):
        maps.append(("Officielle_15x29", "Grande", load_map_from_xml("testmap.xml")))
    else:
        maps.append(("Grande_15x29", "Grande", generate_random_symmetric_map(rows=15, cols=29, start_units=10, num_pairs=5, seed=303)))
    maps.append(("Geante_25x25", "Très Grande", generate_random_symmetric_map(rows=25, cols=25, start_units=12, num_pairs=7, seed=404)))

    print("=" * 85, flush=True)
    print(f"{COLOR_BOLD}🔥 DUEL DE VALIDATION : APEX V2 (NOUVEAU) VS MOHAMED SPLITTER 🔥{COLOR_RESET}", flush=True)
    print(f"Budget par coup : {time_budget}s", flush=True)
    print("=" * 85, flush=True)

    all_res = []
    for m_name, m_cat, state in maps:
        res = run_match_pair(apex, mohamed, m_name, m_cat, state)
        for r in res:
            all_res.append(r)
            win_color = COLOR_RED if r[3] == "Apex_V2" else (COLOR_BLUE if r[3] == "Mohamed_Splitter" else COLOR_YELLOW)
            print(f"  [{r[1]:<11}] {r[0]:<16} | {r[2]:<14} : {win_color}{r[3]:<16}{COLOR_RESET} | {r[4]:2d} tours ({r[7]:.1f}s) | Apex={r[5]} vs Moh={r[6]}", flush=True)

    apex_wins = sum(1 for r in all_res if r[3] == "Apex_V2")
    moh_wins = sum(1 for r in all_res if r[3] == "Mohamed_Splitter")
    draws = sum(1 for r in all_res if r[3] == "NUL")

    print("\n" + "=" * 85, flush=True)
    print(f"{COLOR_BOLD}BILAN V2 vs MOHAMED : Victoires Apex_V2 = {apex_wins} | Victoires Mohamed = {moh_wins} | Nuls = {draws}{COLOR_RESET}", flush=True)
    print("=" * 85, flush=True)

if __name__ == "__main__":
    main()
