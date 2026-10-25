# 17 · Campaign 4: improving both kept models

**Goal:** work on campaign 3's open items (16.8): measure the new Apex V3, fix the flagship's
tempo weakness, understand RaceMCTS-live; then improve **both** the flagship (Splitter-R3) and the
backup (Splitter-Classic) without fitting the teammates' bots.

**References:** the flagship `Splitter` and the backup `Splitter-Classic` (chapter 16.9), each
checked against its frozen version after every code change (300/300 identical decisions under a
fixed clock: the flagship vs `Snap:c3` with its options, the backup vs `Snap:v7`).

## 17.1 Candidates (all off by default)

| Option | For | Origin | What it does | Where |
|---|---|---|---|---|
| `keep_away=True` | Flagship | The tempo weakness (16.9) | When the opponent is desperate and no humans are left, our groups never step next to an enemy that beats them with at least `desperate_p` odds (it would strike first); stepping onto the enemy itself (a sure kill) is allowed; with every step blocked the group stays. In the planner (`safe_step`) and on our side of the race rollouts | [`PlanConfig.keep_away_p`](../../splitter/planner.py#L55), [`safe_step`](../../splitter/planner.py#L164), [`race_rollout_plan`](../../splitter/planner.py#L735) |
| `race_root_safe=True` | Flagship | First-strike exposure of the race root plans (16.6) | When we are not behind, the RaceMCTS-style root plans' steps also avoid cells next to an enemy at least as big as the moving group (it would strike first at 50%+); when behind they stay aggressive | [`race_plans`](../../splitter/planner.py#L840), [`_race_step`](../../splitter/planner.py#L704) |
| `desperate_p=0.1, keep_away=True` | Backup | Leads lost to low-odds strikes (16.7: the Classic lost a 50-to-36 lead to a 12% strike) | The desperate-opponent model with the tempo fix, on the Classic's quick rollouts | [`SplitterAgent._choose`](../../splitter/agent.py#L194) |
| `strike_p=0.6` | Backup | Good-odds first strikes (16.5: +5.0 on Splitter-R) | "strike" plans when not behind | [`generate_plans`](../../splitter/planner.py#L381) |
| Anytime watchdog answer | Both (tournament client) | Code review F7 | When this turn's search is late, `main.py` sends the search's best plan so far (legal-checked) instead of the naive one-step fallback | [`Watchdog.decide`](../../main.py#L66), [`SplitterAgent.anytime_moves`](../../splitter/agent.py#L131) |

Mechanism checks before any game: with `keep_away` the flagship solves both tempo puzzles (5/5,
it was 0/5) and still refuses the desperate opponent's shot (5/5). The anytime answer is
covered by `test_watchdog_sends_the_best_plan_so_far_when_late`. It only acts when the search is
late, which the arena (no watchdog) cannot measure, so it is adopted on these correctness tests.

## 17.2 Data

- **Diagnostic (no decision):** both models against Apex V3 (`Apex-live`, Othmane's push of 24 Oct) and RaceMCTS-live on the 14 tuning maps.
- **Screens:** the tuning slots (as in every campaign).
- **Validation:** a new map family **`fresh2`** (8 maps, seeds 301 to 308) and **Styled:13 to 18** (styles never used before), plus the three live bots. Nothing in campaigns 1 to 3 touched them.

## 17.3 Decision rules, written before the games

1. **Screen F** (flagship; tuning slots, 1.5 s, `--seed 9900`, `--drop-worse`): `Splitter` against `Splitter:keep_away=true`, `Splitter:race_root_safe=true` and both together.
2. **Screen B** (backup; tuning slots, 1.5 s, `--seed 9950`, `--drop-worse`): `Splitter-Classic` against `Splitter-Classic:desperate_p=0.1,keep_away=true`, `Splitter-Classic:strike_p=0.6` and both together.
3. **Selection** (per model): a component is kept if its own variant's paired difference to its model is positive. If both are kept, the candidate is the combination if that variant is not clearly worse than the model (difference + 2 SE > 0), else the kept component with the larger difference. None kept: the model has no candidate.
4. **Validation** (`fresh2` maps; Apex-live, RaceMCTS-live, Expecti-live, Styled:13 to 18; both sides; 1.5 s; `--seed 10000`; no early stopping, since the backup's variants would be stopped for being worse than the flagship): the flagship, its candidate, the backup, its candidate (144 games each).
5. **Adoption** (per model): the candidate replaces its model's settings if **its validation difference is positive and its screen and validation differences pooled are above 1.5 SE**, with 0 timeouts and 0 illegal moves. Why 1.5 rather than campaign 3's 2 SE: these are small, mechanism-backed refinements of a validated model (each verified on puzzles or loss logs first), selected from only two options per model; two independent positive signs plus the pooled evidence guard against noise, without making an improvement that acts in a few positions per game impossible to adopt.
6. **Real conditions:** an adopted model plays `tools/teammate_matches.py` (4 games per live bot); any illegal move or timeout cancels the adoption.

## 17.4 Results

### Two open items closed without new games

- **Moving second is the maps, not our bots.** In a mirror match (the campaign-2 flagship against its frozen copy, campaign 3's first screen) the first player scored 75% and the second 44%: the symmetric maps give the first mover about 30 points (it reaches the contested houses first). Our models' own gap in the campaign-3 final (Classic 75 / 55, Splitter-R3 85 / 60) does not exceed it. The larger gaps against Expecti-live and RaceMCTS-live (8 games per cell) are within noise. Not a weakness to fix.
- **A plans-only transposition cache would not help.** The campaign-2 cache failed as one option. Its board key turned out to be cheap (three small sorts), so key cost was not the reason. The reason is where positions repeat: 93% of plan generations on thetrap, 0% on the big village map, so the cache speeds up the searches that are already fast. Not built.

### Diagnostic: Apex V3 and RaceMCTS-live (14 tuning maps, both sides, 1.5 s; no decision)

`python -m arena.run --bot Splitter Splitter-Classic --opp Apex-live RaceMCTS-live --maps all --games 1 --time 1.5 --hard 2.0 --workers 3 --seed 9800 --out arena/results/c4_diag.csv` (75 minutes)

| | Apex V3 (`Apex-live`, Othmane@73fdaf5) | RaceMCTS-live |
|---|---|---|
| Flagship (Splitter-R3) | 78.6% (21 / 2 / 5) | 71.4% (20 / 0 / 8) |
| Backup (Splitter-Classic) | 78.6% (20 / 4 / 4) | **46.4% (13 / 0 / 15)** |

- **Apex V3 is not harder for us than the October-22 champion:** both models win about four games in five. 0 timeouts, 0 illegal moves.
- **The flagship's RaceMCTS-live weak spot of the final does not reproduce.** Here the flagship beats the backup against it by +25.0 ± 11.1 (paired), the opposite of the fresh-map final (−12.5 ± 8.5). Over both runs it is a map-to-map swing, not a weakness.
- **The backup's losses to RaceMCTS-live, read from the logs:** the material difference over the lost games (ours minus theirs, every 10 to 20 plies) shows two patterns.
  1. **Standoffs between equal armies, then one coin flip** (prize_13x23 both sides, sparse_12x20 both sides, close_8x12, testmap): material level for 40 to 70 plies, no house either army can take (the prize holds 24 against armies of 23), RaceMCTS closes in and herds us towards a corner, and one 50% battle ends the game. With the same dice the flagship won exactly these games: whoever attacks at 50% wins or loses on the same random number, so this is luck, not a decision error. A strike at even odds is worth the same as waiting to be struck.
  2. **A house race lost early** (sym_9x15a −10 by ply 10, sym_11x21 −11 by ply 30): no common cause in the logs.
  
  One loss matches a candidate exactly: a 34-to-23 lead with no humans left, lost to a 30–49% strike (the backup's `desperate_p` candidate). **Nothing else is a mechanism worth a fix**: building a rule against one bot's standoffs would be fitting that bot.

### The order of the runs

All runs below start one after the other, unattended (a scratch script applies rules 1 to 6 in
order and logs each decision), at below-normal priority with 3 workers; the computer stays usable.

| Run | Games | Duration (estimate) |
|---|---|---|
| Diagnostic: both models vs Apex V3 and RaceMCTS-live, 14 tuning maps | 112 | 75 min (done) |
| Screen F (flagship) | 240 | about 2 h |
| Screen B (backup) | 240 | about 2 h |
| Validation on `fresh2` | up to 576 | about 5 h |
| Real conditions for each adopted model | 12 each | about 1 h each |
