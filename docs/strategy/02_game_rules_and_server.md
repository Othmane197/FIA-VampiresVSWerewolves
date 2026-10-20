# 02 · Game rules and the real server

An AI is only as good as its model of the game. We did not trust the PDF alone. The rules below
come from the **real server**, `VampiresVSWerewolvesGameServer.exe`, and were established in two
ways (the full evidence is in [../SERVER_FINDINGS.md](../SERVER_FINDINGS.md)):

1. **Probe games.** Scripted clients played chosen moves on small probe maps, and we read the server's replies and trace files.
   - Script: [tools/probe_server.py](../../tools/probe_server.py) ([`ProbeClient`](../../tools/probe_server.py#L31), scenario table `SCENARIOS`).
   - Restart helper: [tools/restart_server.ps1](../../tools/restart_server.ps1).
   - Maps: [tools/probe_maps/](../../tools/probe_maps).
2. **Disassembly of the server's rules code.** We used a .NET reflection script on `VVSW.Model.dll` to read `Board.GetProba`, `Board.PerformRandomBattle`, `Board.PerformMoves`, `Board.CheckMoves` and `GameControl.GameRoutine`. This gave the exact formulas and checks.

## 2.1 Battles

Let E1 be the attackers and E2 the defenders.

| Situation | Result on the server | PDF |
|---|---|---|
| Humans, E1 ≥ E2 | All humans convert; the cell holds E1 + E2 of our species | same |
| Monsters, E1 ≥ 1.5·E2 | Defenders die; attackers lose nobody | same |
| **Monsters, E2 ≥ 1.5·E1** | **Random battle** with P = E1/(2·E2) | *attackers all die* ⚠ |
| Anything else | Random battle | same |

**Win probability P** (`GetProba`):
- P = 0.5 when E1 = E2;
- P = E1/(2·E2) when E1 < E2;
- P = E1/E2 − 0.5 when E2 < E1 < 1.5·E2.

**Survivors** (`PerformRandomBattle`):
- *Attackers win:* each attacker survives with probability P. Against humans, each human also survives with probability P and is converted.
- *Attackers lose:* **all attackers die**, and each defender survives with probability 1 − P.

**Why the ⚠ row matters.** It was checked live: 6 attackers against 10 defenders won 1 game out of
8. So a much smaller enemy group can still attack ours and win. The starter `game_engine.py`
follows the PDF and gets this wrong. Our threat model (`exposure`, `enemy_attack_loss`) counts
these attacks.

**Implementation:**

| Function | What it does |
|---|---|
| [`win_probability`](../../splitter/rules.py#L39) | `GetProba` exactly |
| [`is_sure_win`](../../splitter/rules.py#L51) | Humans need E1 ≥ E2; monsters need E1 ≥ 1.5·E2 |
| [`resolve_battle`](../../splitter/rules.py#L66) | Resolves one destination cell. `mode="sample"` draws the server's dice (with [`binomial`](../../splitter/rules.py#L56)); `mode="mean"` takes the more likely branch, for deterministic tests |

## 2.2 How a turn is resolved

This is `Board.PerformMoves`, copied by [`State.apply`](../../splitter/state.py#L96):

1. **Creatures leave their source cells.**
2. **Moves are grouped by destination and their counts summed.** Two moves of 3 into a house of 5 make one attack of 6, which converts all 5. This was checked live, and it is what makes the **pincer** plan possible (chapter 03).
3. **Each destination is resolved:**
   - empty or friendly cell → merge;
   - humans → conversion or random battle;
   - enemies → sure kill or random battle.

**Several moves from one cell (a split) are legal.** Checked live: 10 became 3 + 3 + 4.

**Counts are bytes:** more than 255 wraps around (200 + 100 becomes 44). We cap cells at
[`MAX_CELL`](../../splitter/rules.py#L20) = 255 and never plan such a merge.

## 2.3 What counts as cheating (the game ends)

`Board.CheckMoves` rejects a move list, and the server ends the game ("les X ont triché"), if:

- **The MOV is empty.** Logged as *"restés statiques"*: Rule 1.
- **A source or target is in sources ∩ targets.** Rule 5.
- **The source cell is not ours.**
- **A move's count is larger than its source cell holds,** or the moves from one cell add up to more than it holds.
- **It is not a one-step move:** |dx| > 1, |dy| > 1, or source = target.
- **The count is 0.**

A dropped connection, for example after a crash, is also logged as cheating.

[`check_moves`](../../splitter/rules.py#L91) runs all of these checks. It also adds the two the
server forgets: **targets must be inside the board** (the server would throw), and **no cell may
exceed 255**. Every plan the planner builds, and every move list the agent returns, passes through
it (chapters 03 and 06).

## 2.4 Turns, time and the end of the game

- **Player 0, the first client to connect, moves first.** In our runs it always had the Vampires.
- **UPD lists every cell that changed since our last UPD:** our own moves plus the opponent's.
- **A reply slower than `MaxPlayDuration` is a timeout:** the server skips our turn. Worse, a late reply that arrives after the next UPD is taken as the answer to the *new* turn, where it may be illegal and count as cheating. Hence the strict 1.5 s budget (chapter 06).
- **The game ends** when a species is wiped out, after `MaxPlays` plies **in total** (200 means 100 each), or when `MaxGameDuration` runs out (default 5 min). The larger total wins; equal totals mean no winner.

The agent estimates the remaining plies from both the ply cap and the game clock
([`SplitterAgent._remaining_plies`](../../splitter/agent.py#L116)).

## 2.5 Our state representation: [splitter/state.py](../../splitter/state.py)

| Function | Purpose |
|---|---|
| [`State`](../../splitter/state.py#L35) | `humans` and `groups[V]`, `groups[W]` as `{(x, y): count}` dicts, plus `ply` and `max_ply`. Sides are integers ([`V`](../../splitter/rules.py#L17) = 0, `W` = 1) |
| [`State.apply`](../../splitter/state.py#L96) | One turn with the server's semantics (2.2). Returns a new state |
| [`State.copy`](../../splitter/state.py#L52) | Cheap copy (MCTS copies a state for every simulated ply) |
| [`neighbors_table`](../../splitter/state.py#L21) | The 8-neighbourhood of every cell, built once per board size |
| [`State.is_terminal`](../../splitter/state.py#L72), [`State.winner`](../../splitter/state.py#L76) | End of game and its winner (2.4) |
| [`State.from_game_state`](../../splitter/state.py#L156), [`from_board`](../../splitter/state.py#L163), [`to_board`](../../splitter/state.py#L169), [`to_game_state`](../../splitter/state.py#L179), [`side_of_species`](../../splitter/state.py#L194) | Conversions to and from the team's two board types (`game_state.GameState`, `game_engine.BoardState`) |
| [`cheb`](../../splitter/rules.py#L28) | King-move (Chebyshev) distance = the number of moves between two cells |

**Tests:** [tests/test_rules.py](../../tests/test_rules.py) replays the real-server probes (split,
merged attack, 1.5× boundaries, the defender-random rule) and every cheating case.
