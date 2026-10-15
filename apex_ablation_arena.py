"""
Apex Internal Ablation Tournament & Combinatorial Benchmark
FIA - CentraleSupélec / Centrale Casablanca

Permet d'évaluer scientifiquement chaque amélioration isolée et combinée :
1. OFR (Optimal Foraging Rate) : Rendement marginal par unité de temps
2. VOR (Voronoi Temporal Dominance) : Élimination des cibles dans la cellule ennemie
3. QS  (Quiescence Search) : Prolongation tactique sur les contacts à distance 1

Variants évalués :
- Apex_v1_Base     : [0, 0, 0] (Ancienne version de référence)
- Apex_OFR         : [1, 0, 0] (Foraging seul)
- Apex_VOR         : [0, 1, 0] (Voronoï seul)
- Apex_QS          : [0, 0, 1] (Quiescence seule)
- Apex_OFR_VOR     : [1, 1, 0] (Foraging + Voronoï)
- Apex_OFR_QS      : [1, 0, 1] (Foraging + Quiescence)
- Apex_VOR_QS      : [0, 1, 1] (Voronoï + Quiescence)
- Apex_v2_All      : [1, 1, 1] (Version intégrale)
"""

import sys
import time
from typing import List, Dict, Tuple
from game_state import Species
from game_engine import BoardState
from apex_agent import ApexAlphaBetaAgent
from rival_agents import GreedyReflexAgent, TacticalSplitterAgent, ShallowMinimaxAgent, MonteCarloAgent
from tournament_arena import get_diverse_map_pool, play_match_visual

# Définition des 8 configurations d'Ablation
def make_apex_variants(time_limit: float = 0.15) -> Dict[str, ApexAlphaBetaAgent]:
    return {
        "Apex_v1_Base": ApexAlphaBetaAgent("Apex_v1_Base", max_time_seconds=time_limit,
                                          enable_foraging_yield=False, enable_voronoi=False, enable_quiescence=False),
        "Apex_OFR":     ApexAlphaBetaAgent("Apex_OFR",     max_time_seconds=time_limit,
                                          enable_foraging_yield=True,  enable_voronoi=False, enable_quiescence=False),
        "Apex_VOR":     ApexAlphaBetaAgent("Apex_VOR",     max_time_seconds=time_limit,
                                          enable_foraging_yield=False, enable_voronoi=True,  enable_quiescence=False),
        "Apex_QS":      ApexAlphaBetaAgent("Apex_QS",      max_time_seconds=time_limit,
                                          enable_foraging_yield=False, enable_voronoi=False, enable_quiescence=True),
        "Apex_OFR_VOR": ApexAlphaBetaAgent("Apex_OFR_VOR", max_time_seconds=time_limit,
                                          enable_foraging_yield=True,  enable_voronoi=True,  enable_quiescence=False),
        "Apex_OFR_QS":  ApexAlphaBetaAgent("Apex_OFR_QS",  max_time_seconds=time_limit,
                                          enable_foraging_yield=True,  enable_voronoi=False, enable_quiescence=True),
        "Apex_VOR_QS":  ApexAlphaBetaAgent("Apex_VOR_QS",  max_time_seconds=time_limit,
                                          enable_foraging_yield=False, enable_voronoi=True,  enable_quiescence=True),
        "Apex_v2_All":  ApexAlphaBetaAgent("Apex_v2_All",  max_time_seconds=time_limit,
                                          enable_foraging_yield=True,  enable_voronoi=True,  enable_quiescence=True),
    }

def test_variant_vs_hard_rivals(variant_name: str, agent: ApexAlphaBetaAgent, maps: List[Tuple[str, BoardState]]) -> Dict[str, float]:
    """
    Teste une variante spécifique contre les 3 rivaux les plus difficiles (Greedy, TacticalSplitter, ShallowMinimax).
    """
    hard_rivals = [
        GreedyReflexAgent("GreedyReflexAI"),
        TacticalSplitterAgent("TacticalSplitterAI"),
        ShallowMinimaxAgent("ShallowMinimaxAI"),
        MonteCarloAgent("MonteCarloAI", num_rollouts=6, rollout_depth=4)
    ]
    results = {}
    for rival in hard_rivals:
        wins, losses, draws = 0, 0, 0
        for map_name, map_state in maps:
            # Aller : Variant = Vampires
            w, _, _, _ = play_match_visual(agent, rival, map_state, visualize=False)
            if w == agent.name: wins += 1
            elif w == rival.name: losses += 1
            else: draws += 1

            # Retour : Variant = Loups
            w, _, _, _ = play_match_visual(rival, agent, map_state, visualize=False)
            if w == agent.name: wins += 1
            elif w == rival.name: losses += 1
            else: draws += 1

        tot = wins + losses + draws
        rate = (wins / tot * 100) if tot > 0 else 0
        results[rival.name] = (wins, losses, draws, rate)
    return results

