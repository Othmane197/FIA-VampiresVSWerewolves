"""
Benchmark & Diagnostic Comparatif : Top 3 Algorithmes Apex VS Splitter de Mohamed
Analyse des forces, faiblesses et comportement selon la taille des cartes.
"""

import os
import sys
import time
import random
from typing import Dict, List, Tuple, Optional

# Forcer l'encodage utf-8 et stdout non bufférisé
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from game_state import Species
from game_engine import BoardState, chebyshev_dist
from apex_agent import ApexAlphaBetaAgent
from splitter.agent import SplitterAgent
from tournament_arena import (
    load_map_from_xml,
    generate_random_symmetric_map,
    COLOR_RESET,
    COLOR_RED,
    COLOR_BLUE,
    COLOR_BOLD,
    COLOR_CYAN,
    COLOR_YELLOW,
    COLOR_GRAY
)

class MohamedAgentAdapter:
    """Wrapper pour interfacer le SplitterAgent de Mohamed avec notre arène."""
    def __init__(self, name: str = "Mohamed_Splitter", time_limit: float = 0.8):
        self.name = name
        self.agent = SplitterAgent(
            name=name,
            time_limit=time_limit,
            splits=True,
            search="mcts"
        )

    def reset(self):
        self.agent.reset()

    def compute_moves(self, state: BoardState, species: Species) -> List[Tuple[int, int, int, int, int]]:
        return self.agent.compute_moves_board(state, species)

def run_diagnostic_match(
    agent_v, agent_w, initial_state: BoardState
) -> Dict:
    """
    Exécute un match et collecte des métriques diagnostiques approfondies :
    - Vainqueur
    - Nombre de tours
    - Effectif final
    - Évolution des groupes (scission)
    - Captures humaines respectives
    """
    state = initial_state.clone()
    current_species = Species.VAMPIRE

    v_moves_times = []
    w_moves_times = []
    v_group_counts = []
    w_group_counts = []

    init_humans = sum(cnt for _, cnt in state.get_humans())

    start_match_time = time.time()

    while True:
        over, winner = state.is_game_over()
        if over:
            v_cnt = state.get_species_total(Species.VAMPIRE)
            w_cnt = state.get_species_total(Species.WEREWOLF)
            winner_name = "NUL"
            if winner == Species.VAMPIRE:
                winner_name = agent_v.name
            elif winner == Species.WEREWOLF:
                winner_name = agent_w.name

            rem_humans = sum(cnt for _, cnt in state.get_humans())
            total_duration = time.time() - start_match_time

            return {
                "winner": winner_name,
                "winner_species": winner,
                "turns": state.turn_count,
                "v_units": v_cnt,
                "w_units": w_cnt,
                "v_player": agent_v.name,
                "w_player": agent_w.name,
                "duration": total_duration,
                "avg_v_time": sum(v_moves_times) / max(1, len(v_moves_times)),
                "avg_w_time": sum(w_moves_times) / max(1, len(w_moves_times)),
                "avg_v_groups": sum(v_group_counts) / max(1, len(v_group_counts)),
                "avg_w_groups": sum(w_group_counts) / max(1, len(w_group_counts)),
                "max_v_groups": max(v_group_counts) if v_group_counts else 1,
                "max_w_groups": max(w_group_counts) if w_group_counts else 1,
                "remaining_humans": rem_humans,
                "consumed_humans": init_humans - rem_humans,
            }

        active_agent = agent_v if current_species == Species.VAMPIRE else agent_w
        our_groups = state.get_species_groups(current_species)

        if current_species == Species.VAMPIRE:
            v_group_counts.append(len(our_groups))
        else:
            w_group_counts.append(len(our_groups))

        t0 = time.perf_counter()
        moves = active_agent.compute_moves(state, current_species)
        elapsed = time.perf_counter() - t0

        if current_species == Species.VAMPIRE:
            v_moves_times.append(elapsed)
        else:
            w_moves_times.append(elapsed)

        valid, reason = state.validate_moves(moves, current_species)
        if not valid:
            disq_winner = agent_w.name if current_species == Species.VAMPIRE else agent_v.name
            return {
                "winner": disq_winner,
                "winner_species": Species.WEREWOLF if current_species == Species.VAMPIRE else Species.VAMPIRE,
                "turns": state.turn_count,
                "v_units": 0 if current_species == Species.VAMPIRE else state.get_species_total(Species.VAMPIRE),
                "w_units": 0 if current_species == Species.WEREWOLF else state.get_species_total(Species.WEREWOLF),
                "v_player": agent_v.name,
                "w_player": agent_w.name,
                "duration": time.time() - start_match_time,
                "error": f"Disqualification de {active_agent.name}: {reason}"
            }

        state = state.apply_moves(moves, current_species, deterministic=False)
        current_species = Species.WEREWOLF if current_species == Species.VAMPIRE else Species.VAMPIRE

