# Lab notebook: my bot against my teammates' bots (Oct 29–31, 2026)

Everything done after Report v2, step by step, for the next version of the report.

## Step 1. Keep the original safe
- Copied the whole project to `FIA-VampiresVSWerewolves_WORKCOPY_2026-10-29`. All work below happens there.
- The original folder `FIA-VampiresVSWerewolves` is unchanged: last commit `139df90` (Oct 16, 19:34), no edited files.

## Step 2. Pull every teammate's latest code from GitHub (read-only)
Checked out into `WORKCOPY\teammates\`. Their code was not changed.

| Teammate | Commit | Date | Bot |
|---|---|---|---|
| Othmane | 475549f | Oct 25, 15:59 | Apex V3.1: iterative-deepening Alpha-Beta, 25-ply race projection, multi-splitting |
| Dana | 4554265 | Oct 22, 10:05 | SafeAgent: expectiminimax (averages over dice outcomes), material + race |
| Mohamed | 118e3ae | Oct 25, 19:57 | Splitter-R3: MCTS over ~15 plans, safe detachments, commitment, merged with my long dice rollouts |
| Harsha | 88600de | Oct 28, 14:29 | MCTS built on my design ("rebuilt around Ronita's approach"), 15 parallel trees on 15 cores |

- All four use only standard Python and start with `python main.py <IP> <PORT>`, like mine.
- Harsha's code vs mine, share of identical lines per function: group_goals 90%, build_turn 83%, generate_plans 82%, select_child 82%, evaluate 69%, rollout_plan 69%, step_toward 64%, race_projection 57%, run_iteration 54%, rollout 30%.

## Step 3. Read their documentation
- Mohamed's `docs/SERVER_FINDINGS.md` (from the real server's code): one rule differs from the PDF. When the defender is 1.5x bigger, the real server rolls dice (attacker wins with probability E1/(2·E2)); it is not certain death. Moves into the same cell are added together before battles. An empty or illegal move ends the game (cheating). A late answer skips the turn.
- Mohamed's chapters 14–16: about 50 ideas tested; most "improvements" disappeared on new maps (luck). Halving thinking time cost 25 points. He merged my RaceMCTS's long dice-driven imaginary games into his flagship. He identified my bot's weak spot: my simulator uses the PDF rule, so it underestimates smaller enemies. His result against my bot: 2 wins, 2 losses.

## Step 4. Build a referee (stand-in for the professor's server)
- `team_arena/referee.py`: speaks the official protocol (SET, HUM, HME, MAP, UPD, MOV, END, BYE), uses the real server's rules (Step 3), 2.0 s per move, 200 plies maximum, 5-minute game clock, records every move to a JSON file.
- `team_arena/run_matches.py`: launches both bots with their own `main.py`. First to connect plays Vampires, as on the real server.
- Fairness: Harsha's bot uses 15 cores, so his games ran alone; the other three opponents ran side by side (one core each, 16 cores available).
- Check before the real games: my bot vs itself on thetrap, 30 plies: protocol and timing correct (moves 1.60 s).

## Step 5. Round 1: my original bot vs all four (16 games)
2 maps (testmap, thetrap; testmap2 is an identical copy, so not used) x 2 sides x 4 opponents, 1 game each.
Result: 10 wins, 6 losses.

**Finding: Othmane's and Harsha's main.py still wait 0.5 s before thinking** (the starter kit default I removed on Oct 16).
- Othmane: 0.5 + 1.65 s = 2.15 s, over the limit on every turn: 64 and 67 timeouts in the two big-map games; his late answers were then read as the next turn's move, which ended one game as "cheating" (move from an empty cell).
- Harsha: 0.5 + 1.4 s = about 1.92 s, 0.08 s under the limit (one timeout seen in round 2).
- At the tournament the launcher gives no --delay, so Othmane's bot would time out every turn.

## Step 6. Fair replay of Othmane (4 games, his wait set to 0)
2 wins, 1 draw, 1 loss. His slowest move: 1.69 s, no timeouts.

## Step 7. What the games show (paths from the move logs)
- Small map (thetrap): every game is a coin flip, decided in 2 to 35 plies by one early dice battle between equal groups.
- Big map: Mohamed collects fastest (house of 4 at turn 10, house of 2 at turn 14); Dana waits with one big group (11) and picks off small groups; Harsha is slow (first capture turn 17 or 51) with up to 7 small groups; my bot's first capture came around turn 10–23.
- Most of my wins came from the opponent's dice gambles failing (Othmane 16v16, Mohamed 8v12 twice, Dana 6v10, 4v11 ...).
- My big-map losses came from my small split groups being eaten (Dana killed 2, 6 and 6 with 11; Mohamed killed 8 with 16).

My original bot, per opponent (fair Othmane replay): Othmane 2W 1D 1L, Dana 3W 1L, Mohamed 2W 2L, Harsha 2W 2L. Total 9W 1D 6L.

## Step 8. Experiment 1: "remember the target" (Mohamed's commitment, bonus 0.35)
- Change (work copy only): each group keeps last turn's goal with a 35% bonus; memory reset each game; also fixed the log counter.
- Quick check vs Greedy (0.2 s, 18 games): 11W 7L (before: 14W 4L).
- Full test vs all four (16 games, same settings as round 1): 6W 1D 9L (before: 9W 1D 6L). Big map 2W 1D 5L (before 5W 1D 2L). Small map unchanged.
- Decision (rule agreed in advance: keep only if it wins more): switched off (COMMIT_BONUS = 0), code kept.

## Step 9. Bug found while studying the losses
In 2 of the new losses my group walked onto an equal or slightly bigger enemy (16 onto 16, 8 onto 10) and lost the dice battle. Cause: `step_toward` only avoids enemies 1.5x bigger, so an equal enemy on the shortest path gets attacked by accident. The bug is in the original bot too. Proposed next experiment: never step onto an enemy unless it is a sure kill; do not stop next to an enemy that wins at 50% or more (real-server odds).

## Numbers kept for the report
- 36 games played in total (16 + 4 + 16), 0 timeouts and 0 illegal moves by my bot; my slowest move 1.62 s.
- Full table of all 36 games: `report_material/all_36_games_table.md`.

## Where the evidence is (all inside WORKCOPY\team_arena\)
| What | File |
|---|---|
| One line per game (result, score, plies, reason) | results/results.jsonl |
| Every move of every game, with battles and timing | results/games/*.json (36 files) |
| Each bot's own screen output | results/bots/*.txt (72 files) |
| Round summaries | run_round1.txt, run_othmane_nodelay.txt, run_v2_commit.txt |
| The referee and the runner | referee.py, run_matches.py |

---

## Oct 31, 2026: diagnosis and experiment 2

### Step 10. What I learned from the 36 games: five faults
| # | Fault | Evidence |
|---|---|---|
| 1 | Walks into enemies by accident (step_toward only avoided enemies 1.5x bigger) | 16 onto 16 vs Mohamed, 8 onto 10 vs Harsha: both lost |
| 2 | Splits into groups small enough to be eaten | Dana ate 2, 6 and 6 with 11; Mohamed ate 8 with 16 |
| 3 | Imagines the PDF rules, not the real server's | Small-map losses; Mohamed's notes name it my weak spot |
| 4 | Ends moves next to equal enemies (free 50% first strike) | Small-map games lost in 2 to 4 moves |
| 5 | Scoring ignores risk below the 1.5x line | Same games as 2 and 4 |

Strategic idea noted for later: the house of 20 in the middle of the big map is almost never taken; no bot plans to merge its groups to 20+ to capture it.

### Step 11. Where the thinking time goes (profile, Oct 31)
One 3-second decision, big map, original bot: 1,805 imaginary games. step_toward used 47% of the time; the distance function was called 736,407 times (about 30%).

### Step 12. Experiment 2: safe steps (fixes 1 and 4), work copy only
- step_toward: never steps onto an enemy it can't kill for sure, or onto humans it can't convert for sure; prefers not to end next to an enemy at least its own size.
- First version was 25 to 30% slower (fewer imaginary games), so it was optimised: neighbours of every cell stored once per board size, dangerous cells worked out once per turn (threat map) and shared by all plans, distances computed inline.

Imaginary games per second, same positions, average of 3 runs:
| Position | Original | Safe steps, first try | Safe steps, optimised |
|---|---|---|---|
| Start of big map | 2,013 | 1,496 | 2,272 (+13%) |
| Mid-game | 1,425 | 1,002 | 2,251 (+58%) |

Quick check vs Greedy (0.2 s, PDF-rule practice arena, 18 games): 8 wins, 6 losses, 4 draws (original: 14 wins, 4 losses). New draws come from both sides keeping apart on the big map; one loss came from stepping onto the last house next to an enemy 8 (we became 9, and an 8 attacking a 9 wins 44%).

Full test vs all four teammates (16 games, real rules): running, results below when done.

### Step 13. Experiment 2 result (Oct 31): safe steps vs all four teammates (16 games, real rules)
| Version | Big map | Small map | Total |
|---|---|---|---|
| Original | 5W 1D 2L | 4W 0D 4L | 9W 1D 6L |
| Memory (experiment 1) | 2W 1D 5L | 4W 0D 4L | 6W 1D 9L |
| Safe steps (experiment 2) | 4W 2D 2L | 6W 0D 2L | 10W 2D 4L |

- Small map: from coin flips (4-4) to 6-2: the bot no longer offers a free 50% first strike.
- Harsha: 4 wins out of 4 (original 2 of 4). Mohamed big map: 2 losses became 2 draws. New loss: Othmane, big map, as Vampires (0-9).
- Decision: safe steps KEPT (clear mechanism, best result so far; still only 16 games, to confirm with more).

### Step 14. Experiment 3: attack mode ("divide and conquer", Ronita's idea, Oct 31)
Built on top of safe steps, switched on with RONITA_ATTACK=1 (off by default):
- Divide: one group sends exact-size detachments to up to 3 houses at once (each converts for sure and comes back doubled).
- Conquer: sure kills (1.5x) hunted twice as hard (weight 1.2 -> 2.4).
- Strike: deliberate attacks at 1.1x or more (60%+ odds), never by accident.
- Not "attack everything": in the 36 games, opponents attacking equal or bigger groups lost almost every such battle.
Test vs all four teammates (16 games): running.

### Step 15. Experiment 3 result (Oct 31): attack mode vs all four teammates (16 games)
| Version | Big map | Small map | Total | Points (win 1, draw 0.5) |
|---|---|---|---|---|
| Original | 5W 1D 2L | 4W 0D 4L | 9W 1D 6L | 9.5 |
| Safe steps | 4W 2D 2L | 6W 0D 2L | 10W 2D 4L | 11 |
| Attack mode | 5W 0D 3L | 6W 0D 2L | 11W 0D 5L | 11 |

By opponent (safe steps -> attack mode): Othmane 2W 2L -> 4W 0L; Harsha 4W -> 4W; Dana 3W 1L -> 3W 1L; Mohamed 1W 2D 1L -> 0W 4L.
- Attack mode won every fight it chose: 4 good-odds strikes won, 0 lost; 4 sure kills.
- All 4 losses to Mohamed were close, at the 200-ply limit (14-16, 12-14, 8-9, 7-10): his bot ends slightly bigger by collecting faster.
- Verdict: safe steps and attack mode are tied (11 points each in 16 games). Not decided; needs more games.

---

## Nov 5, 2026: code cleanup (work copy only, nothing pushed)

### Step 16. Cleaned mcts_agent.py without changing the bot's behaviour
- Removed the switched-off memory feature (bonus, goal tracking, reset code), since experiment 1 rejected it. The version used in the experiments is kept in team_arena/snapshots/mcts_agent_before_cleanup_2026-11-05.py, so those results stay reproducible.
- Split the 120-line generate_plans into small functions (two_house_splits, detachment_orders, other_groups_moves); removed a duplicated block, an unused parameter (species in build_turn), a redundant one (threats in step_toward) and an unused import (time in ai_agent.py); moved all settings to the top of the file.
- 505 lines -> 480 lines.

Checks:
- Old vs new on 6,000 random boards, both sides, in normal and attack mode: plans, imaginary-game moves and scores identical, 0 differences; every plan legal.
- Speed unchanged: 863 vs 862 imaginary games per second, same position, same run. (Lower than the 2,251 measured on Oct 31, so the laptop was slower today; compare only within one run.)
- Real games through main.py and the referee, 24 plies, both modes: no timeouts, no fallback moves, slowest move 1.61 s.

Status: safe steps and attack mode still tied (11 points each in 16 games). GitHub still has only the Oct 16 commit (139df90).

### Step 17 (Nov 5). Bigger test: safe steps vs attack mode (72 games, low priority, no internet)
36 games each against Othmane, Dana and Mohamed (rounds 2 to 4: 2 maps x 2 sides x 3 rounds). Harsha left out: both versions were already 4-0 against him and his bot uses 15 cores. No timeouts, no illegal moves, slowest move 1.617 s. Imaginary games per move were higher than on Oct 31 (big map, safe steps: about 3,500 vs 2,700), so the bots were not starved.

| Version | Total | Score | Othmane | Dana | Mohamed | Big map | Small map |
|---|---|---|---|---|---|---|---|
| Safe steps | 12W 4D 20L | 39% | 4W 2D 6L | 4W 8L | 4W 2D 6L | 6W 4D 8L | 6W 12L |
| Attack mode | 7W 8D 21L | 31% | 4W 4D 4L | 3W 9L | 4D 8L | 8D 10L | 7W 11L |

- The Oct 31 scores (11 of 16 for each) were mostly luck: both versions are below 50% against these three.
- Decision: attack mode stays off (31% vs 39%; 17% vs Mohamed, 22% on the big map). The gap is within luck, but nothing favours attack mode overall.
- Open question: the original bot had not played these same games, so "safe steps beats the original" is NOT proven. Control run started.
- Log reading (safe steps): opponents killed my groups 21 times, I killed theirs 8 times; opponents won 16 dice battles. My imagined players only attacked when sure, so the search could not see those strikes.

### Step 18 (Nov 5). Merge 1 from Mohamed: real battle rules and striking imagined players
- game_engine.py: with real dice, a defender 1.5x bigger no longer wins for sure, and the minimum of 1 survivor is gone (matches the server). Check: 4 attacking 10 leaves survivors 11% of the time, as the maths predicts.
- mcts_agent.py: in imaginary games, a group strikes an adjacent enemy at 45%+ odds (Mohamed's measured value). 8,000 test turns on random boards: 0 illegal.
- Run started: original bot and merge 1, 36 games each, same opponents and rounds.

### Step 19 (Nov 5). Control and merge 1 results (36 games each, same opponents and rounds)
| Version | Total | Score | Othmane | Dana | Mohamed | Big map | Small map |
|---|---|---|---|---|---|---|---|
| Original (Oct 16) | 13W 0D 23L | 36% | 3W 9L | 6W 6L | 4W 8L | 8W 10L | 5W 13L |
| Safe steps | 12W 4D 20L | 39% | 4W 2D 6L | 4W 8L | 4W 2D 6L | 6W 4D 8L | 6W 12L |
| Merge 1 (real rules + imagined strikes) | 10W 6D 20L | 36% | 6W 1D 5L | 4W 1D 7L | 4D 8L | 4W 6D 8L | 6W 12L |
| Attack mode | 7W 8D 21L | 31% | 4W 4D 4L | 3W 9L | 4D 8L | 8D 10L | 7W 11L |

- With 36 games, gaps under about 15 points can be luck: no version is proven better than the original.
- Merge 1 did not win more: removed from the working code (kept in team_arena/frozen/merge1_2026-11-05).
- Original had 1 timeout in 36 games (slowest move 2.0 s); safe steps none (slowest 1.62 s).
- Opponents' sure kills: 6 against the original, 21 against safe steps. Fewer dice losses, but more groups cleanly eaten.

### Step 20 (Nov 5). Which groups get eaten (safe steps, 36 games)
18 of the 21 groups killed were of size 1, 2 or 4; the killer was on average 2.9x bigger. My groups moved in several pieces on 57% of big-map turns. Collection speed is not the problem: first capture at turn 10 for both sides, second at turn 19 (me) vs 25 (them).

### Step 21 (Nov 5). Merges 2 and 3, built on the clean safe-step version
- Merge 2, safe splits (idea from Mohamed's detachment_safe): walk_is_safe refuses a split if an enemy at least the group's size can touch it on the way, or an enemy at least its size after capturing can reach the house in time.
- Merge 3 = merge 2 + regroup when hunted: a group with an enemy 1.5x bigger on the board values rejoining its friends 3x more (0.3 -> 0.9).
- Checks: three hand-made safety cases correct; 57,509 plans on random boards, 0 illegal.
- Run started: 36 games each, same opponents and rounds.

### Step 22 (Nov 5). Merges 2 and 3 results (36 games each, same opponents and rounds)
| Version | Total | Score | Othmane | Dana | Mohamed | Big map | Small map |
|---|---|---|---|---|---|---|---|
| Original (Oct 16) | 13W 0D 23L | 36% | 3W 9L | 6W 6L | 4W 8L | 8W 10L | 5W 13L |
| Safe steps | 12W 4D 20L | 39% | 4W 2D 6L | 4W 8L | 4W 2D 6L | 6W 4D 8L | 6W 12L |
| Merge 2 (safe splits) | 9W 4D 23L | 31% | 5W 1D 6L | 3W 9L | 1W 3D 8L | 4W 4D 10L | 5W 13L |
| Merge 3 (safe splits + regroup when hunted) | 14W 3D 19L | 43% | 7W 5L | 6W 6L | 1W 3D 8L | 8W 3D 7L | 6W 12L |

- Opponents' sure kills fell from 21 (safe steps) to 11 (merge 3). No timeouts or illegal moves; slowest 1.625 s.
- Merge 3 is the best of 5 versions, but 7 points above the original is within luck, and picking the best of 5 flatters it. Mohamed remains the weak spot (21%).

### Step 23 (Nov 5). Confirmation test on fresh games and new maps
- Two new fair maps generated (mirror-symmetric): mid_11x17 (start 8, 50 humans) and wide_13x21 (start 6, 36 humans), in team_arena/maps/.
- Merge 4 added: the regroup rule alone, without the safe-split check.
- Run started: merge 3, original and merge 4, 48 games each (3 opponents x 4 maps x 2 sides x 2 new rounds).

### Step 24 (Nov 6). Confirmation test result (48 games each, fresh dice, 4 maps, Othmane/Dana/Mohamed)
| Version | Total | Score (+/- 1 standard error) | Othmane | Dana | Mohamed |
|---|---|---|---|---|---|
| Original (Oct 16) | 22W 0D 26L | 46% +/- 7 | 11W 5L | 4W 12L | 7W 9L |
| Merge 3 (safe splits + regroup) | 17W 7D 24L | 43% +/- 7 | 10W 6L | 5W 2D 9L | 2W 5D 9L |
| Regroup only | 18W 4D 26L | 42% +/- 7 | 11W 5L | 3W 1D 12L | 4W 3D 9L |

- Reliability: no timeouts, no illegal moves; slowest move 1.64 s.
- By map: all three versions stay between 25% and 50%; no map shows a clear winner.
- Decision: no version beats the original, so the algorithm changes are NOT pushed. Merge 3's 43% in Step 22 was not confirmed as a lead (it scored 43% again, but the original rose from 36% to 46%).
- Lesson: every apparent gain since Oct 31 (safe steps 39%, attack mode, merge 3) sits within luck of the original.

### Step 25 (Nov 6). Report v4 written and saved
Chapter 16 (360 more games), a correction note in chapter 15, chapter 17 (dated diary). Saved as report_versions/Report_v4_2026-11-06.pdf. No code pushed.

### Step 26 (Nov 6). Why the original bot loses, read game by game
Games lost by the original to Dana and Mohamed (tests A and B):
- Dana: 12 of 18 lost games were games where my bot had been ahead at some point; peak sizes up to 30.
- Weak enemies won big dice battles: 6 beat 16, 19 beat 30, 4 beat 17. On the real server the loser's whole group dies.
- After the houses ran out, my bot chased enemies, which handed them the first strike.
- Mohamed on thetrap as Werewolves: 4 identical 7v10 accidental attacks (the bug safe steps removes).

### Step 27 (Nov 6). Merge 5: protect the lead
Built on merge 3. When my total is bigger than the enemy's: every adjacent enemy counts as danger, no hunting (only kills already next to me), and with nothing to do the group moves away instead of chasing. Reason: the bigger side wins when time runs out.
Checks: 3 hand-made positions correct; 53,542 plans on random boards, 0 illegal.
Run started: 48 games, same settings as the original's 46%.

### Step 28 (Nov 6). Merge 5 result: protect the lead (48 games, same settings as test B)
| Version | Total | Score | Othmane | Dana | Mohamed | testmap | thetrap | mid_11x17 | wide_13x21 |
|---|---|---|---|---|---|---|---|---|---|
| Original | 22W 0D 26L | 46% +/- 7 | 69% | 25% | 44% | 42% | 50% | 42% | 50% |
| Merge 3 | 17W 7D 24L | 43% +/- 7 | 62% | 38% | 28% | 46% | 33% | 42% | 50% |
| Merge 5, protect the lead | 22W 8D 18L | 54% +/- 7 | 69% | 69% | 25% | 67% | 33% | 67% | 50% |

No timeouts or illegal moves; slowest move 1.63 s. Dana rose from 25% to 69%. 8 of the 10 losses to Mohamed ended at the limit just behind, often with no fights late on. The 8-point gain over the original is within luck, so it needs confirming on fresh games.

### Step 29 (Nov 6). Merge 6: comeback rule (Ronita's option C)
Built on merge 5. When behind, within the last 50 plies, with no house still convertible: each group goes for the enemy group with the best odds-weighted value, and the final step onto it is allowed. Checks: 4 hand-made positions correct; 53,634 plans, 0 illegal.
Queued: merge 6 on test B settings, then fresh games (rounds 7 and 8) for merge 6, merge 5 and the original, 48 each.

### Step 30 (Nov 6 to Nov 9). Comeback stopped early, push, report v5
- The comeback run stopped after 43 of 48 games when the app session ended (Nov 6): 18W 6D 19L, 49%, below protect the lead (54%). Comeback dropped. The fresh-game confirmation did not run.
- Nov 9: pushed protect the lead (merge 5, as tested) to the Ronita branch: commit c9f42ee (mcts_agent.py, ai_agent.py). Checked first: files identical to the tested copy; a real 24-ply game through main.py ran with no timeouts or errors (slowest move 1.63 s).
- Report v5: chapter 18 (protect the lead), diary to Nov 9. Saved as report_versions/Report_v5_2026-11-09.pdf.

### Step 31 (Nov 10). Why we lose to Mohamed (merge 5, 16 games)
Score 25% (2W 4D 10L). Almost every loss ends at the 200-ply limit a few creatures short (8-9, 10-7).
- thetrap: after the 4-house we have 8 vs his 4; he splits 2+2, takes the far houses, merges to 9. Protect the lead stopped us hunting his small groups.
- mid_11x17 and wide_13x21: the Vampire side wins almost every game in every version, so these maps decide the side more than the bot.
- testmap: 16-16 draws; the 20-human house can't be taken by anyone.

### Step 32 (Nov 10). Merge 7 (short hunts when leading) and merge 8 (enemies strike together)
- Merge 7: when leading, sure kills within 4 steps if no enemy can protect the prey; only enemies at least half our size count as danger; with no humans left all groups merge.
- Bug found in a merge 7 game (also in merge 5): danger was checked per enemy group, but the server adds up moves into one cell. Our 8 stood next to a 4 and a 5, each "smaller", and lost to 9. Merge 8 adds up all enemies around a cell.
- New: run_matches.py --port-offset, so two runs share the laptop on the same dice; team_arena/score.py prints the table.

### Step 33 (Nov 10). Merge 9: desperation (same idea as merge 6's comeback, all game long)
When behind and the humans left can't close the gap, a dice fight beats a sure loss on time (8 vs 9 wins 44%). The score at the end of an imaginary game is made sharp when no humans are left (8 vs 9 is nearly a loss), so the tree sees why the fight is worth it. Checks on hand-made positions: approaches and attacks when behind, walks away when ahead, kills the 4 when the enemy is split 5+4.

### Step 34 (Nov 10). Results, rounds 7-8 (fresh dice, 48 games each, same dice for every version)
| Version | Score | Othmane | Dana | Mohamed |
|---|---|---|---|---|
| Merge 5 (pushed) | 52% | 72% | 56% | 28% |
| Merge 7 | 48% | 69% | 59% | 16% |
| Merge 8 | 51% | 59% | 66% | 28% |
| Merge 9 | 47% | 68% | 41% | 34% |
Merge 5 on rounds 5-6 scored 54%, so it is confirmed at about 53% on 96 games.
Reading the games: desperation helps against Mohamed (he never gives anything away) but hurts against Dana, who often attacks into bigger groups and hands creatures over (one game went from behind to ahead, then a 41% attack threw it away). Also a house of 20 that nobody can take counted as "humans left", so groups never merged and a lone 4 was killed.

### Step 35 (Nov 10). Merge 10: wait, then fight
Merge 9, but desperation only in the last 40 plies (a careless opponent has time to give creatures away first), and houses nobody can convert are ignored. Checks: holds back at ply 40, attacks at ply 170.
Running: merge 10 on rounds 7-8; merge 5 on rounds 9-10 for more control games.

### Step 36 (Nov 10). Merge 10 and merge 11 results, and the verdict
Merge 11 = merge 10 + two lessons from Mohamed's strategy notes: (1) our simulator said a defender 1.5x bigger always wins, the real server still rolls dice; fixed in game_engine.py for the dice mode; (2) when ahead with no humans left, an enemy 1/5 of our size counts as danger (his bot gambles from 10% odds when losing) and we no longer chase. Checks: 15,340 plans on random boards, 0 illegal; a 4 attacking 20 now wins about 9% in the simulator (server: 10%).

| Version, same dice | Rounds 7-8 | Rounds 9-10 | Pooled (96 games) | vs Mohamed (32) |
|---|---|---|---|---|
| Merge 5 (pushed) | 52% | 42% | 47% | 23% |
| Merge 10 | 53% | - | - | 22% (16 games) |
| Merge 11 | 52% | 45% | 48% | 22% |

No timeouts, no illegal moves. The same code swung 10 points between rounds 7-8 and 9-10, so luck is bigger than any change made today.
Verdict: no version beats merge 5, so nothing new is pushed. Against Mohamed every version scores 16-34%: the gap is not in the end game but in the human race (his splits take more houses earlier), and on mid_11x17 and wide_13x21 the Vampire side wins in almost every game whatever the bot.