def run_round_robin_championship(variants: List[ApexAlphaBetaAgent], maps: List[Tuple[str, BoardState]]):
    """
    Championnat interne All-Play-All : chaque combinaison affronte toutes les autres.
    """
    print("\n" + "=" * 90)
    print("       CHAMPIONNAT INTERNE ROUND-ROBIN : TOUTES LES COMBINAISONS D'APEX (8x8)       ")
    print("=" * 90)

    names = [v.name for v in variants]
    # Matrice de scores : [p1][p2] = (wins, losses, draws)
    matrix = {n1: {n2: [0, 0, 0] for n2 in names} for n1 in names}
    total_scores = {n: 0.0 for n in names}  # 1 pt victoire, 0.5 nul

    num_v = len(variants)
    for i in range(num_v):
        for j in range(i + 1, num_v):
            v1 = variants[i]
            v2 = variants[j]

            for map_name, map_state in maps:
                # Match 1 : v1 = Vampires, v2 = Loups
                w1, _, _, _ = play_match_visual(v1, v2, map_state, visualize=False)
                if w1 == v1.name:
                    matrix[v1.name][v2.name][0] += 1
                    matrix[v2.name][v1.name][1] += 1
                    total_scores[v1.name] += 1.0
                elif w1 == v2.name:
                    matrix[v1.name][v2.name][1] += 1
                    matrix[v2.name][v1.name][0] += 1
                    total_scores[v2.name] += 1.0
                else:
                    matrix[v1.name][v2.name][2] += 1
                    matrix[v2.name][v1.name][2] += 1
                    total_scores[v1.name] += 0.5
                    total_scores[v2.name] += 0.5

                # Match 2 : v2 = Vampires, v1 = Loups
                w2, _, _, _ = play_match_visual(v2, v1, map_state, visualize=False)
                if w2 == v1.name:
                    matrix[v1.name][v2.name][0] += 1
                    matrix[v2.name][v1.name][1] += 1
                    total_scores[v1.name] += 1.0
                elif w2 == v2.name:
                    matrix[v1.name][v2.name][1] += 1
                    matrix[v2.name][v1.name][0] += 1
                    total_scores[v2.name] += 1.0
                else:
                    matrix[v1.name][v2.name][2] += 1
                    matrix[v2.name][v1.name][2] += 1
                    total_scores[v1.name] += 0.5
                    total_scores[v2.name] += 0.5

    # Affichage du classement Round-Robin
    sorted_ranking = sorted(total_scores.items(), key=lambda x: x[1], reverse=True)
    total_games_per_agent = (len(variants) - 1) * len(maps) * 2

    print("\n" + "-" * 90)
    print(f"{'Rang':<5} | {'Variante Apex':<18} | {'Points':<8} | {'Max Pts':<8} | {'Pourcentage':<12} | {'Statut':<20}")
    print("-" * 90)
    for rank, (name, pts) in enumerate(sorted_ranking, 1):
        pct = (pts / total_games_per_agent * 100) if total_games_per_agent > 0 else 0
        status = "CHAMPION V2" if rank == 1 else ("BASELINE V1" if name == "Apex_v1_Base" else "Variante intermédiaire")
        print(f"#{rank:<4} | {name:<18} | {pts:6.1f} | {total_games_per_agent:6.1f} | {pct:10.1f}% | {status}")
    print("-" * 90)

    # Affichage duel direct V2 vs V1
    v2_vs_v1 = matrix["Apex_v2_All"]["Apex_v1_Base"]
    print(f"\n>>> FACE-À-FACE DIRECT : Apex_v2_All VS Apex_v1_Base <<<")
    print(f"Victoires v2 : {v2_vs_v1[0]} | Victoires v1 : {v2_vs_v1[1]} | Nuls : {v2_vs_v1[2]}")
    print("=" * 90 + "\n")

if __name__ == "__main__":
    maps = get_diverse_map_pool()
    variants_dict = make_apex_variants(time_limit=0.15)

    print("=" * 90)
    print("          ÉTUDE D'ABLATION SCIENTIFIQUE : VALIDATION PAS À PAS D'APEX V2           ")
    print("=" * 90)
    print("1. Évaluation isolée de chaque brique contre les rivaux difficiles")
    print("2. Évaluation des paires combinées")
    print("3. Évaluation de la version intégrale Apex_v2_All")
    print("4. Grand Championnat Round-Robin (Toutes contre toutes)")
    print("-" * 90)

    # ÉTAPE A : Benchmark de chaque variante contre les rivaux difficiles
    order_to_test = [
        "Apex_v1_Base",
        "Apex_OFR",
        "Apex_VOR",
        "Apex_QS",
        "Apex_OFR_VOR",
        "Apex_OFR_QS",
        "Apex_VOR_QS",
        "Apex_v2_All"
    ]

    print("\n--- RÉSULTATS COMPARATIFS CONTRE LES RIVAUX DIFFICILES (4 Cartes x Aller-Retour = 8 matchs/rival) ---")
    print(f"{'Variante':<15} | {'GreedyReflex':<15} | {'TacticalSplit':<15} | {'ShallowMini':<15} | {'MonteCarlo':<15} | {'Moyenne Globale':<15}")
    print("-" * 95)

    all_results = {}
    for v_name in order_to_test:
        agent = variants_dict[v_name]
        res = test_variant_vs_hard_rivals(v_name, agent, maps)
        all_results[v_name] = res

        g_pct = res["GreedyReflexAI"][3]
        t_pct = res["TacticalSplitterAI"][3]
        s_pct = res["ShallowMinimaxAI"][3]
        m_pct = res["MonteCarloAI"][3]
        avg_pct = (g_pct + t_pct + s_pct + m_pct) / 4.0

        print(f"{v_name:<15} | {g_pct:5.1f}%          | {t_pct:5.1f}%          | {s_pct:5.1f}%          | {m_pct:5.1f}%          | {avg_pct:5.1f}%")

    # ÉTAPE B : Grand Championnat Interne Round-Robin
    variant_list = [variants_dict[name] for name in order_to_test]
    run_round_robin_championship(variant_list, maps)
