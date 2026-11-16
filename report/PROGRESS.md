# Ronita's progress (as of Nov 17, 2026)

**Bot:** MCTS with the "Race to the Humans" heuristic (`mcts_agent.py`), run with `python main.py <IP> <PORT>`.
The version on this branch is "protect the lead" (commit c9f42ee, Nov 9).

## Results against the team (my current version, real server rules, 2 s per move)

| Opponent | Games | Won | Draw | Lost | Score |
|---|---|---|---|---|---|
| Othmane | 48 | 32 | 3 | 13 | 70% |
| Dana | 48 | 25 | 2 | 21 | 54% |
| Mohamed | 48 | 7 | 9 | 32 | 24% |

Score = wins + half the draws. Maps: testmap, thetrap and two bigger maps (11x17, 13x21), both sides.
Over all 903 test games (every version): Othmane 63%, Harsha 62% (16 games), Dana 46%, Mohamed 27%.
No timeouts and no illegal moves in any game.

## What happened since Nov 9

- Nov 10: tried five new versions to beat Mohamed (short hunts when ahead, enemies that strike together,
  fighting when behind near the end, a simulator that rolls dice like the real server). 528 games, same dice
  for every version: none beat the pushed version, so the bot code was not changed.
- Mohamed's bot wins the race for the humans: it splits earlier and takes more houses before any fight.

## Files

- `Report_v6_2026-11-17.pdf`: the full report (chapters 1-19, diary, appendix).
- `lab_notebook.md`: every test, step by step, with dates.