def run_suite():
    # 1. Définition des 3 algorithmes Apex
    apex_time_budget = 0.45
    mohamed_time_budget = 0.45

    apex_variants = [
        ("Apex_VOR_QS (Champion #1)", ApexAlphaBetaAgent(
            name="Apex_VOR_QS", max_time_seconds=apex_time_budget,
            enable_foraging_yield=False, enable_voronoi=True, enable_quiescence=True
        )),
        ("Apex_v2_All (Vice-Champion #2)", ApexAlphaBetaAgent(
            name="Apex_v2_All", max_time_seconds=apex_time_budget,
            enable_foraging_yield=True, enable_voronoi=True, enable_quiescence=True
        )),
        ("Apex_OFR_QS (Top Dueliste #3)", ApexAlphaBetaAgent(
            name="Apex_OFR_QS", max_time_seconds=apex_time_budget,
            enable_foraging_yield=True, enable_voronoi=False, enable_quiescence=True
        )),
    ]

    mohamed = MohamedAgentAdapter(name="Mohamed_Splitter", time_limit=mohamed_time_budget)

    # 2. Pool de cartes : Petite, Moyenne, Grande Officielle, Très Grande
    maps = []
    maps.append(("Petite_6x9", "Petite", generate_random_symmetric_map(rows=6, cols=9, start_units=6, num_pairs=2, seed=101)))
    maps.append(("Carree_10x10", "Petite/Moyenne", generate_random_symmetric_map(rows=10, cols=10, start_units=8, num_pairs=3, seed=202)))
    if os.path.exists("testmap.xml"):
        maps.append(("Officielle_15x29", "Grande", load_map_from_xml("testmap.xml")))
    else:
        maps.append(("Grande_15x29", "Grande", generate_random_symmetric_map(rows=15, cols=29, start_units=10, num_pairs=5, seed=303)))
    maps.append(("Geante_25x25", "Très Grande", generate_random_symmetric_map(rows=25, cols=25, start_units=12, num_pairs=7, seed=404)))

    print("=" * 95, flush=True)
    print(f"{COLOR_BOLD}🔥 BANC D'ESSAI COMPARATIF : TOP 3 APEX VS SPLITTER (MOHAMED) 🔥{COLOR_RESET}", flush=True)
    print(f"Budget par coup : Apex = {apex_time_budget}s | Mohamed = {mohamed_time_budget}s", flush=True)
    print(f"Cartes testées : {[m[0] for m in maps]}", flush=True)
    print("=" * 95, flush=True)

    all_results = []

    for algo_label, apex_agent in apex_variants:
        print(f"\n{COLOR_CYAN}══════════════════════════════════════════════════════════════════════════════{COLOR_RESET}", flush=True)
        print(f"{COLOR_BOLD}🎯 ÉVALUATION DE : {algo_label}{COLOR_RESET}", flush=True)
        print(f"{COLOR_CYAN}══════════════════════════════════════════════════════════════════════════════{COLOR_RESET}", flush=True)

        for map_name, map_cat, base_state in maps:
            # Match 1 : Apex (Vampires) vs Mohamed (Loups)
            apex_agent.transposition_table.clear()
            mohamed.reset()
            res1 = run_diagnostic_match(apex_agent, mohamed, base_state)
            res1["map_name"] = map_name
            res1["map_category"] = map_cat
            res1["algo_tested"] = apex_agent.name
            res1["side"] = "Aller (Apex=V)"
            all_results.append(res1)

            res_color = COLOR_RED if res1["winner"] == apex_agent.name else (COLOR_BLUE if res1["winner"] == mohamed.name else COLOR_YELLOW)
            print(f"  [{map_cat:<11}] {map_name:<16} | Aller (V) : {res_color}{res1['winner']:<17}{COLOR_RESET} | {res1['turns']:2d} tours ({res1['duration']:.1f}s) | V={res1['v_units']} vs W={res1['w_units']} | Grps: V={res1.get('avg_v_groups', 1):.1f} vs W={res1.get('avg_w_groups', 1):.1f}", flush=True)

            # Match 2 : Mohamed (Vampires) vs Apex (Loups)
            apex_agent.transposition_table.clear()
            mohamed.reset()
            res2 = run_diagnostic_match(mohamed, apex_agent, base_state)
            res2["map_name"] = map_name
            res2["map_category"] = map_cat
            res2["algo_tested"] = apex_agent.name
            res2["side"] = "Retour (Apex=W)"
            all_results.append(res2)

            res_color2 = COLOR_RED if res2["winner"] == apex_agent.name else (COLOR_BLUE if res2["winner"] == mohamed.name else COLOR_YELLOW)
            print(f"  [{map_cat:<11}] {map_name:<16} | Retour (W): {res_color2}{res2['winner']:<17}{COLOR_RESET} | {res2['turns']:2d} tours ({res2['duration']:.1f}s) | V={res2['v_units']} vs W={res2['w_units']} | Grps: V={res2.get('avg_v_groups', 1):.1f} vs W={res2.get('avg_w_groups', 1):.1f}", flush=True)

    # Synthèse globale par catégorie de carte et par algorithme
    print("\n" + "=" * 95, flush=True)
    print(f"{COLOR_BOLD}                     SYNTHÈSE GLOBALE DES PERFORMANCES                          {COLOR_RESET}", flush=True)
    print("=" * 95, flush=True)

    for algo_label, apex_agent in apex_variants:
        algo_matches = [r for r in all_results if r["algo_tested"] == apex_agent.name]
        wins = sum(1 for r in algo_matches if r["winner"] == apex_agent.name)
        losses = sum(1 for r in algo_matches if r["winner"] == mohamed.name)
        draws = sum(1 for r in algo_matches if r["winner"] == "NUL")

        small_matches = [r for r in algo_matches if r["map_category"] in ("Petite", "Petite/Moyenne")]
        small_wins = sum(1 for r in small_matches if r["winner"] == apex_agent.name)

        large_matches = [r for r in algo_matches if r["map_category"] in ("Grande", "Très Grande")]
        large_wins = sum(1 for r in large_matches if r["winner"] == apex_agent.name)

        print(f"\n📊 {COLOR_BOLD}{algo_label}{COLOR_RESET}:")
        print(f"   • Total : {wins}V - {losses}D - {draws}N (Winrate: {wins/len(algo_matches)*100:.1f}%)")
        print(f"   • Petites cartes  : {small_wins}/{len(small_matches)} victoires ({small_wins/len(small_matches)*100:.1f}%)")
        print(f"   • Grandes cartes  : {large_wins}/{len(large_matches)} victoires ({large_wins/len(large_matches)*100:.1f}%)")

    import json
    with open("benchmark_top3_vs_mohamed_results.json", "w", encoding="utf-8") as f:
        clean_results = []
        for r in all_results:
            rc = dict(r)
            if "winner_species" in rc and rc["winner_species"] is not None:
                rc["winner_species"] = str(rc["winner_species"])
            clean_results.append(rc)
        json.dump(clean_results, f, indent=2)
    print(f"\n💾 Résultats détaillés exportés dans benchmark_top3_vs_mohamed_results.json", flush=True)

    return all_results

if __name__ == "__main__":
    run_suite()
