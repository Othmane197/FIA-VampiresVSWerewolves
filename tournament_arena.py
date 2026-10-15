"""
Tournament Arena & AI Benchmark Harness (Tailles Variables & Visualisation Propre)
Permet de simuler et tester des matrices de tailles très variées :
- Petites cartes (ex: 6x9)
- Cartes carrées (ex: 10x10)
- Cartes rectangulaires (ex: 10x18)
- Grandes cartes officielles (ex: 15x29)
- Générateur aléatoire de cartes équilibrées de n'importe quelle taille n x m.
"""

import os
import sys
import time
import random
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Optional
from game_state import Species
from game_engine import BoardState
from rival_agents import (
    RandomAgent,
    GreedyReflexAgent,
    PotentialFieldAgent,
    ShallowMinimaxAgent,
    MonteCarloAgent,
    TacticalSplitterAgent
)
from apex_agent import ApexAlphaBetaAgent

# Couleurs ANSI pour le terminal
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"      # Vampires
COLOR_BLUE = "\033[94m"     # Werewolves
COLOR_YELLOW = "\033[93m"   # Humains
COLOR_GRAY = "\033[90m"     # Case vide
COLOR_CYAN = "\033[96m"     # Infos tour
COLOR_BOLD = "\033[1m"

def render_board_ascii(state: BoardState, last_move_desc: str = "") -> str:
    """
    Affichage ASCII propre à espacement fixe (3 caractères par case)
    pour éviter tout chevauchement du type '11H4'.
    """
    lines = []
    # Numéros de colonnes alignés sur 3 caractères
    col_header = "    " + "".join(f"{x%100:2d} " for x in range(state.cols))
    lines.append(col_header)
    lines.append("   +" + "---" * state.cols + "+")

    for y in range(state.rows):
        row_str = [f"{y:2d} |"]
        for x in range(state.cols):
            h, v, w = state.get_cell((x, y))
            if h == 0 and v == 0 and w == 0:
                row_str.append(f"{COLOR_GRAY} . {COLOR_RESET}")
            elif v > 0:
                cnt = min(v, 99)
                row_str.append(f"{COLOR_RED}V{cnt:<2d}{COLOR_RESET}")
            elif w > 0:
                cnt = min(w, 99)
                row_str.append(f"{COLOR_BLUE}W{cnt:<2d}{COLOR_RESET}")
            elif h > 0:
                cnt = min(h, 99)
                row_str.append(f"{COLOR_YELLOW}H{cnt:<2d}{COLOR_RESET}")
        row_str.append("|")
        lines.append("".join(row_str))

    lines.append("   +" + "---" * state.cols + "+")

    v_tot = state.get_species_total(Species.VAMPIRE)
    w_tot = state.get_species_total(Species.WEREWOLF)
    h_tot = sum(cnt for _, cnt in state.get_humans())
    summary = (
        f"   {COLOR_RED}[VAMPIRES : {v_tot:2d}]{COLOR_RESET} | "
        f"{COLOR_BLUE}[LOUPS-GAROUS : {w_tot:2d}]{COLOR_RESET} | "
        f"{COLOR_YELLOW}[HUMAINS : {h_tot:2d}]{COLOR_RESET}"
    )
    lines.append(summary)
    if last_move_desc:
        lines.append(f"   {COLOR_CYAN}{last_move_desc}{COLOR_RESET}")

    return "\n".join(lines)

def load_map_from_xml(xml_path: str) -> BoardState:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    rows = int(root.attrib.get("Rows", 10))
    cols = int(root.attrib.get("Columns", 10))

    state = BoardState(rows, cols, max_turns=80)
    for elem in root:
        tag = elem.tag
        x = int(elem.attrib["X"])
        y = int(elem.attrib["Y"])
        count = int(elem.attrib["Count"])
        h, v, w = state.get_cell((x, y))
        if tag == "Humans":
            state.set_cell((x, y), h + count, v, w)
        elif tag == "Vampires":
            state.set_cell((x, y), h, v + count, w)
        elif tag == "Werewolves":
            state.set_cell((x, y), h, v, w + count)
    return state

