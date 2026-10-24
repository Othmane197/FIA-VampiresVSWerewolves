"""
Duel des Titans : 10 Matchs Alternés (Vampires <-> Werewolves)
Mohamed's Splitter (MCTS) VS Apex Champion (Alpha-Beta Minimax)
Strictly on Othmane branch - Mohamed branch is completely untouched.
"""

import sys
import time
import os
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from typing import List, Tuple
from game_state import Species
from game_engine import BoardState
from apex_agent import ApexAlphaBetaAgent
from splitter.agent import SplitterAgent
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

class MohamedAgentAdapter:
    """Wrapper to make Mohamed's SplitterAgent compatible with tournament_arena interface."""
    def __init__(self, name: str = "Mohamed_Splitter", time_limit: float = 1.2):
        self.name = name
        self.agent = SplitterAgent(name=name, time_limit=time_limit, splits=True, search="mcts")

    def reset(self):
        self.agent.reset()

    def compute_moves(self, state: BoardState, species: Species) -> List[Tuple[int, int, int, int, int]]:
        return self.agent.compute_moves_board(state, species)

def run_10_matches():
    print("=" * 85, flush=True)
    print(f"{COLOR_BOLD}🔥 FIA 10-MATCH TOURNAMENT: Mohamed's Splitter VS Apex Champion 🔥{COLOR_RESET}", flush=True)
    print("=" * 85, flush=True)

    # 1. Agents Setup
    time_budget = 0.6

    apex = ApexAlphaBetaAgent(
        name="ApexChampion",
        max_time_seconds=time_budget,
        enable_foraging_yield=False,
        enable_voronoi=True,
        enable_quiescence=True
    )

    mohamed = MohamedAgentAdapter(
        name="Mohamed_Splitter",
        time_limit=time_budget
    )

    # 2. 5 Distinct Maps covering small, medium, large, and giant scales
    maps = []
    if os.path.exists("thetrap.xml"):
        maps.append(("TheTrap_5x10", load_map_from_xml("thetrap.xml")))
    else:
        maps.append(("Compacte_6x9", generate_random_symmetric_map(6, 9, start_units=6, num_pairs=2, seed=42)))
    maps.append(("Carree_10x10", generate_random_symmetric_map(10, 10, start_units=8, num_pairs=3, seed=42)))
    maps.append(("Rectangle_10x18", generate_random_symmetric_map(10, 18, start_units=10, num_pairs=4, seed=123)))
    if os.path.exists("testmap.xml"):
        maps.append(("Officielle_15x29", load_map_from_xml("testmap.xml")))
    else:
        maps.append(("Grande_15x29", generate_random_symmetric_map(15, 29, start_units=10, num_pairs=5, seed=303)))
    maps.append(("Geante_25x25", generate_random_symmetric_map(25, 25, start_units=12, num_pairs=7, seed=404)))

    results = []
    apex_wins = 0
    mohamed_wins = 0
    draws = 0

    match_idx = 1
    total_matches = len(maps) * 2

    for map_name, base_state in maps:
        # Match Aller: Apex = Vampires, Mohamed = Werewolves
        print(f"\n{COLOR_CYAN}>>> MATCH {match_idx:02d}/{total_matches:02d} : {map_name} (Aller){COLOR_RESET}", flush=True)
        print(f"    Vampires [ROUGE] : {apex.name} | Loups-Garous [BLEU] : {mohamed.name}", flush=True)
        apex.transposition_table.clear()
        mohamed.reset()
        t0 = time.time()
        winner, turns, v_cnt, w_cnt = play_match_visual(apex, mohamed, base_state, visualize=False)
        dur = time.time() - t0

        if winner == apex.name:
            apex_wins += 1
            res_str = f"{COLOR_RED}Victoire {apex.name}{COLOR_RESET}"
        elif winner == mohamed.name:
            mohamed_wins += 1
            res_str = f"{COLOR_BLUE}Victoire {mohamed.name}{COLOR_RESET}"
        else:
            draws += 1
            res_str = f"{COLOR_YELLOW}Match NUL{COLOR_RESET}"

        print(f"    Résultat : {res_str} en {turns} tours ({dur:.1f}s) | Score V={v_cnt} vs W={w_cnt}", flush=True)
        results.append((match_idx, f"{map_name} (Aller)", f"{apex.name} (V)", f"{mohamed.name} (W)", winner, turns, v_cnt, w_cnt, dur))
        match_idx += 1

        # Match Retour: Mohamed = Vampires, Apex = Werewolves (Inversion complète)
        print(f"\n{COLOR_CYAN}>>> MATCH {match_idx:02d}/{total_matches:02d} : {map_name} (Retour){COLOR_RESET}", flush=True)
        print(f"    Vampires [ROUGE] : {mohamed.name} | Loups-Garous [BLEU] : {apex.name}", flush=True)
        apex.transposition_table.clear()
        mohamed.reset()
        t0 = time.time()
        winner, turns, v_cnt, w_cnt = play_match_visual(mohamed, apex, base_state, visualize=False)
        dur = time.time() - t0

        if winner == apex.name:
            apex_wins += 1
            res_str = f"{COLOR_RED}Victoire {apex.name}{COLOR_RESET}"
        elif winner == mohamed.name:
            mohamed_wins += 1
            res_str = f"{COLOR_BLUE}Victoire {mohamed.name}{COLOR_RESET}"
        else:
            draws += 1
            res_str = f"{COLOR_YELLOW}Match NUL{COLOR_RESET}"

        print(f"    Résultat : {res_str} en {turns} tours ({dur:.1f}s) | Score V={v_cnt} vs W={w_cnt}", flush=True)
        results.append((match_idx, f"{map_name} (Retour)", f"{mohamed.name} (V)", f"{apex.name} (W)", winner, turns, v_cnt, w_cnt, dur))
        match_idx += 1

    # Tableau final détaillé
    print("\n" + "=" * 90, flush=True)
    print(f"{COLOR_BOLD}                  CLASSEMENT & RÉSULTATS DES 10 MATCHS                  {COLOR_RESET}", flush=True)
    print("=" * 90, flush=True)
    print(f"{'#':<3} | {'Carte':<26} | {'Vampires [R]':<18} | {'Loups [B]':<18} | {'Gagnant':<16} | {'Tours':<5} | {'Score'}", flush=True)
    print("-" * 90, flush=True)
    for m_i, m_name, v_player, w_player, w_name, t, v, w, dur in results:
        winner_display = w_name if w_name else "NUL"
        print(f"{m_i:<3} | {m_name:<26} | {v_player:<18} | {w_player:<18} | {winner_display:<16} | {t:<5} | V={v:<2} W={w:<2}", flush=True)
    print("-" * 90, flush=True)

    apex_pct = (apex_wins / total_matches) * 100
    mohamed_pct = (mohamed_wins / total_matches) * 100
    draws_pct = (draws / total_matches) * 100

    print(f"\n🏆 BILAN FINAL DU TOURNOI (10 MATCHS) :", flush=True)
    print(f"   • {COLOR_BOLD}Apex Champion (Minimax){COLOR_RESET}   : {apex_wins} victoires ({apex_pct:.1f}%)", flush=True)
    print(f"   • {COLOR_BOLD}Mohamed Splitter (MCTS){COLOR_RESET}    : {mohamed_wins} victoires ({mohamed_pct:.1f}%)", flush=True)
    print(f"   • Matchs Nuls                  : {draws} nuls ({draws_pct:.1f}%)", flush=True)
    print("=" * 90, flush=True)

if __name__ == "__main__":
    run_10_matches()
