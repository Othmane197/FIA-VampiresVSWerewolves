"""
Grand Tournament: Apex V3 Flagship (apex_agent.py) vs Mohamed Splitter (MCTS)
Full 8-Match Aller-Retour Duel on 4 Diverse Map Topologies.
"""
import time
from game_engine import BoardState, Species
from tournament_arena import (
    load_map_from_xml, generate_random_symmetric_map,
    play_match_visual
)
from apex_agent import ApexAlphaBetaAgent as ApexV3
from splitter.agent import SplitterAgent

class MohamedSplitterAdapter:
    def __init__(self, name="MohamedSplitter", time_limit=0.7):
        self.agent = SplitterAgent(name=name, time_limit=time_limit)
        self.name = name

    def compute_moves(self, state: BoardState, species: Species):
        return self.agent.compute_moves_board(state, species)

def run_tournament():
    maps = [
        ("Carree_10x10", generate_random_symmetric_map(10, 10, start_units=8, num_pairs=3, seed=202)),
        ("Rectangle_10x18", generate_random_symmetric_map(10, 18, start_units=10, num_pairs=4, seed=303)),
        ("Officielle_15x29", load_map_from_xml("testmap.xml")),
        ("Geante_25x25", generate_random_symmetric_map(25, 25, start_units=14, num_pairs=6, seed=404)),
    ]

    v3_score = 0.0
    moh_score = 0.0

    print("=" * 75)
    print("      FINAL GRAND TOURNAMENT : APEX V3 FLAGSHIP vs MOHAMED SPLITTER")
    print("=" * 75)

    for map_name, initial_state in maps:
        # Aller: Apex V3 (Vampires) vs Mohamed (Werewolves)
        v3 = ApexV3(name="ApexV3", max_time_seconds=0.7)
        moh = MohamedSplitterAdapter(name="MohamedSplitter", time_limit=0.7)
        winner, turns, v_cnt, w_cnt = play_match_visual(v3, moh, initial_state, visualize=False)
        
        if winner == "ApexV3":
            res = "APEX V3 WIN"
            v3_score += 1.0
        elif winner == "MohamedSplitter":
            res = "MOHAMED WIN"
            moh_score += 1.0
        else:
            res = "DRAW"
            v3_score += 0.5
            moh_score += 0.5
        print(f"[{map_name:16s}] Aller  (V3=Vmp, Moh=Wrw) -> {res:14s} | Score: V3 {v_cnt:2d} - {w_cnt:2d} Moh in {turns:2d} turns")

        # Retour: Mohamed (Vampires) vs Apex V3 (Werewolves)
        moh_ret = MohamedSplitterAdapter(name="MohamedSplitter", time_limit=0.7)
        v3_ret = ApexV3(name="ApexV3", max_time_seconds=0.7)
        winner, turns, v_cnt, w_cnt = play_match_visual(moh_ret, v3_ret, initial_state, visualize=False)

        if winner == "ApexV3":
            res = "APEX V3 WIN"
            v3_score += 1.0
        elif winner == "MohamedSplitter":
            res = "MOHAMED WIN"
            moh_score += 1.0
        else:
            res = "DRAW"
            v3_score += 0.5
            moh_score += 0.5
        print(f"[{map_name:16s}] Retour (Moh=Vmp, V3=Wrw) -> {res:14s} | Score: Moh {v_cnt:2d} - {w_cnt:2d} V3 in {turns:2d} turns")

    print("=" * 75)
    print(f"FINAL RESULT : Apex V3 = {v3_score:.1f} pts  |  Mohamed Splitter = {moh_score:.1f} pts")
    print("=" * 75)

if __name__ == "__main__":
    run_tournament()
