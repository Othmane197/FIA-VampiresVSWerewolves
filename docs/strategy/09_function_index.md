# 09 · Function index (generated)

Every class, function and method of our code, with a link to its line.
**Do not edit by hand**: run `python tools/gen_function_index.py` after changing the code.
Chapters 01–08 explain *why*; this page answers *where*.

## Tournament entry point

### [main.py](../../main.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `parse_args` | function | [11](../../main.py#L11) | Read --name / --delay and the server ip + port (the last two arguments, as the caller adds them). |
| `fallback_moves` | function | [39](../../main.py#L39) | One legal move (biggest group to a free neighbour that is not a source): never send an empty MOV. |
| `Watchdog` | class | [51](../../main.py#L51) | Runs agent.compute_moves in a worker thread and waits at most `limit` seconds: a late answer |
| `Watchdog.__init__` | method | [59](../../main.py#L59) | limit = seconds from the UPD to the MOV (the server allows 2 s). |
| `Watchdog.decide` | method | [65](../../main.py#L65) | Moves from the agent, or None if it crashed, returned nothing or was too slow. |
| `main` | function | [89](../../main.py#L89) | Protocol loop: NME, then SET/HUM/HME/MAP to build the state, then answer every UPD with a MOV. |

### [ai_agent.py](../../ai_agent.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `AIAgent` | class | [22](../../ai_agent.py#L22) | The tournament bot: "The Splitter" (splitter/agent.py, MCTS over joint plans with safe |
| `AIAgent.__init__` | method | [32](../../ai_agent.py#L32) | Create the Splitter engine (time budget from SPLITTER_TIME) and the starter fallback. |
| `AIAgent.reset` | method | [48](../../ai_agent.py#L48) | Forget the previous game (called by main.py on END). |
| `AIAgent.compute_moves` | method | [53](../../ai_agent.py#L53) | Splitter's moves for this turn; the starter strategy if the Splitter fails. |
| `StarterAgent` | class | [65](../../ai_agent.py#L65) | The original starter-kit strategy (walk to the nearest target). Kept as fallback/baseline. |
| `StarterAgent.__init__` | method | [68](../../ai_agent.py#L68) | Original starter-kit agent (kept as last-resort fallback and as a baseline opponent). |
| `StarterAgent.compute_moves` | method | [72](../../ai_agent.py#L72) | Computes the list of moves for the current turn. |

### [network.py](../../network.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `NetworkClient` | class | [6](../../network.py#L6) |  |
| `NetworkClient.__init__` | method | [7](../../network.py#L7) |  |
| `NetworkClient._socket` | method | [12](../../network.py#L12) | The connected socket (raises ConnectionError before connect() / after close()). |
| `NetworkClient.connect` | method | [18](../../network.py#L18) |  |
| `NetworkClient._recv_exact` | method | [23](../../network.py#L23) |  |
| `NetworkClient.send_name` | method | [32](../../network.py#L32) |  |
| `NetworkClient.send_moves` | method | [38](../../network.py#L38) | moves: list of (x_src, y_src, count, x_dst, y_dst) |
| `NetworkClient.receive_command` | method | [49](../../network.py#L49) |  |
| `NetworkClient.close` | method | [93](../../network.py#L93) |  |

### [game_state.py](../../game_state.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `Species` | class | [5](../../game_state.py#L5) |  |
| `Cell` | class | [9](../../game_state.py#L9) |  |
| `Cell.__init__` | method | [11](../../game_state.py#L11) |  |
| `Cell.is_empty` | method | [16](../../game_state.py#L16) |  |
| `Cell.copy` | method | [19](../../game_state.py#L19) |  |
| `GameState` | class | [22](../../game_state.py#L22) |  |
| `GameState.__init__` | method | [23](../../game_state.py#L23) |  |
| `GameState.set_grid` | method | [33](../../game_state.py#L33) |  |
| `GameState.set_houses` | method | [38](../../game_state.py#L38) |  |
| `GameState.set_home` | method | [41](../../game_state.py#L41) |  |
| `GameState.apply_updates` | method | [44](../../game_state.py#L44) |  |
| `GameState.get_our_groups` | method | [66](../../game_state.py#L66) |  |
| `GameState.get_enemy_groups` | method | [74](../../game_state.py#L74) |  |
| `GameState.get_human_groups` | method | [82](../../game_state.py#L82) |  |
| `GameState.chebyshev_dist` | method | [89](../../game_state.py#L89) |  |
| `GameState.get_legal_adjacent_cells` | method | [92](../../game_state.py#L92) |  |
| `GameState.reset_for_new_game` | method | [104](../../game_state.py#L104) |  |
| `GameState.render_board` | method | [111](../../game_state.py#L111) | Renders a clean ASCII board representation with colors. |

## Splitter: exact rules and state

### [splitter/rules.py](../../splitter/rules.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `other` | function | [23](../../splitter/rules.py#L23) | The opposite side: V <-> W. |
| `cheb` | function | [28](../../splitter/rules.py#L28) | King-move (Chebyshev) distance: number of moves between two cells. |
| `win_probability` | function | [39](../../splitter/rules.py#L39) | Board.GetProba: probability that E1 attackers beat E2 defenders. |
| `is_sure_win` | function | [51](../../splitter/rules.py#L51) | No dice: humans need E1 >= E2, monsters need E1 >= 1.5 * E2. |
| `binomial` | function | [56](../../splitter/rules.py#L56) | Number of successes among n independent trials of probability p (server dice). |
| `resolve_battle` | function | [66](../../splitter/rules.py#L66) | Board.PerformMoves + PerformRandomBattle for one destination cell. |
| `check_moves` | function | [91](../../splitter/rules.py#L91) | Board.CheckMoves (what the server calls cheating) + the checks the server forgets |

### [splitter/state.py](../../splitter/state.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `neighbors_table` | function | [21](../../splitter/state.py#L21) | {cell: (adjacent cells inside the board)}; built once per board size. |
| `State` | class | [35](../../splitter/state.py#L35) | Board position: humans, both species' groups, ply counter. Cheap to copy, exact to update. |
| `State.__init__` | method | [39](../../splitter/state.py#L39) | Build a state from {pos: count} dictionaries. |
| `State.copy` | method | [52](../../splitter/state.py#L52) | Independent copy (the dictionaries are copied, the neighbour table is shared). |
| `State.total` | method | [64](../../splitter/state.py#L64) | Total number of creatures of one side. |
| `State.humans_total` | method | [68](../../splitter/state.py#L68) | Total number of humans left on the board. |
| `State.is_terminal` | method | [72](../../splitter/state.py#L72) | Game over: a species is wiped out or the ply limit is reached. |
| `State.winner` | method | [76](../../splitter/state.py#L76) | Side with more creatures (the server's rule at the end), None if equal. |
| `State.key` | method | [85](../../splitter/state.py#L85) | Hashable snapshot of the position (used in tests to compare states). |
| `State.__repr__` | method | [90](../../splitter/state.py#L90) | Readable one-line description for debugging. |
| `State.apply` | method | [96](../../splitter/state.py#L96) | New state after `side` plays `moves` (assumed legal: see rules.check_moves). |
| `State.from_cells` | method | [143](../../splitter/state.py#L143) | cells: iterable of ((x, y), humans, vampires, werewolves). |
| `State.from_game_state` | method | [156](../../splitter/state.py#L156) | From the repo's game_state.GameState (what main.py maintains). |
| `State.from_board` | method | [163](../../splitter/state.py#L163) | From game_engine.BoardState (the teammates' search board). |
| `State.to_board` | method | [169](../../splitter/state.py#L169) | Convert to game_engine.BoardState (the teammates' search board). |
| `State.to_game_state` | method | [179](../../splitter/state.py#L179) | Convert to game_state.GameState, as main.py would hold it for `side`. |
| `side_of_species` | function | [194](../../splitter/state.py#L194) | game_state.Species -> V / W. |

## Splitter: plan generator

### [splitter/planner.py](../../splitter/planner.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `PlanConfig` | class | [31](../../splitter/planner.py#L31) | Every tunable of the plan generator (the bot's variants are just different PlanConfigs). |
| `Goal` | class | [51](../../splitter/planner.py#L51) | One candidate objective for one group: a target cell, a kind and an estimated value. |
| `Plan` | class | [61](../../splitter/planner.py#L61) | A joint plan = one full turn (moves of all our groups), with its prior score and a tag. |
| `_step_dir` | function | [72](../../splitter/planner.py#L72) | -1, 0 or +1: the direction of one king step from coordinate a towards b. |
| `straight_path` | function | [77](../../splitter/planner.py#L77) | Cells visited by a king walking diagonally first, then straight (excludes src). |
| `enemy_attack_loss` | function | [88](../../splitter/planner.py#L88) | Expected creatures we lose if we stand on `cell` with `count` and the best adjacent enemy |
| `race_won` | function | [102](../../splitter/planner.py#L102) | Do we reach `target` (a house needing `need`) no later than any enemy group that can take it? |
| `detachment_safe` | function | [112](../../splitter/planner.py#L112) | Can a detachment of k creatures walk from src to the house `target` (h humans, k >= h), |
| `safe_step` | function | [140](../../splitter/planner.py#L140) | Best neighbour of src to walk `count` creatures towards `goal`: |
| `border_distance` | function | [189](../../splitter/planner.py#L189) | Number of cells between p and the nearest edge of the board (0 = on the edge). |
| `flee_cell` | function | [194](../../splitter/planner.py#L194) | Where to run: far from the threats FIRST, but into open space (a king chased along an edge or |
| `candidate_goals` | function | [217](../../splitter/planner.py#L217) | Ranked goals for one group (best first). `committed` = the goal this group had last turn. |
| `_Builder` | class | [294](../../splitter/planner.py#L294) | Turns a set of orders (src, count, goal) into a legal list of moves. |
| `_Builder.__init__` | method | [297](../../splitter/planner.py#L297) | One builder per generate_plans call: its caches are only valid for this state. |
| `_Builder.build` | method | [306](../../splitter/planner.py#L306) | -> (moves, intents). Orders whose goal is their own cell mean 'stay'. |
| `_orders_value` | function | [333](../../splitter/planner.py#L333) | Prior score of a plan = sum of the values of the goals its orders pursue. |
| `generate_plans` | function | [338](../../splitter/planner.py#L338) | The short list of joint plans for `side` to move. Never empty while `side` has creatures. |
| `_split_orders` | function | [456](../../splitter/planner.py#L456) | Yield (orders, tag, bonus) for plans where the group at `pos` sends detachments. |
| `_pincer_orders` | function | [524](../../splitter/planner.py#L524) | Yield (orders, tag) converging groups on the best house that only their sum can convert. |
| `fallback_plan` | function | [562](../../splitter/planner.py#L562) | A plain legal move: the biggest group steps to its least dangerous empty/friendly neighbour. |
| `quick_plan` | function | [582](../../splitter/planner.py#L582) | Cheap greedy policy for rollouts: take what is adjacent, else walk to the best target. |

## Splitter: evaluation

### [splitter/evaluate.py](../../splitter/evaluate.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `EvalParams` | class | [29](../../splitter/evaluate.py#L29) | The evaluation's tunable constants. Defaults = the flagship. The backup "Splitter-Calibrated" |
| `resolve_immediate` | function | [43](../../splitter/evaluate.py#L43) | Groups after the player to move takes its certain gains (kills >= 1.5x, conversions). |
| `project_race` | function | [67](../../splitter/evaluate.py#L67) | Projected sizes after both sides collect the houses they reach first (see module doc). |
| `_contest` | function | [121](../../splitter/evaluate.py#L121) | Is the capture of house hp by runner r (ending with size_after at time t) safe? |
| `exposure` | function | [140](../../splitter/evaluate.py#L140) | Expected creatures lost because enemies can attack these groups soon. |
| `evaluate` | function | [169](../../splitter/evaluate.py#L169) | P(side wins) estimate in [0, 1]; `ev` = the evaluation constants (see EvalParams). |
| `material_balance` | function | [218](../../splitter/evaluate.py#L218) | Quick (our total - their total) / everything, used to decide whether we are behind. |

## Splitter: search

### [splitter/mcts.py](../../splitter/mcts.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `Node` | class | [26](../../splitter/mcts.py#L26) | One node of the open-loop tree: the plan that leads to it, statistics, children. |
| `Node.__init__` | method | [31](../../splitter/mcts.py#L31) | New node reached by `mover` playing `plan`; prior = the plan's normalized prior. |
| `MCTS` | class | [43](../../splitter/mcts.py#L43) | Monte Carlo Tree Search over joint plans (see the module docstring). |
| `MCTS.__init__` | method | [46](../../splitter/mcts.py#L46) | Configure exploration, rollouts, widening, the plan configs of both sides and the evaluation. |
| `MCTS._plans` | method | [66](../../splitter/mcts.py#L66) | Plans for `side` at a tree node (opponent: gambles allowed), priors normalized to [0, 1]. |
| `MCTS._select` | method | [76](../../splitter/mcts.py#L76) | UCT + progressive bias. Only called on a node that has children. |
| `MCTS._widen_limit` | method | [92](../../splitter/mcts.py#L92) | Progressive widening: how many children a node with `visits` visits may have. |
| `MCTS.search` | method | [97](../../splitter/mcts.py#L97) | Run iterations until the deadline and return the most visited root plan. |
| `MCTS._iterate` | method | [122](../../splitter/mcts.py#L122) | One iteration: select / expand by replaying plans with fresh dice, roll out, evaluate, back up. |
| `MCTS.root_stats` | method | [177](../../splitter/mcts.py#L177) | [(visits, mean value, tag, moves)] of the root's children, most visited first. |

## Splitter: agent and safety net

### [splitter/agent.py](../../splitter/agent.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `SplitterAgent` | class | [41](../../splitter/agent.py#L41) | The tournament bot: planner + MCTS under a strict time budget, with a legal-move guarantee. |
| `SplitterAgent.__init__` | method | [44](../../splitter/agent.py#L44) | Build the plan config (variants via keyword arguments), the evaluation and the MCTS engine. |
| `SplitterAgent.reset` | method | [75](../../splitter/agent.py#L75) | Call between games (main.py does it on END). |
| `SplitterAgent.compute_moves` | method | [82](../../splitter/agent.py#L82) | main.py interface: moves for the GameState kept from the server messages. |
| `SplitterAgent.compute_moves_board` | method | [97](../../splitter/agent.py#L97) | Othmane's / Ronita's interface: moves for a BoardState and a Species. |
| `SplitterAgent.choose` | method | [104](../../splitter/agent.py#L104) | Arena interface: moves for a splitter State (fastest, true ply known). |
| `SplitterAgent._remaining_plies` | method | [113](../../splitter/agent.py#L113) | Plies left, from the ply cap and from the game clock (whichever ends first). |
| `SplitterAgent._safe_choose` | method | [123](../../splitter/agent.py#L123) | Never-fail wrapper: search, then validate, then fallbacks; always returns legal moves. |
| `SplitterAgent._choose` | method | [150](../../splitter/agent.py#L150) | Decide: evaluate, generate plans (with last turn's intents), search, remember intents. |
| `_emergency_move` | function | [184](../../splitter/agent.py#L184) | Last resort: any legal one-step move of the biggest group to a non-hostile cell. |

## Arena (benchmarking)

### [arena/maps.py](../../arena/maps.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `load_xml` | function | [28](../../arena/maps.py#L28) | Read a server map file (XML) into a State. |
| `write_xml` | function | [43](../../arena/maps.py#L43) | Save a State as a server map file, so the real GUI can load it. |
| `_cheb` | function | [58](../../arena/maps.py#L58) | King-move distance (local copy, keeps this module independent). |
| `symmetric_map` | function | [63](../../arena/maps.py#L63) | Random point-symmetric map: mirrored starts and mirrored houses of equal size. |
| `build_suite` | function | [138](../../arena/maps.py#L138) | name: 'all' (the 14 tuning maps), 'given', a family name ('holdout' = validation only), |
| `render` | function | [165](../../arena/maps.py#L165) | ASCII board: V12 / W7 / H4, '.' empty. |

### [arena/opponents.py](../../arena/opponents.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `_species` | function | [47](../../arena/opponents.py#L47) | V / W -> game_state.Species. |
| `load_vendor` | function | [52](../../arena/opponents.py#L52) | Import `modules` from arena/vendor/<branch> without clashing with the repo's modules. |
| `Bot` | class | [76](../../arena/opponents.py#L76) | Common interface of every arena bot: reset() and play(state, side) -> moves. |
| `Bot.reset` | method | [80](../../arena/opponents.py#L80) | Prepare for a new game. |
| `Bot.play` | method | [83](../../arena/opponents.py#L83) | Moves for `side` in `state` (implemented by the adapters). |
| `GameStateBot` | class | [88](../../arena/opponents.py#L88) | Adapter for agents with compute_moves(GameState) (repo starter, Dana's bots, AIAgent). |
| `GameStateBot.__init__` | method | [90](../../arena/opponents.py#L90) | Wrap an agent factory; a fresh agent is built for every game. |
| `GameStateBot.reset` | method | [97](../../arena/opponents.py#L97) | Fresh agent instance for a new game. |
| `GameStateBot.play` | method | [102](../../arena/opponents.py#L102) | Convert the State to a GameState and ask the agent. |
| `BoardBot` | class | [110](../../arena/opponents.py#L110) | Adapter for agents with compute_moves(BoardState, Species) (Othmane's and Ronita's bots). |
| `BoardBot.__init__` | method | [112](../../arena/opponents.py#L112) | Wrap an agent factory; a fresh agent is built for every game. |
| `BoardBot.reset` | method | [118](../../arena/opponents.py#L118) | Fresh agent instance for a new game. |
| `BoardBot.play` | method | [122](../../arena/opponents.py#L122) | Convert the State to a BoardState and ask the agent. |
| `SplitterBot` | class | [127](../../arena/opponents.py#L127) | Our bot through its fast choose(State, side) interface. |
| `SplitterBot.__init__` | method | [129](../../arena/opponents.py#L129) | SplitterAgent with the given keyword arguments (game clock disabled in the arena). |
| `SplitterBot.reset` | method | [136](../../arena/opponents.py#L136) | Forget the previous game. |
| `SplitterBot.play` | method | [140](../../arena/opponents.py#L140) | Moves chosen by the SplitterAgent. |
| `_parse_value` | function | [145](../../arena/opponents.py#L145) | '3' -> 3, '0.5' -> 0.5, 'true' -> True, else the string (for 'Splitter:key=value'). |
| `_registry` | function | [156](../../arena/opponents.py#L156) | name -> builder(time_limit) for every non-Splitter bot (teammates' bots are loaded lazily). |
| `_models` | function | [213](../../arena/opponents.py#L213) | The two kept models, named for the arena (defined once, in splitter/agent.py). |
| `styled_config` | function | [222](../../arena/opponents.py#L222) | Opponent style number n (deterministic): random risk taking, splitting, caution, search depth. |
| `bot_names` | function | [251](../../arena/opponents.py#L251) | Every bot name make_bot() accepts. |
| `SnapshotBot` | class | [256](../../arena/opponents.py#L256) | A frozen copy of splitter/ (arena/snapshots/splitter_<version>), see arena/snapshot.py. |
| `SnapshotBot.__init__` | method | [259](../../arena/opponents.py#L259) | SplitterAgent imported from arena/snapshots/splitter_<version>/. |
| `load_external` | function | [267](../../arena/opponents.py#L267) | 'py:<path>[:ClassName]' -> a Bot around an external Python agent class. Without ClassName the |
| `make_bot` | function | [310](../../arena/opponents.py#L310) | spec: registry name, Splitter variant, 'Splitter:k=v,..', 'Snap:<version>[:k=v,..]' or 'py:<file>[:Class]'. |

### [arena/referee.py](../../arena/referee.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `SideStats` | class | [22](../../arena/referee.py#L22) | Per-side statistics of one game: decision times, problems, split turns, max groups. |
| `GameResult` | class | [34](../../arena/referee.py#L34) | Outcome of one game: winner, length, final totals, end reason, stats and move log. |
| `state_to_dict` | function | [46](../../arena/referee.py#L46) | JSON-friendly board: lists of [x, y, n] for humans, vampires and werewolves. |
| `state_from_dict` | function | [53](../../arena/referee.py#L53) | Inverse of state_to_dict. |
| `play_game` | function | [59](../../arena/referee.py#L59) | Play one full game between two bots with the real server's rules (see module docstring). |

### [arena/run.py](../../arena/run.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `_file_safe` | function | [39](../../arena/run.py#L39) | A bot spec as a file-name part ('py:C:/x/bot.py:Cls', 'Splitter:c=0.8' contain : / = ...). |
| `_play_task` | function | [44](../../arena/run.py#L44) | Worker: play one game (bot vs opponent on a map and side) and return its CSV row. |
| `_score` | function | [85](../../arena/run.py#L85) | Win rate (win 1, draw 0.5) with its standard error. |
| `report` | function | [94](../../arena/run.py#L94) | Print the results grouped by opponent, map, our side and first player. |
| `_cost` | function | [127](../../arena/run.py#L127) | Rough game duration, to schedule the longest games first (no idle workers at the end). |
| `_append_csv` | function | [139](../../arena/run.py#L139) | Append records to a persistent CSV (header written once). |
| `store_history` | function | [150](../../arena/run.py#L150) | Persist one summary line per bot (history.csv) and per paired comparison (comparisons.csv). |
| `compare` | function | [169](../../arena/run.py#L169) | Paired comparison of every bot with the first one: same opponent, map, side and seed. |
| `paired_delta` | function | [200](../../arena/run.py#L200) | (mean paired difference, its standard error, games) of `bot` vs `ref` on the same games. |
| `_row_key` | function | [214](../../arena/run.py#L214) | Identity of one game of a run: (bot, opponent, map, our side, first player, seed). |
| `_load_rows` | function | [219](../../arena/run.py#L219) | Rows of an earlier (possibly interrupted) run, with numeric fields converted back. |
| `_rounds` | function | [235](../../arena/run.py#L235) | Split tasks into n rounds by GAME (all bots of one game stay in the same round), each round |
| `keep_awake` | function | [245](../../arena/run.py#L245) | Windows: keep the machine awake while this process runs (a sleep in the middle of a benchmark |
| `main` | function | [260](../../arena/run.py#L260) | Command line: build every (bot, opponent, map, side, game) task, run them in ONE pool, report. |

### [arena/replay.py](../../arena/replay.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `main` | function | [21](../../arena/replay.py#L21) | Command line: replay one game verbosely, optionally with the board after every ply. |

### [arena/snapshot.py](../../arena/snapshot.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|

### [arena/fetch_opponents.py](../../arena/fetch_opponents.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `fetch` | function | [27](../../arena/fetch_opponents.py#L27) | Copy the teammates' agent files from their origin/<branch> into arena/vendor/<branch>/. |

### [arena/history.py](../../arena/history.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `main` | function | [18](../../arena/history.py#L18) | Command line: print the selected stored results as a table. |

## Tools

### [tools/fake_server.py](../../tools/fake_server.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `_recv_exact` | function | [34](../../tools/fake_server.py#L34) | Read exactly n bytes from the socket (optionally before a deadline). |
| `FakeServer` | class | [52](../../tools/fake_server.py#L52) | One-game headless server with the real protocol, rules, time limit and cheating checks. |
| `FakeServer.__init__` | method | [54](../../tools/fake_server.py#L54) | Listen on 127.0.0.1:port (0 = any free port) for a game on `state`; game_seconds = game clock. |
| `FakeServer._cells` | method | [71](../../tools/fake_server.py#L71) | Encode cells as the protocol's 5-byte tuples (x, y, humans, vampires, werewolves). |
| `FakeServer._send_upd` | method | [79](../../tools/fake_server.py#L79) | Send a MAP or UPD message with the given cells. |
| `FakeServer.run` | method | [84](../../tools/fake_server.py#L84) | Accept 2 players, play the whole game, send END and BYE, return the result. |
| `main` | function | [186](../../tools/fake_server.py#L186) | Command line: run the fake server on a map file. |

### [tools/teammate_matches.py](../../tools/teammate_matches.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `load_map` | function | [66](../../tools/teammate_matches.py#L66) | An .xml map file (relative to the repo) or a map name of arena/maps.py. |
| `play_game` | function | [73](../../tools/teammate_matches.py#L73) | One full game over the protocol: fake server + main.py + the teammate's bot. Returns one row. |
| `summarize` | function | [126](../../tools/teammate_matches.py#L126) | Per-opponent table (markdown) of the finished games. |
| `store_history` | function | [152](../../tools/teammate_matches.py#L152) | One line per opponent in arena/results/history.csv (same file as the arena and server matches). |
| `main` | function | [171](../../tools/teammate_matches.py#L171) | Command line: play every (opponent, game), record each game at once, print the summary. |

### [tools/server_match.py](../../tools/server_match.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `_label` | function | [39](../../tools/server_match.py#L39) | Short name of a client command (its --name, else the script / program name). |
| `_maps` | function | [48](../../tools/server_match.py#L48) | Map names / families of arena.maps, or .xml paths. |
| `play_one` | function | [60](../../tools/server_match.py#L60) | One game: server thread + two client processes. Returns the server's result dict. |
| `main` | function | [84](../../tools/server_match.py#L84) | Command line: play the matches, print a summary, store the results. |

### [tools/probe_server.py](../../tools/probe_server.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `log` | function | [25](../../tools/probe_server.py#L25) | Thread-safe timestamped print. |
| `ProbeClient` | class | [31](../../tools/probe_server.py#L31) | Scripted client used to probe the real server's rules (moves fixed in advance). |
| `ProbeClient.__init__` | method | [33](../../tools/probe_server.py#L33) | Client with a script {turn: moves}, optional late answers and raw byte answers. |
| `ProbeClient.recv_exact` | method | [47](../../tools/probe_server.py#L47) | Read exactly n bytes from the server. |
| `ProbeClient.send_moves` | method | [57](../../tools/probe_server.py#L57) | Send a MOV message. |
| `ProbeClient.fallback_move` | method | [64](../../tools/probe_server.py#L64) | A simple legal move when the script has nothing for this turn. |
| `ProbeClient.run` | method | [77](../../tools/probe_server.py#L77) | Connect, then log every server message and answer every UPD. |
| `ProbeClient.play` | method | [125](../../tools/probe_server.py#L125) | Answer one UPD: scripted move, late answer or raw bytes. |
| `main` | function | [168](../../tools/probe_server.py#L168) | Command line: run one probe scenario with two clients. |

### [tools/play_bot.py](../../tools/play_bot.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `main` | function | [25](../../tools/play_bot.py#L25) | Command line: connect any arena bot to a game server and play. |

### [tools/gen_function_index.py](../../tools/gen_function_index.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `_doc` | function | [37](../../tools/gen_function_index.py#L37) | First line of a node's docstring (escaped for a markdown table). |
| `_entries` | function | [46](../../tools/gen_function_index.py#L46) | (name, kind, line, doc) for every top-level function, class and method of a file. |
| `render` | function | [63](../../tools/gen_function_index.py#L63) | The whole markdown index. |
| `check_chapter_links` | function | [92](../../tools/gen_function_index.py#L92) | Every chapter link to a definition (`name` + file + #L line) must point at the line defining `name`. |
| `_definition_lines` | function | [118](../../tools/gen_function_index.py#L118) | Candidate definition lines of `name` ('Class.method', a function, class, constant or field). |
| `fix_chapter_links` | function | [134](../../tools/gen_function_index.py#L134) | Move every chapter line link to the current definition line of the function it names. |
| `main` | function | [171](../../tools/gen_function_index.py#L171) | Write the index, or with --check fail if it (or a chapter's line link) is out of date. |

### [tools/tune_eval.py](../../tools/tune_eval.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `load_samples` | function | [38](../../tools/tune_eval.py#L38) | [(State, mover, result for the mover)] from recorded games (every `every`-th position). |
| `log_loss` | function | [56](../../tools/tune_eval.py#L56) | Mean cross-entropy of evaluate() against the game results. |
| `calibration` | function | [65](../../tools/tune_eval.py#L65) | [(predicted mean, observed mean, count)] per probability decile. |
| `fit` | function | [77](../../tools/tune_eval.py#L77) | Coordinate descent: try +-step on each constant, keep improvements, halve steps each round. |
| `main` | function | [100](../../tools/tune_eval.py#L100) | Command line: fit on --train, report on --check, print the arena spec. |

### [tools/informative_slots.py](../../tools/informative_slots.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `slot_information` | function | [25](../../tools/informative_slots.py#L25) | {(opp, map): [games, disagreement sum, plies sum]} from stored runs (first bot = reference). |
| `select` | function | [50](../../tools/informative_slots.py#L50) | Slots sorted by disagreement per ply, kept until `coverage` of the disagreement is reached. |
| `main` | function | [65](../../tools/informative_slots.py#L65) | Command line: write the informative slots of the given runs as JSON. |

## Tests

### [tests/test_rules.py](../../tests/test_rules.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `TestProbability` | class | [13](../../tests/test_rules.py#L13) |  |
| `TestProbability.test_server_formula` | method | [14](../../tests/test_rules.py#L14) |  |
| `TestProbability.test_defender_1_5x_is_random_not_sure` | method | [22](../../tests/test_rules.py#L22) |  |
| `TestProbability.test_sure_results` | method | [28](../../tests/test_rules.py#L28) |  |
| `TestCheckMoves` | class | [36](../../tests/test_rules.py#L36) |  |
| `TestCheckMoves.setUp` | method | [37](../../tests/test_rules.py#L37) |  |
| `TestCheckMoves.ok` | method | [40](../../tests/test_rules.py#L40) |  |
| `TestCheckMoves.test_legal_split` | method | [43](../../tests/test_rules.py#L43) |  |
| `TestCheckMoves.test_cheats` | method | [46](../../tests/test_rules.py#L46) |  |
| `TestCheckMoves.test_byte_overflow_refused` | method | [60](../../tests/test_rules.py#L60) |  |
| `TestApply` | class | [64](../../tests/test_rules.py#L64) |  |
| `TestApply.test_probe1_split_and_merged_attack` | method | [65](../../tests/test_rules.py#L65) |  |
| `TestApply.test_sure_kill_and_merge` | method | [75](../../tests/test_rules.py#L75) |  |
| `TestApply.test_mean_mode_deterministic` | method | [83](../../tests/test_rules.py#L83) |  |

### [tests/test_planner.py](../../tests/test_planner.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `random_state` | function | [14](../../tests/test_planner.py#L14) |  |
| `TestLegality` | class | [25](../../tests/test_planner.py#L25) |  |
| `TestLegality.test_fuzz_all_plans_legal` | method | [26](../../tests/test_planner.py#L26) |  |
| `TestLegality.test_safe_step_never_walks_into_bigger_humans` | method | [48](../../tests/test_planner.py#L48) |  |
| `TestSplits` | class | [55](../../tests/test_planner.py#L55) |  |
| `TestSplits.test_split_generated_for_two_small_houses` | method | [56](../../tests/test_planner.py#L56) |  |
| `TestSplits.test_no_split_when_disabled` | method | [66](../../tests/test_planner.py#L66) |  |
| `TestSplits.test_detachment_safety` | method | [74](../../tests/test_planner.py#L74) |  |
| `TestSplits.test_unsafe_house_not_split_to` | method | [83](../../tests/test_planner.py#L83) |  |

### [tests/test_agent.py](../../tests/test_agent.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `agent` | function | [16](../../tests/test_agent.py#L16) |  |
| `TestPuzzles` | class | [20](../../tests/test_agent.py#L20) |  |
| `TestPuzzles.test_takes_the_sure_kill` | method | [21](../../tests/test_agent.py#L21) |  |
| `TestPuzzles.test_does_not_suicide_or_wait_next_to_a_killer` | method | [27](../../tests/test_agent.py#L27) |  |
| `TestPuzzles.test_splits_to_take_two_adjacent_houses` | method | [36](../../tests/test_agent.py#L36) |  |
| `TestPuzzles.test_converges_two_groups_on_a_big_house` | method | [44](../../tests/test_agent.py#L44) |  |
| `TestSafety` | class | [54](../../tests/test_agent.py#L54) |  |
| `TestSafety.test_time_budget_big_map` | method | [55](../../tests/test_agent.py#L55) |  |
| `TestSafety.test_fuzz_never_illegal` | method | [63](../../tests/test_agent.py#L63) |  |
| `TestSafety.test_backup_model_never_illegal` | method | [79](../../tests/test_agent.py#L79) |  |
| `TestSafety.test_tournament_client_selects_the_model` | method | [97](../../tests/test_agent.py#L97) |  |
| `TestSafety.test_watchdog_sends_the_fallback_when_late` | method | [115](../../tests/test_agent.py#L115) |  |
| `TestSafety.test_gamestate_interface` | method | [137](../../tests/test_agent.py#L137) |  |

### [tests/test_protocol.py](../../tests/test_protocol.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `_launch` | function | [19](../../tests/test_protocol.py#L19) |  |
| `TestProtocol` | class | [27](../../tests/test_protocol.py#L27) |  |
| `TestProtocol._play` | method | [28](../../tests/test_protocol.py#L28) |  |
| `TestProtocol.test_full_game_no_cheat_no_timeout` | method | [47](../../tests/test_protocol.py#L47) |  |
| `TestProtocol.test_small_map_to_the_end` | method | [54](../../tests/test_protocol.py#L54) |  |

### [tests/test_arena.py](../../tests/test_arena.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `TestExternalBots` | class | [40](../../tests/test_arena.py#L40) |  |
| `TestExternalBots.setUp` | method | [41](../../tests/test_arena.py#L41) |  |
| `TestExternalBots.tearDown` | method | [50](../../tests/test_arena.py#L50) |  |
| `TestExternalBots.test_python_file_bots_are_loaded_and_play` | method | [53](../../tests/test_arena.py#L53) |  |
| `TestExternalBots.test_arena_task_against_a_file_bot_stores_its_files` | method | [63](../../tests/test_arena.py#L63) |  |
| `TestVariants` | class | [73](../../tests/test_arena.py#L73) |  |
| `TestVariants.test_flagship_and_backup` | method | [74](../../tests/test_arena.py#L74) |  |
| `TestVariants.test_styled_opponents_are_reproducible` | method | [86](../../tests/test_arena.py#L86) |  |
| `TestVariants.test_unknown_option_is_refused` | method | [92](../../tests/test_arena.py#L92) |  |
| `TestResultStoring` | class | [97](../../tests/test_arena.py#L97) |  |
| `TestResultStoring.test_history_and_comparisons_are_appended` | method | [98](../../tests/test_arena.py#L98) |  |
| `TestFasterBenchmarks` | class | [123](../../tests/test_arena.py#L123) |  |
| `TestFasterBenchmarks.test_rounds_keep_the_pairs_together` | method | [124](../../tests/test_arena.py#L124) |  |
| `TestFasterBenchmarks.test_paired_delta_and_drop_rule` | method | [133](../../tests/test_arena.py#L133) |  |
| `TestFasterBenchmarks.test_informative_slots_skip_games_nobody_disagrees_on` | method | [141](../../tests/test_arena.py#L141) |  |
| `TestTeammateMatches` | class | [166](../../tests/test_arena.py#L166) |  |
| `TestTeammateMatches.test_real_conditions_script_plays_and_records` | method | [167](../../tests/test_arena.py#L167) |  |
| `TestServerMatch` | class | [183](../../tests/test_arena.py#L183) |  |
| `TestServerMatch.test_two_programs_play_over_the_protocol` | method | [184](../../tests/test_arena.py#L184) |  |
