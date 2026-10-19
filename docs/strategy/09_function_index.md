# 09 · Function index (generated)

Every class, function and method of our code, with a link to its line.
**Do not edit by hand**: run `python tools/gen_function_index.py` after changing the code.
Chapters 01–08 explain *why*; this page answers *where*.

## Tournament entry point

### [main.py](../../main.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `parse_args` | function | [9](../../main.py#L9) | Read --name / --delay and the server ip + port (the last two arguments, as the caller adds them). |
| `fallback_moves` | function | [37](../../main.py#L37) | One legal move (biggest group to a free neighbour that is not a source): never send an empty MOV. |
| `main` | function | [49](../../main.py#L49) | Protocol loop: NME, then SET/HUM/HME/MAP to build the state, then answer every UPD with a MOV. |

### [ai_agent.py](../../ai_agent.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `AIAgent` | class | [22](../../ai_agent.py#L22) | The tournament bot: "The Splitter" (splitter/agent.py, MCTS over joint plans with safe |
| `AIAgent.__init__` | method | [31](../../ai_agent.py#L31) | Create the Splitter engine (time budget from SPLITTER_TIME) and the starter fallback. |
| `AIAgent.reset` | method | [45](../../ai_agent.py#L45) | Forget the previous game (called by main.py on END). |
| `AIAgent.compute_moves` | method | [50](../../ai_agent.py#L50) | Splitter's moves for this turn; the starter strategy if the Splitter fails. |
| `StarterAgent` | class | [62](../../ai_agent.py#L62) | The original starter-kit strategy (walk to the nearest target). Kept as fallback/baseline. |
| `StarterAgent.__init__` | method | [65](../../ai_agent.py#L65) | Original starter-kit agent (kept as last-resort fallback and as a baseline opponent). |
| `StarterAgent.compute_moves` | method | [69](../../ai_agent.py#L69) | Computes the list of moves for the current turn. |

### [network.py](../../network.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `NetworkClient` | class | [5](../../network.py#L5) |  |
| `NetworkClient.__init__` | method | [6](../../network.py#L6) |  |
| `NetworkClient.connect` | method | [11](../../network.py#L11) |  |
| `NetworkClient._recv_exact` | method | [16](../../network.py#L16) |  |
| `NetworkClient.send_name` | method | [25](../../network.py#L25) |  |
| `NetworkClient.send_moves` | method | [31](../../network.py#L31) | moves: list of (x_src, y_src, count, x_dst, y_dst) |
| `NetworkClient.receive_command` | method | [42](../../network.py#L42) |  |
| `NetworkClient.close` | method | [89](../../network.py#L89) |  |

### [game_state.py](../../game_state.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `Species` | class | [4](../../game_state.py#L4) |  |
| `Cell` | class | [8](../../game_state.py#L8) |  |
| `Cell.__init__` | method | [10](../../game_state.py#L10) |  |
| `Cell.is_empty` | method | [15](../../game_state.py#L15) |  |
| `Cell.copy` | method | [18](../../game_state.py#L18) |  |
| `GameState` | class | [21](../../game_state.py#L21) |  |
| `GameState.__init__` | method | [22](../../game_state.py#L22) |  |
| `GameState.set_grid` | method | [32](../../game_state.py#L32) |  |
| `GameState.set_houses` | method | [37](../../game_state.py#L37) |  |
| `GameState.set_home` | method | [40](../../game_state.py#L40) |  |
| `GameState.apply_updates` | method | [43](../../game_state.py#L43) |  |
| `GameState.get_our_groups` | method | [65](../../game_state.py#L65) |  |
| `GameState.get_enemy_groups` | method | [73](../../game_state.py#L73) |  |
| `GameState.get_human_groups` | method | [81](../../game_state.py#L81) |  |
| `GameState.chebyshev_dist` | method | [88](../../game_state.py#L88) |  |
| `GameState.get_legal_adjacent_cells` | method | [91](../../game_state.py#L91) |  |
| `GameState.reset_for_new_game` | method | [103](../../game_state.py#L103) |  |
| `GameState.render_board` | method | [110](../../game_state.py#L110) | Renders a clean ASCII board representation with colors. |

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
| `_pincer_orders` | function | [533](../../splitter/planner.py#L533) | Yield (orders, tag) converging groups on the best house that only their sum can convert. |
| `fallback_plan` | function | [571](../../splitter/planner.py#L571) | A plain legal move: the biggest group steps to its least dangerous empty/friendly neighbour. |
| `quick_plan` | function | [591](../../splitter/planner.py#L591) | Cheap greedy policy for rollouts: take what is adjacent, else walk to the best target. |

## Splitter: evaluation

### [splitter/evaluate.py](../../splitter/evaluate.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `resolve_immediate` | function | [27](../../splitter/evaluate.py#L27) | Groups after the player to move takes its certain gains (kills >= 1.5x, conversions). |
| `project_race` | function | [51](../../splitter/evaluate.py#L51) | Projected sizes after both sides collect the houses they reach first (see module doc). |
| `_contest` | function | [104](../../splitter/evaluate.py#L104) | Is the capture of house hp by runner r (ending with size_after at time t) safe? |
| `exposure` | function | [123](../../splitter/evaluate.py#L123) | Expected creatures lost because enemies can attack these groups soon. |
| `evaluate` | function | [151](../../splitter/evaluate.py#L151) | P(side wins) estimate in [0, 1]. |
| `material_balance` | function | [199](../../splitter/evaluate.py#L199) | Quick (our total - their total) / everything, used to decide whether we are behind. |

## Splitter: search

### [splitter/mcts.py](../../splitter/mcts.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `Node` | class | [27](../../splitter/mcts.py#L27) | One node of the open-loop tree: the plan that leads to it, statistics, children. |
| `Node.__init__` | method | [31](../../splitter/mcts.py#L31) | New node reached by `mover` playing `plan`; prior = the plan's normalized prior. |
| `MCTS` | class | [43](../../splitter/mcts.py#L43) | Monte Carlo Tree Search over joint plans (see the module docstring). |
| `MCTS.__init__` | method | [45](../../splitter/mcts.py#L45) | Configure exploration, rollouts, widening and the plan configs of both sides. |
| `MCTS._plans` | method | [69](../../splitter/mcts.py#L69) | Plans for `side` at a tree node (opponent: gambles allowed), priors normalized to [0, 1]. |
| `MCTS._select` | method | [79](../../splitter/mcts.py#L79) | UCT + progressive bias. Only called on a node that has children. |
| `MCTS._widen_limit` | method | [95](../../splitter/mcts.py#L95) | Progressive widening: how many children a node with `visits` visits may have. |
| `MCTS.search` | method | [100](../../splitter/mcts.py#L100) | Run iterations until the deadline and return the most visited root plan. |
| `MCTS._iterate` | method | [125](../../splitter/mcts.py#L125) | One iteration: select / expand by replaying plans with fresh dice, roll out, evaluate, back up. |
| `MCTS.root_stats` | method | [175](../../splitter/mcts.py#L175) | [(visits, mean value, tag, moves)] of the root's children, most visited first. |

## Splitter: agent and safety net

### [splitter/agent.py](../../splitter/agent.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `SplitterAgent` | class | [33](../../splitter/agent.py#L33) | The tournament bot: planner + MCTS under a strict time budget, with a legal-move guarantee. |
| `SplitterAgent.__init__` | method | [35](../../splitter/agent.py#L35) | Build the plan config (variants via keyword arguments) and the MCTS engine. |
| `SplitterAgent.reset` | method | [59](../../splitter/agent.py#L59) | Call between games (main.py does it on END). |
| `SplitterAgent.compute_moves` | method | [66](../../splitter/agent.py#L66) | main.py interface: moves for the GameState kept from the server messages. |
| `SplitterAgent.compute_moves_board` | method | [81](../../splitter/agent.py#L81) | Othmane's / Ronita's interface: moves for a BoardState and a Species. |
| `SplitterAgent.choose` | method | [88](../../splitter/agent.py#L88) | Arena interface: moves for a splitter State (fastest, true ply known). |
| `SplitterAgent._remaining_plies` | method | [95](../../splitter/agent.py#L95) | Plies left, from the ply cap and from the game clock (whichever ends first). |
| `SplitterAgent._safe_choose` | method | [105](../../splitter/agent.py#L105) | Never-fail wrapper: search, then validate, then fallbacks; always returns legal moves. |
| `SplitterAgent._choose` | method | [132](../../splitter/agent.py#L132) | Decide: evaluate, generate plans (with last turn's intents), search, remember intents. |
| `_emergency_move` | function | [166](../../splitter/agent.py#L166) | Last resort: any legal one-step move of the biggest group to a non-hostile cell. |

## Arena (benchmarking)

### [arena/maps.py](../../arena/maps.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `load_xml` | function | [28](../../arena/maps.py#L28) | Read a server map file (XML) into a State. |
| `write_xml` | function | [43](../../arena/maps.py#L43) | Save a State as a server map file, so the real GUI can load it. |
| `_cheb` | function | [58](../../arena/maps.py#L58) | King-move distance (local copy, keeps this module independent). |
| `symmetric_map` | function | [63](../../arena/maps.py#L63) | Random point-symmetric map: mirrored starts and mirrored houses of equal size. |
| `build_suite` | function | [127](../../arena/maps.py#L127) | name: 'all', 'given', a family name, or a comma-separated list of map names/families. |
| `render` | function | [153](../../arena/maps.py#L153) | ASCII board: V12 / W7 / H4, '.' empty. |

### [arena/opponents.py](../../arena/opponents.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `_species` | function | [34](../../arena/opponents.py#L34) | V / W -> game_state.Species. |
| `load_vendor` | function | [39](../../arena/opponents.py#L39) | Import `modules` from arena/vendor/<branch> without clashing with the repo's modules. |
| `Bot` | class | [63](../../arena/opponents.py#L63) | Common interface of every arena bot: reset() and play(state, side) -> moves. |
| `Bot.reset` | method | [67](../../arena/opponents.py#L67) | Prepare for a new game. |
| `Bot.play` | method | [70](../../arena/opponents.py#L70) | Moves for `side` in `state` (implemented by the adapters). |
| `GameStateBot` | class | [75](../../arena/opponents.py#L75) | Adapter for agents with compute_moves(GameState) (repo starter, Dana's bots, AIAgent). |
| `GameStateBot.__init__` | method | [77](../../arena/opponents.py#L77) | Wrap an agent factory; a fresh agent is built for every game. |
| `GameStateBot.reset` | method | [84](../../arena/opponents.py#L84) | Fresh agent instance for a new game. |
| `GameStateBot.play` | method | [89](../../arena/opponents.py#L89) | Convert the State to a GameState and ask the agent. |
| `BoardBot` | class | [97](../../arena/opponents.py#L97) | Adapter for agents with compute_moves(BoardState, Species) (Othmane's and Ronita's bots). |
| `BoardBot.__init__` | method | [99](../../arena/opponents.py#L99) | Wrap an agent factory; a fresh agent is built for every game. |
| `BoardBot.reset` | method | [105](../../arena/opponents.py#L105) | Fresh agent instance for a new game. |
| `BoardBot.play` | method | [109](../../arena/opponents.py#L109) | Convert the State to a BoardState and ask the agent. |
| `SplitterBot` | class | [114](../../arena/opponents.py#L114) | Our bot through its fast choose(State, side) interface. |
| `SplitterBot.__init__` | method | [116](../../arena/opponents.py#L116) | SplitterAgent with the given keyword arguments (game clock disabled in the arena). |
| `SplitterBot.reset` | method | [123](../../arena/opponents.py#L123) | Forget the previous game. |
| `SplitterBot.play` | method | [127](../../arena/opponents.py#L127) | Moves chosen by the SplitterAgent. |
| `_parse_value` | function | [132](../../arena/opponents.py#L132) | '3' -> 3, '0.5' -> 0.5, 'true' -> True, else the string (for 'Splitter:key=value'). |
| `_registry` | function | [143](../../arena/opponents.py#L143) | name -> builder(time_limit) for every non-Splitter bot (teammates' bots are loaded lazily). |
| `bot_names` | function | [210](../../arena/opponents.py#L210) | Every bot name make_bot() accepts. |
| `SnapshotBot` | class | [215](../../arena/opponents.py#L215) | A frozen copy of splitter/ (arena/snapshots/splitter_<version>), see arena/snapshot.py. |
| `SnapshotBot.__init__` | method | [218](../../arena/opponents.py#L218) | SplitterAgent imported from arena/snapshots/splitter_<version>/. |
| `make_bot` | function | [226](../../arena/opponents.py#L226) | spec: a registry name, a Splitter variant, 'Splitter:key=val,key=val' or 'Snap:<version>[:k=v,..]'. |

### [arena/referee.py](../../arena/referee.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `SideStats` | class | [22](../../arena/referee.py#L22) | Per-side statistics of one game: decision times, problems, split turns, max groups. |
| `GameResult` | class | [34](../../arena/referee.py#L34) | Outcome of one game: winner, length, final totals, end reason, stats and move log. |
| `play_game` | function | [45](../../arena/referee.py#L45) | Play one full game between two bots with the real server's rules (see module docstring). |

### [arena/run.py](../../arena/run.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `_play_task` | function | [38](../../arena/run.py#L38) | Worker: play one game (bot vs opponent on a map and side) and return its CSV row. |
| `_score` | function | [71](../../arena/run.py#L71) | Win rate (win 1, draw 0.5) with its standard error. |
| `report` | function | [80](../../arena/run.py#L80) | Print the results grouped by opponent, map, our side and first player. |
| `main` | function | [107](../../arena/run.py#L107) | Command line: build every (opponent, map, side, game) task, run them in parallel, report. |

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

## Tools

### [tools/fake_server.py](../../tools/fake_server.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `_recv_exact` | function | [33](../../tools/fake_server.py#L33) | Read exactly n bytes from the socket (optionally before a deadline). |
| `FakeServer` | class | [51](../../tools/fake_server.py#L51) | One-game headless server with the real protocol, rules, time limit and cheating checks. |
| `FakeServer.__init__` | method | [53](../../tools/fake_server.py#L53) | Listen on 127.0.0.1:port (0 = any free port) for a game on `state`. |
| `FakeServer._cells` | method | [68](../../tools/fake_server.py#L68) | Encode cells as the protocol's 5-byte tuples (x, y, humans, vampires, werewolves). |
| `FakeServer._send_upd` | method | [76](../../tools/fake_server.py#L76) | Send a MAP or UPD message with the given cells. |
| `FakeServer.run` | method | [81](../../tools/fake_server.py#L81) | Accept 2 players, play the whole game, send END and BYE, return the result. |
| `main` | function | [178](../../tools/fake_server.py#L178) | Command line: run the fake server on a map file. |

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
| `_doc` | function | [35](../../tools/gen_function_index.py#L35) | First line of a node's docstring (escaped for a markdown table). |
| `_entries` | function | [44](../../tools/gen_function_index.py#L44) | (name, kind, line, doc) for every top-level function, class and method of a file. |
| `render` | function | [61](../../tools/gen_function_index.py#L61) | The whole markdown index. |
| `check_chapter_links` | function | [90](../../tools/gen_function_index.py#L90) | Every [`name`](../../file.py#Lnn) link in the chapters must point at the line defining `name`. |
| `main` | function | [116](../../tools/gen_function_index.py#L116) | Write the index, or with --check fail if it (or a chapter's line link) is out of date. |

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
| `TestSafety.test_gamestate_interface` | method | [79](../../tests/test_agent.py#L79) |  |

### [tests/test_protocol.py](../../tests/test_protocol.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `_launch` | function | [19](../../tests/test_protocol.py#L19) |  |
| `TestProtocol` | class | [27](../../tests/test_protocol.py#L27) |  |
| `TestProtocol._play` | method | [28](../../tests/test_protocol.py#L28) |  |
| `TestProtocol.test_full_game_no_cheat_no_timeout` | method | [47](../../tests/test_protocol.py#L47) |  |
| `TestProtocol.test_small_map_to_the_end` | method | [54](../../tests/test_protocol.py#L54) |  |
