# What the real game server actually does

How we know:
- **Scripted probe games** against `VampiresVSWerewolvesGameServer.exe`: [tools/probe_server.py](../tools/probe_server.py), with the maps in `tools/probe_maps/`.
- **Disassembly of the server's rules code** (`VVSW.Model.dll`: `Board.PerformMoves`, `CheckMoves`, `GetProba`, `PerformRandomBattle`, `GameControl.GameRoutine`). We read it with a small .NET reflection script, so this is the real logic, not a guess.

To rerun a probe:

    powershell -File tools/restart_server.ps1 -Map tools/probe_maps/probe1.xml -MaxPlays 20
    python tools/probe_server.py rules

`restart_server.ps1` rewrites the server's `.exe.config`. Restore it afterwards with `git checkout VampiresVSWerewolvesGameServer.exe.config`.

## Battles: one difference from the PDF

| Situation (E1 = attackers, E2 = defenders) | PDF | **Server** |
|---|---|---|
| Humans, E1 ≥ E2 | convert all | convert all, the cell gets E1+E2 ✔ |
| Humans, E1 < E2 | random | random ✔ |
| Monsters, E1 ≥ 1.5·E2 | sure win, no losses | sure win, no losses ✔ |
| **Monsters, E2 ≥ 1.5·E1** | **attackers all die** | **RANDOM battle**, P = E1/(2·E2) ⚠ |
| Monsters, otherwise | random | random ✔ |

- **Checked in a live game:** 6 attackers against 10 defenders won 1 time out of 8. The trace shows *"Déclenchement d'une bataille aléatoire … L'attaquant va survivre"*.
- **Consequence for us:** a much smaller enemy group can still attack one of our groups and win with probability E1/(2·E2). A threat is not only "an enemy at least 1.5× my size".

**Win probability** (`GetProba`):
- P = 0.5 when E1 = E2;
- P = E1/(2·E2) when E1 < E2;
- P = E1/E2 − 0.5 when E2 < E1 < 1.5·E2.

**Survivors** (`PerformRandomBattle`):
- *Attackers win:* each attacker survives with probability P. Against humans, each human also survives with probability P and joins the attacker's species.
- *Attackers lose:* **all attackers die**, and each defender survives with probability 1 − P. Checked live: 4 against 9 humans left 8 humans and 0 attackers.

## How a turn is resolved (`Board.PerformMoves`)

- **Moves are grouped by DESTINATION and their counts are SUMMED** before any battle. Two moves of 3 into a cell of 5 humans give a single attack of 6, so all 5 convert. Checked live: the cell ended with 11 werewolves.
- **Several moves from the same cell (a split) are allowed.** Checked live: 10 became 3 + 3 + 4.
- **Counts are stored in bytes (`conv.u1`):** 200 + 100 wraps around to 44. **Never let a cell go above 255.**

## What counts as cheating (`Board.CheckMoves`): the game ends at once

Every one of these ends the game. The trace says *"Fin de la partie car les X ont triché"*.

- **An empty MOV.** Logged as *"ont triché car ils sont restés statiques"*.
- **Rule 5:** a move whose source or target is in the set (all sources) ∩ (all targets).
- **Wrong source:** the source cell does not hold our species.
- **Not enough creatures:** a move's count is larger than the source cell holds, or all moves out of one cell add up to more than it holds.
- **Not one step:** |dx| > 1 or |dy| > 1, or source = target (that also breaks Rule 5).
- **A zero count.**
- **Off the board:** targets are **not** bounds-checked. An off-board index would make the server throw, so never send one.
- **A dropped connection,** for example if our process crashes, is also logged as cheating.

## Turns, time and the end of the game (`GameControl.GameRoutine`)

- **Player 0, the first client to connect, moves first.** In our runs player 0 always had the Vampires.
- **The UPD sent to a player** lists every cell that changed since that player's last UPD: our own moves plus the opponent's.
- **Waiting for a reply.** The server polls for at least 4 bytes until `MaxPlayDuration`. On timeout it logs *"ont fait un time out"*, **skips our turn**, and play continues.
- **Leftover bytes** from an earlier turn are flushed before the next UPD is sent. **But** if our late reply arrives after the next UPD was sent, the server takes it as the answer to the *new* turn. It may then be illegal, which counts as cheating. **Never be late.**
- **The game ends when** a species reaches 0, after `MaxPlays` plies **in total** (200 means 100 per player), or when `MaxGameDuration` runs out (default 5 min). The winner is the larger total, or nobody if the totals are equal. END and BYE arrive about 4s after the last move.
- **One game per launch:** the server stops listening once 2 players have connected.
- **One starting cell per species:** a map with 2 starting cells for one species crashed the server, so tournament maps will have one cell per species.

## Rules for our bot

1. **Validate every move list** against the rules above before sending it (`splitter/rules.py: check_moves`). If it fails, send a safe one-step fallback move.
2. **Never send two moves into a cell held by humans or enemies if their sum would still lose.** Merging is legal and is a valid tactic: sum the counts.
3. **Keep a strict time budget** of 1.5s by default, measured from the moment the UPD arrives.
4. **Never let a cell go above 255** creatures.
5. **Treat a smaller enemy group next to us as a real (random) threat,** not as harmless.
