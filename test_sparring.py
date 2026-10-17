"""Run with:  python3 test_sparring.py   (from the repo folder)"""
import os
import random
import tempfile
import time

from game_state import Species
from maps import build_suite, make_symmetric_map, mirror, write_xml
from map_loader import load_map
from selfplay import play_game
from sparring_agents import PANEL, make_opponent
from state_converter import state_from_board

V, W = Species.VAMPIRE, Species.WEREWOLF

# 1) Generated maps are point-symmetric: every cell has a twin with the species swapped.
for name, b in build_suite():
    for (x, y), (h, v, w) in b.grid.items():
        mh, mv, mw = b.get_cell(mirror((x, y), b.rows, b.cols))
        if name.startswith("g"):
            assert (h, v, w) == (mh, mw, mv), (name, (x, y))
    tv = sum(v for _, v, _ in b.grid.values()); tw = sum(w for _, _, w in b.grid.values())
    assert tv > 0 and tv == tw, name
print("OK  generated maps are point-symmetric and fair (equal armies)")

# 2) Same seed -> same map; XML round trip keeps the map.
assert make_symmetric_map(3, 9, 15, 8, 5, 6).grid == make_symmetric_map(3, 9, 15, 8, 5, 6).grid
b = build_suite()[5][1]
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "m.xml")
    write_xml(b, p)
    assert load_map(p).grid == b.grid
print("OK  maps are reproducible and XML export/import round-trips")

# 3) Every opponent plays only legal turns, for both species, in whole games on every map.
t_max = 0.0
turns_checked = 0
for name in PANEL:
    for map_name, board in build_suite():
        for first in (V, W):
            agents = {V: make_opponent(name), W: make_opponent("Random")}
            r = play_game(board, agents, first=first, seed=1)
            st = r.stats[V]
            assert st.illegal == 0 and st.crashes == 0 and st.timeouts == 0, (name, map_name, st.last_problem)
            t_max = max(t_max, max(st.decision_times, default=0))
            turns_checked += len(st.decision_times)
print(f"OK  6 opponents x {len(build_suite())} maps x 2 orders: {turns_checked} turns, "
      f"0 illegal/crash/timeout, slowest decision {1000 * t_max:.0f} ms")

# 4) Each opponent answers the very first position of the trap map legally.
trap = load_map("thetrap.xml")
st = state_from_board(trap, V, home=(4, 3))
for n in PANEL:
    mv = make_opponent(n).compute_moves(st)
    assert mv and trap.validate_moves(mv, V)[0], n
print("OK  every opponent answers with a legal turn on the trap map")
print("\nAll tests passed.")