def generate_random_symmetric_map(rows: int, cols: int, start_units: int = 8,
                                  num_pairs: int = 3, seed: Optional[int] = None) -> BoardState:
    """
    Génère une carte de taille arbitraire (rows x cols) 100% symétrique par rapport au centre.
    Pour tout élément en (x, y), son clone est placé en (cols - 1 - x, rows - 1 - y).
    """
    if seed is not None:
        rng = random.Random(seed)
    else:
        rng = random.Random()

    state = BoardState(rows, cols, max_turns=80)

    # Départ : Vampires en haut à gauche, Loups en bas à droite
    state.set_cell((1, 1), 0, start_units, 0)
    state.set_cell((cols - 2, rows - 2), 0, 0, start_units)

    occupied = {(1, 1), (cols - 2, rows - 2)}

    # Génération de paires symétriques de villages humains
    for _ in range(num_pairs):
        for _ in range(30):
            x = rng.randint(1, cols - 2)
            y = rng.randint(1, rows - 2)
            opp_x = cols - 1 - x
            opp_y = rows - 1 - y

            # Éviter superposition
            if (x, y) not in occupied and (opp_x, opp_y) not in occupied:
                # Nombre d'humains proportionnel aux unités de départ
                h_cnt = rng.randint(2, max(3, start_units // 2))
                state.set_cell((x, y), h_cnt, 0, 0)
                state.set_cell((opp_x, opp_y), h_cnt, 0, 0)
                occupied.add((x, y))
                occupied.add((opp_x, opp_y))
                break

    # Un village central équidistant si les dimensions le permettent
    mid_x, mid_y = cols // 2, rows // 2
    if (mid_x, mid_y) not in occupied and (cols - 1 - mid_x, rows - 1 - mid_y) not in occupied:
        center_prize = max(4, start_units - 2)
        state.set_cell((mid_x, mid_y), center_prize, 0, 0)
        state.set_cell((cols - 1 - mid_x, rows - 1 - mid_y), center_prize, 0, 0)

    return state

def get_diverse_map_pool() -> List[Tuple[str, BoardState]]:
    """
    Fournit un panel complet de cartes de tailles très différentes.
    """
    pool = []

    # 1. Petite carte compacte (6 lignes x 9 colonnes, 6 unités)
    pool.append(("Petite_6x9", generate_random_symmetric_map(rows=6, cols=9, start_units=6, num_pairs=2, seed=101)))

    # 2. Carte carrée moyenne (10 lignes x 10 colonnes, 8 unités)
    pool.append(("Carree_10x10", generate_random_symmetric_map(rows=10, cols=10, start_units=8, num_pairs=3, seed=202)))

    # 3. Carte rectangulaire allongée (10 lignes x 18 colonnes, 10 unités)
    pool.append(("Rectangle_10x18", generate_random_symmetric_map(rows=10, cols=18, start_units=10, num_pairs=4, seed=303)))

    # 4. Carte officielle du professeur (15 lignes x 29 colonnes, 10 unités)
    if os.path.exists("testmap.xml"):
        pool.append(("Officielle_15x29", load_map_from_xml("testmap.xml")))

    return pool

def play_match_visual(agent_vampire, agent_werewolf, initial_state: BoardState,
                      visualize: bool = False, delay: float = 0.04) -> Tuple[Optional[str], int, int, int]:
    state = initial_state.clone()
    current_species = Species.VAMPIRE

    if visualize:
        print(f"\n{COLOR_BOLD}=== DÉBUT DU MATCH : {COLOR_RED}{agent_vampire.name} (Vampires){COLOR_RESET} vs {COLOR_BLUE}{agent_werewolf.name} (Loups){COLOR_RESET}{COLOR_BOLD} [{state.rows}x{state.cols}] ==={COLOR_RESET}", flush=True)
        print(render_board_ascii(state, "Position Initiale"), flush=True)
        time.sleep(delay)

    while True:
        over, winner = state.is_game_over()
        if over:
            v_cnt = state.get_species_total(Species.VAMPIRE)
            w_cnt = state.get_species_total(Species.WEREWOLF)
            winner_name = "NUL"
            if winner == Species.VAMPIRE:
                winner_name = agent_vampire.name
            elif winner == Species.WEREWOLF:
                winner_name = agent_werewolf.name

            if visualize:
                print(f"\n{COLOR_BOLD}>>> FIN DE PARTIE au Tour {state.turn_count} | Vainqueur : {winner_name} (Vampires: {v_cnt}, Loups: {w_cnt}) <<<{COLOR_RESET}\n", flush=True)
                time.sleep(delay * 2)

            return winner_name, state.turn_count, v_cnt, w_cnt

        active_agent = agent_vampire if current_species == Species.VAMPIRE else agent_werewolf
        moves = active_agent.compute_moves(state, current_species)

        valid, reason = state.validate_moves(moves, current_species)
        if not valid:
            other = agent_werewolf.name if current_species == Species.VAMPIRE else agent_vampire.name
            if visualize:
                print(f"[DISQUALIFIÉ] {active_agent.name} coup illégal : {reason}", flush=True)
            return other, state.turn_count, 0, 0

        state = state.apply_moves(moves, current_species, deterministic=False)

        if visualize:
            spec_str = "VAMPIRES" if current_species == Species.VAMPIRE else "LOUPS-GAROUS"
            move_info = ", ".join(f"{cnt}u de ({x1},{y1}) -> ({x2},{y2})" for x1, y1, cnt, x2, y2 in moves)
            desc = f"Tour {state.turn_count:2d} | {active_agent.name} ({spec_str}) : {move_info}"
            print(f"\n{render_board_ascii(state, desc)}", flush=True)
            time.sleep(delay)

        current_species = Species.WEREWOLF if current_species == Species.VAMPIRE else Species.VAMPIRE

def run_tournament():
    print("=" * 85, flush=True)
    print("      TOURNOI MULTI-MATRICES FIA : VAMPIRES VS WEREWOLVES (TAILLES VARIABLES)       ", flush=True)
    print("=" * 85, flush=True)

    args = sys.argv[1:]
    matches_per_duel = 4   # 4 matchs par duel par défaut (Aller-Retour sur 2 cartes différentes)
    visualize = True
    delay = 0.04
    chosen_pool_mode = "all"  # 'all', 'custom', 'official'
    custom_rows = 10
    custom_cols = 15

    # Arguments en ligne de commande
    if "--matches" in args:
        idx = args.index("--matches")
        if idx + 1 < len(args):
            matches_per_duel = int(args[idx + 1])
    elif sys.stdin.isatty():
        try:
            print("\n--- PARAMÈTRES DU TOURNOI ---")
            resp_matches = input("Combien de matchs par duel contre chaque IA ? (Nombre pair, ex: 2, 4, 8) [Défaut: 4] : ").strip()
            if resp_matches.isdigit() and int(resp_matches) > 0:
                matches_per_duel = int(resp_matches)

            print("\nSélection des tailles de cartes à simuler :")
            print("  1. Panel complet de tailles variables (Petite 6x9, Carrée 10x10, Rectangle 10x18, Officielle 15x29) [Recommandé]")
            print("  2. Générer une taille personnalisée (ex: choisir vos propres n et m)")
            print("  3. Carte officielle testmap.xml uniquement")
            resp_mode = input("Votre choix (1, 2 ou 3) [Défaut: 1] : ").strip()

            if resp_mode == "2":
                chosen_pool_mode = "custom"
                r_in = input("Nombre de lignes (ex: 7, 12, 16) [Défaut: 10] : ").strip()
                c_in = input("Nombre de colonnes (ex: 9, 14, 22) [Défaut: 15] : ").strip()
                if r_in.isdigit(): custom_rows = max(5, int(r_in))
                if c_in.isdigit(): custom_cols = max(6, int(c_in))
            elif resp_mode == "3":
                chosen_pool_mode = "official"
            else:
                chosen_pool_mode = "all"

            resp_vis = input("\nVoulez-vous visualiser les parties en direct sur le plateau ? (O/n) [Défaut: O] : ").strip().lower()
            if resp_vis in ("n", "non", "no"):
                visualize = False
            else:
                visualize = True
                resp_delay = input("Délai d'animation par coup en secondes (ex: 0.03, 0.08) [Défaut: 0.04] : ").strip()
                if resp_delay:
                    try:
                        delay = float(resp_delay)
                    except ValueError:
                        pass
        except (EOFError, KeyboardInterrupt):
            pass

    if "--no-visual" in args:
        visualize = False
    if "--delay" in args:
        idx = args.index("--delay")
        if idx + 1 < len(args):
            delay = float(args[idx + 1])

    # Construction du jeu de cartes
    if chosen_pool_mode == "custom":
        maps = [(f"Custom_{custom_rows}x{custom_cols}", generate_random_symmetric_map(custom_rows, custom_cols, start_units=8))]
    elif chosen_pool_mode == "official":
        maps = [("Officielle_15x29", load_map_from_xml("testmap.xml"))]
    else:
        maps = get_diverse_map_pool()

    # Détermination du nombre de paires Aller-Retour par carte
    # Au minimum 1 paire (Aller + Retour) par carte
    pairs_per_map = max(1, matches_per_duel // (2 * len(maps))) if matches_per_duel >= 2 * len(maps) else 1
    total_matches_per_rival = pairs_per_map * 2 * len(maps)

    # Instanciation de l'IA Championne Apex
    apex = ApexAlphaBetaAgent(name="ApexChampion", max_time_seconds=0.15)

    # Instanciation des IA rivales
    rivals = [
        RandomAgent("RandomAI"),
        GreedyReflexAgent("GreedyReflexAI"),
        PotentialFieldAgent("PotentialFieldAI"),
        ShallowMinimaxAgent("ShallowMinimaxAI"),
        MonteCarloAgent("MonteCarloAI", num_rollouts=6, rollout_depth=4),
        TacticalSplitterAgent("TacticalSplitterAI")
    ]

    results: Dict[str, Dict[str, int]] = {
        r.name: {"wins_vamp": 0, "wins_were": 0, "losses": 0, "draws": 0}
        for r in rivals
    }
    total_apex_wins = 0
    total_apex_losses = 0
    total_apex_draws = 0

    print(f"\nChampionne : {COLOR_BOLD}{apex.name}{COLOR_RESET} (Minimax Alpha-Bêta + Approfondissement Itératif)")
    print(f"Rivalités  : {[r.name for r in rivals]}")
    print(f"Cartes au programme ({len(maps)}) : {[m[0] for m in maps]}")
    print(f"Format des duels : {len(maps)} carte(s) x {pairs_per_map} Aller-Retour(s) = {total_matches_per_rival} matchs par rival")
    print(f"Visualisation : {'ACTIVÉE (' + str(delay) + 's/coup)' if visualize else 'DÉSACTIVÉE (Mode rapide)'}")
    print("\nLancement des duels...\n", flush=True)

    for rival in rivals:
        print(f"\n{COLOR_BOLD}{'='*32} DUEL : {apex.name} VS {rival.name} {'='*32}{COLOR_RESET}", flush=True)
        current_match_idx = 0

        for map_name, map_state in maps:
            for pair in range(pairs_per_map):
                # 1. Match ALLER : Apex = Vampires, Rival = Loups
                current_match_idx += 1
                w, turns, v_cnt, w_cnt = play_match_visual(
                    apex, rival, map_state,
                    visualize=visualize, delay=delay
                )
                if w == apex.name:
                    results[rival.name]["wins_vamp"] += 1
                    total_apex_wins += 1
                    verdict = f"{COLOR_BOLD}{COLOR_RED}VICTOIRE Apex{COLOR_RESET}"
                elif w == rival.name:
                    results[rival.name]["losses"] += 1
                    total_apex_losses += 1
                    verdict = f"{COLOR_BLUE}DÉFAITE Apex{COLOR_RESET}"
                else:
                    results[rival.name]["draws"] += 1
                    total_apex_draws += 1
                    verdict = "MATCH NUL"

                print(f"  Match {current_match_idx:2d}/{total_matches_per_rival} [ALLER ] | Carte: {map_name:<16} | Apex (Vampires    ) : {verdict:<22} en {turns} tours", flush=True)

                # 2. Match RETOUR : Rival = Vampires, Apex = Loups
                current_match_idx += 1
                w, turns, v_cnt, w_cnt = play_match_visual(
                    rival, apex, map_state,
                    visualize=visualize, delay=delay
                )
                if w == apex.name:
                    results[rival.name]["wins_were"] += 1
                    total_apex_wins += 1
                    verdict = f"{COLOR_BOLD}{COLOR_RED}VICTOIRE Apex{COLOR_RESET}"
                elif w == rival.name:
                    results[rival.name]["losses"] += 1
                    total_apex_losses += 1
                    verdict = f"{COLOR_BLUE}DÉFAITE Apex{COLOR_RESET}"
                else:
                    results[rival.name]["draws"] += 1
                    total_apex_draws += 1
                    verdict = "MATCH NUL"

                print(f"  Match {current_match_idx:2d}/{total_matches_per_rival} [RETOUR] | Carte: {map_name:<16} | Apex (Loups-Garous) : {verdict:<22} en {turns} tours", flush=True)

    # Tableau final détaillé
    print("\n" + "=" * 90, flush=True)
    print("                    CLASSEMENT FINAL MULTI-MATRICES (DÉTAILLÉ)                    ", flush=True)
    print("=" * 90, flush=True)
    print(f"{'Algorithme Rival':<20} | {'Vict. (V)':<10} | {'Vict. (W)':<10} | {'Total Vict.':<12} | {'Défaites':<9} | {'Nuls':<6} | {'Taux':<8}", flush=True)
    print("-" * 90, flush=True)

    for r_name, stat in results.items():
        w_v = stat["wins_vamp"]
        w_w = stat["wins_were"]
        tot_w = w_v + w_w
        losses = stat["losses"]
        draws = stat["draws"]
        total_g = tot_w + losses + draws
        pct = (tot_w / total_g * 100) if total_g > 0 else 0
        print(f"{r_name:<20} | {w_v:<10} | {w_w:<10} | {tot_w:<12} | {losses:<9} | {draws:<6} | {pct:5.1f}%", flush=True)

    total_matches = total_apex_wins + total_apex_losses + total_apex_draws
    overall_rate = (total_apex_wins / total_matches * 100) if total_matches > 0 else 0
    print("-" * 90, flush=True)
    print(f"BILAN GLOBAL : {total_matches} matchs joués | Apex : {total_apex_wins} Victoires - {total_apex_losses} Défaites - {total_apex_draws} Nuls | RÉUSSITE : {overall_rate:.1f}%", flush=True)
    print("=" * 90, flush=True)

if __name__ == "__main__":
    run_tournament()
