# 09 · Function index (generated)

Every class, function and method of our code, with a link to its line.
**Do not edit by hand**: run `python tools/gen_function_index.py` after changing the code.
Chapters 01–08 explain *why*; this page answers *where*.

## Tournament entry point

### [main.py](../../main.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `parse_args` | function | [9](../../main.py#L9) | Read --name / --delay and the server ip + port (the last two arguments, as the caller adds them). |
| `fallback_moves` | function | [41](../../main.py#L41) | One legal move (biggest group to a free neighbour that is not a source): never send an empty MOV. |
| `main` | function | [53](../../main.py#L53) | Protocol loop: NME, then SET/HUM/HME/MAP to build the state, then answer every UPD with a MOV. |

### [ai_agent.py](../../ai_agent.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `AIAgent` | class | [22](../../ai_agent.py#L22) | The tournament bot: "The Splitter" (splitter/agent.py, MCTS over joint plans with safe |
| `AIAgent.__init__` | method | [31](../../ai_agent.py#L31) | Create the Splitter engine (time budget from SPLITTER_TIME) and the starter fallback. |
| `AIAgent.pregame` | method | [45](../../ai_agent.py#L45) | Optional pre-game analysis (main.py --pregame): see SplitterAgent.pregame. |
| `AIAgent.reset` | method | [53](../../ai_agent.py#L53) | Forget the previous game (called by main.py on END). |
| `AIAgent.compute_moves` | method | [58](../../ai_agent.py#L58) | Splitter's moves for this turn; the starter strategy if the Splitter fails. |
| `StarterAgent` | class | [70](../../ai_agent.py#L70) | The original starter-kit strategy (walk to the nearest target). Kept as fallback/baseline. |
| `StarterAgent.__init__` | method | [73](../../ai_agent.py#L73) | Original starter-kit agent (kept as last-resort fallback and as a baseline opponent). |
| `StarterAgent.compute_moves` | method | [77](../../ai_agent.py#L77) | Computes the list of moves for the current turn. |

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

## Splitter: opponent model (HMMs)

### [splitter/observe.py](../../splitter/observe.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `TurnObservation` | class | [35](../../splitter/observe.py#L35) | One opponent turn as the HMM sees it (see module docstring), plus the flows behind it. |
| `TurnObservation.vector` | method | [44](../../splitter/observe.py#L44) | The four feature values, in FEATURES order. |
| `_nearest` | function | [49](../../splitter/observe.py#L49) | Distance from p to the closest of `cells` (INF if there is none). |
| `features_from_flows` | function | [58](../../splitter/observe.py#L58) | Classify a turn of `mover`, given the board before it (`mid`) and its creature flows. |
| `plan_features` | function | [111](../../splitter/observe.py#L111) | Features of a HYPOTHETICAL turn (used to score opponent plans with the HMM's prediction). |
| `reconstruct_flows` | function | [117](../../splitter/observe.py#L117) | Rebuild the creature flows of `mover`'s turn from the boards before (`mid`) and after it. |
| `OpponentTracker` | class | [215](../../splitter/observe.py#L215) | Remembers the board at our last decision and our moves, to observe the opponent's reply. |
| `OpponentTracker.__init__` | method | [218](../../splitter/observe.py#L218) | Empty tracker (nothing observed yet). |
| `OpponentTracker.reset` | method | [222](../../splitter/observe.py#L222) | Forget everything (new game). |
| `OpponentTracker.note_our_move` | method | [230](../../splitter/observe.py#L230) | Call right after choosing our moves for `state`. |
| `OpponentTracker.observe` | method | [236](../../splitter/observe.py#L236) | The opponent's last turn, reconstructed from our previous decision and this board. |

### [splitter/opponent_model.py](../../splitter/opponent_model.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `phase_of` | function | [35](../../splitter/opponent_model.py#L35) | Game phase used by the transitions: 0 while humans remain, 1 after. |
| `default_params` | function | [42](../../splitter/opponent_model.py#L42) | Hand-set starting parameters, from the behaviour measured in arena logs (chapter 11). |
| `load_params` | function | [64](../../splitter/opponent_model.py#L64) | Trained parameters if tools/train_opponent_model.py produced them, else the defaults. |
| `_normalize` | function | [73](../../splitter/opponent_model.py#L73) |  |
| `StyleHMM` | class | [82](../../splitter/opponent_model.py#L82) | Online opponent-style HMM: forward filtering + adaptive emissions + trust. |
| `StyleHMM.__init__` | method | [85](../../splitter/opponent_model.py#L85) | `prior_strength` = how many turns of evidence the starting emissions are worth. |
| `StyleHMM.reset` | method | [96](../../splitter/opponent_model.py#L96) | New game: uniform-prior belief, emissions back to the starting tables. |
| `StyleHMM.emission` | method | [104](../../splitter/opponent_model.py#L104) | P(obs \| z) for every mode z. |
| `StyleHMM.predicted_belief` | method | [113](../../splitter/opponent_model.py#L113) | Belief over the opponent's mode for its NEXT turn. |
| `StyleHMM.predict_features` | method | [118](../../splitter/opponent_model.py#L118) | For each feature, the predicted distribution of its value on the opponent's next turn. |
| `StyleHMM.update` | method | [124](../../splitter/opponent_model.py#L124) | Forward step with a new observation; returns the new belief. |
| `StyleHMM.trust` | method | [153](../../splitter/opponent_model.py#L153) | How much to rely on the model: 0 (ignore) .. 0.8, from its recent predictive gain. |
| `StyleHMM.mode_probs` | method | [159](../../splitter/opponent_model.py#L159) | The current belief as {mode name: probability}. |
| `_forward_backward` | function | [166](../../splitter/opponent_model.py#L166) | Scaled forward-backward: (gammas, xis per transition with its phase, log-likelihood). |
| `sequence_loglik` | function | [207](../../splitter/opponent_model.py#L207) | log P(sequence \| params): the held-out validation score. |
| `baum_welch` | function | [214](../../splitter/opponent_model.py#L214) | EM training of the style HMM on many observation sequences (one per opponent per game). |
| `GroupPrediction` | class | [267](../../splitter/opponent_model.py#L267) | What one enemy group is expected to do next. |
| `GroupPrediction.next_cell` | method | [275](../../splitter/opponent_model.py#L275) | The most likely next cell. |
| `GoalRecognizer` | class | [280](../../splitter/opponent_model.py#L280) | Per enemy group, a belief over its target, updated from its observed steps. |
| `GoalRecognizer.__init__` | method | [283](../../splitter/opponent_model.py#L283) | beta = rationality of the opponent; stay = probability it keeps its target. |
| `GoalRecognizer.reset` | method | [290](../../splitter/opponent_model.py#L290) | New game. |
| `GoalRecognizer.candidates` | method | [294](../../splitter/opponent_model.py#L294) | Targets a group of `size` at `pos` could plausibly be heading for. |
| `GoalRecognizer._dist` | method | [309](../../splitter/opponent_model.py#L309) |  |
| `GoalRecognizer.step_distribution` | method | [320](../../splitter/opponent_model.py#L320) | P(next cell \| target): a softmax of beta x (distance reduction), over 8 moves + staying. |
| `GoalRecognizer._prior` | method | [328](../../splitter/opponent_model.py#L328) | Sticky transition onto the current candidates (vanished targets are dropped). |
| `GoalRecognizer._rekey` | method | [339](../../splitter/opponent_model.py#L339) | Moving targets (groups) are matched to the nearest current group of the same side. |
| `GoalRecognizer.update` | method | [353](../../splitter/opponent_model.py#L353) | Bayes update of every enemy group's target from its observed step (mid -> after). |
| `GoalRecognizer.predict` | method | [379](../../splitter/opponent_model.py#L379) | Next-step prediction for every current enemy group. |
| `_point` | function | [400](../../splitter/opponent_model.py#L400) | (1 - eps) on `cell`, eps spread over every option (8 neighbours + staying). |
| `greedy_steps` | function | [408](../../splitter/opponent_model.py#L408) | Each group walks to the nearest house it can convert, else to the nearest enemy group. |
| `away_steps` | function | [422](../../splitter/opponent_model.py#L422) | Each group steps to the neighbour farthest from the other side's groups. |
| `plan_steps` | function | [432](../../splitter/opponent_model.py#L432) | Main destination of every group under a move list (staying if it did not move). |
| `planner_steps` | function | [447](../../splitter/opponent_model.py#L447) | Steps of the top plan our own planner would play for `mover` (a model of a smart bot). |
| `PolicyHMM` | class | [454](../../splitter/opponent_model.py#L454) | Which policy is the opponent following? Hidden state = one of EXPERTS; emission = how likely |
| `PolicyHMM.__init__` | method | [461](../../splitter/opponent_model.py#L461) | Uses `goals` as the GOAL expert; eps = noise every expert allows for. |
| `PolicyHMM.reset` | method | [468](../../splitter/opponent_model.py#L468) | New game: no preference between experts. |
| `PolicyHMM.expert_dists` | method | [474](../../splitter/opponent_model.py#L474) | For each expert, its next-step distribution for every group of `mover` in `state`. |
| `PolicyHMM.mixture` | method | [491](../../splitter/opponent_model.py#L491) | Belief-weighted prediction for every group. |
| `PolicyHMM.update` | method | [502](../../splitter/opponent_model.py#L502) | Forward step: dists computed on the board before the opponent's turn, actual = its steps. |
| `PolicyHMM.accuracy` | method | [522](../../splitter/opponent_model.py#L522) | Share of enemy group steps our mixture predicted (top-1) so far this game. |
| `PolicyHMM.trust` | method | [527](../../splitter/opponent_model.py#L527) | 0 .. 0.8: how much the search should rely on the predicted moves (from the accuracy). |
| `Predictions` | class | [539](../../splitter/opponent_model.py#L539) | Everything the planner / search / evaluation need to know about the opponent. |
| `Predictions.p_gamble` | method | [548](../../splitter/opponent_model.py#L548) | Probability that the opponent's next attack (if any) is a coin flip or long shot. |
| `OpponentModel` | class | [555](../../splitter/opponent_model.py#L555) | Observe the opponent every turn and predict its next move: |
| `OpponentModel.__init__` | method | [563](../../splitter/opponent_model.py#L563) | Style HMM (trained parameters if available), goal recognizer, policy HMM, move tracker. |
| `OpponentModel.reset` | method | [571](../../splitter/opponent_model.py#L571) | New game. |
| `OpponentModel.observe` | method | [579](../../splitter/opponent_model.py#L579) | Call at the start of our turn: learn from the opponent's last move. |
| `OpponentModel.note_our_move` | method | [594](../../splitter/opponent_model.py#L594) | Call after choosing our moves. |
| `OpponentModel.trust` | method | [599](../../splitter/opponent_model.py#L599) | How much the search should follow the predictions (policy HMM accuracy this game). |
| `OpponentModel.p_gamble` | method | [604](../../splitter/opponent_model.py#L604) | Probability that an attack by this opponent is a coin flip or a long shot (style HMM). |
| `OpponentModel.p_longshot` | method | [611](../../splitter/opponent_model.py#L611) | Probability that an attack by this opponent is a long shot (P < 0.5). |
| `OpponentModel.tendencies` | method | [617](../../splitter/opponent_model.py#L617) | Measured tendencies for adaptive settings: aggression, split rate, long-shot rate. |
| `OpponentModel.score_plans` | method | [623](../../splitter/opponent_model.py#L623) | Model probability (up to a constant) of each candidate opponent plan in `state`: the |
| `OpponentModel.predictions` | method | [655](../../splitter/opponent_model.py#L655) | Predictions for the opponent's next turn in `state` (we are `side`). |

## Splitter: plan generator

### [splitter/planner.py](../../splitter/planner.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `PlanConfig` | class | [32](../../splitter/planner.py#L32) | Every tunable of the plan generator (the bot's variants are just different PlanConfigs). |
| `Goal` | class | [56](../../splitter/planner.py#L56) | One candidate objective for one group: a target cell, a kind and an estimated value. |
| `Plan` | class | [66](../../splitter/planner.py#L66) | A joint plan = one full turn (moves of all our groups), with its prior score and a tag. |
| `_step_dir` | function | [77](../../splitter/planner.py#L77) | -1, 0 or +1: the direction of one king step from coordinate a towards b. |
| `straight_path` | function | [82](../../splitter/planner.py#L82) | Cells visited by a king walking diagonally first, then straight (excludes src). |
| `enemy_attack_loss` | function | [93](../../splitter/planner.py#L93) | Expected creatures we lose if we stand on `cell` with `count` and the best adjacent enemy |
| `race_won` | function | [107](../../splitter/planner.py#L107) | Do we reach `target` (a house needing `need`) no later than any enemy group that can take it? |
| `detachment_safe` | function | [117](../../splitter/planner.py#L117) | Can a detachment of k creatures walk from src to the house `target` (h humans, k >= h), |
| `safe_step` | function | [145](../../splitter/planner.py#L145) | Best neighbour of src to walk `count` creatures towards `goal`: |
| `border_distance` | function | [194](../../splitter/planner.py#L194) | Number of cells between p and the nearest edge of the board (0 = on the edge). |
| `flee_cell` | function | [199](../../splitter/planner.py#L199) | Where to run: far from the threats FIRST, but into open space (a king chased along an edge or |
| `candidate_goals` | function | [222](../../splitter/planner.py#L222) | Ranked goals for one group (best first). `committed` = the goal this group had last turn. |
| `_Builder` | class | [299](../../splitter/planner.py#L299) | Turns a set of orders (src, count, goal) into a legal list of moves. |
| `_Builder.__init__` | method | [302](../../splitter/planner.py#L302) | One builder per generate_plans call: its caches are only valid for this state. |
| `_Builder.build` | method | [311](../../splitter/planner.py#L311) | -> (moves, intents). Orders whose goal is their own cell mean 'stay'. |
| `_orders_value` | function | [338](../../splitter/planner.py#L338) | Prior score of a plan = sum of the values of the goals its orders pursue. |
| `generate_plans` | function | [343](../../splitter/planner.py#L343) | The short list of joint plans for `side` to move. Never empty while `side` has creatures. |
| `_split_orders` | function | [470](../../splitter/planner.py#L470) | Yield (orders, tag, bonus) for plans where the group at `pos` sends detachments. |
| `_preempt_orders` | function | [547](../../splitter/planner.py#L547) | Pre-emptive plans from the opponent model's predicted targets (opponent_model.GoalRecognizer): |
| `_pincer_orders` | function | [598](../../splitter/planner.py#L598) | Yield (orders, tag) converging groups on the best house that only their sum can convert. |
| `fallback_plan` | function | [636](../../splitter/planner.py#L636) | A plain legal move: the biggest group steps to its least dangerous empty/friendly neighbour. |
| `quick_plan` | function | [656](../../splitter/planner.py#L656) | Cheap greedy policy for rollouts: take what is adjacent, else walk to the best target. |

## Splitter: evaluation

### [splitter/evaluate.py](../../splitter/evaluate.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `resolve_immediate` | function | [27](../../splitter/evaluate.py#L27) | Groups after the player to move takes its certain gains (kills >= 1.5x, conversions). |
| `project_race` | function | [51](../../splitter/evaluate.py#L51) | Projected sizes after both sides collect the houses they reach first (see module doc). |
| `_contest` | function | [104](../../splitter/evaluate.py#L104) | Is the capture of house hp by runner r (ending with size_after at time t) safe? |
| `exposure` | function | [123](../../splitter/evaluate.py#L123) | Expected creatures lost because enemies can attack these groups soon. |
| `evaluate` | function | [152](../../splitter/evaluate.py#L152) | P(side wins) estimate in [0, 1]. strike_p = lowest odds at which the enemy strikes (I3). |
| `material_balance` | function | [205](../../splitter/evaluate.py#L205) | Quick (our total - their total) / everything, used to decide whether we are behind. |

## Splitter: search

### [splitter/mcts.py](../../splitter/mcts.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `Node` | class | [27](../../splitter/mcts.py#L27) | One node of the open-loop tree: the plan that leads to it, statistics, children. |
| `Node.__init__` | method | [31](../../splitter/mcts.py#L31) | New node reached by `mover` playing `plan`; prior = the plan's normalized prior. |
| `MCTS` | class | [43](../../splitter/mcts.py#L43) | Monte Carlo Tree Search over joint plans (see the module docstring). |
| `MCTS.__init__` | method | [45](../../splitter/mcts.py#L45) | Configure exploration, rollouts, widening and the plan configs of both sides. |
| `MCTS._plans` | method | [80](../../splitter/mcts.py#L80) | Plans for `side` at a tree node (opponent: gambles allowed), priors normalized to [0, 1]. |
| `MCTS._select` | method | [96](../../splitter/mcts.py#L96) | UCT + progressive bias. Only called on a node that has children. |
| `MCTS._widen_limit` | method | [117](../../splitter/mcts.py#L117) | Progressive widening: how many children a node with `visits` visits may have. |
| `MCTS.search` | method | [122](../../splitter/mcts.py#L122) | Run iterations until the deadline and return the most visited root plan. |
| `MCTS._iterate` | method | [156](../../splitter/mcts.py#L156) | One iteration: select / expand by replaying plans with fresh dice, roll out, evaluate, back up. |
| `MCTS.root_stats` | method | [215](../../splitter/mcts.py#L215) | [(visits, mean value, tag, moves)] of the root's children, most visited first. |
| `_strike` | function | [225](../../splitter/mcts.py#L225) | A gambling opponent's rollout move: strike the best adjacent target it beats at >= min_p. |

## Splitter: agent and safety net

### [splitter/agent.py](../../splitter/agent.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `SplitterAgent` | class | [35](../../splitter/agent.py#L35) | The tournament bot: planner + MCTS under a strict time budget, with a legal-move guarantee. |
| `SplitterAgent.__init__` | method | [37](../../splitter/agent.py#L37) | Build the plan config (variants via keyword arguments) and the MCTS engine. |
| `SplitterAgent.reset` | method | [74](../../splitter/agent.py#L74) | Call between games (main.py does it on END). |
| `SplitterAgent.compute_moves` | method | [87](../../splitter/agent.py#L87) | main.py interface: moves for the GameState kept from the server messages. |
| `SplitterAgent.compute_moves_board` | method | [102](../../splitter/agent.py#L102) | Othmane's / Ronita's interface: moves for a BoardState and a Species. |
| `SplitterAgent.choose` | method | [109](../../splitter/agent.py#L109) | Arena interface: moves for a splitter State (fastest, true ply known). |
| `SplitterAgent._remaining_plies` | method | [116](../../splitter/agent.py#L116) | Plies left, from the ply cap and from the game clock (whichever ends first). |
| `SplitterAgent._safe_choose` | method | [126](../../splitter/agent.py#L126) | Never-fail wrapper: search, then validate, then fallbacks; always returns legal moves. |
| `SplitterAgent._choose` | method | [169](../../splitter/agent.py#L169) | Decide: evaluate, generate plans (with last turn's intents), search, remember intents. |
| `SplitterAgent.pregame` | method | [215](../../splitter/agent.py#L215) | I6 (flag --pregame, off by default): use the idle time between MAP and the first UPD. |
| `SplitterAgent._adapt_settings` | method | [233](../../splitter/agent.py#L233) | I5: adjust risk settings to the observed opponent (after 8 observed turns): |
| `prize_dominated` | function | [256](../../splitter/agent.py#L256) | Map-aware strategy (chapter 08): when one house holds >= `share` of all humans and is bigger |
| `_emergency_move` | function | [268](../../splitter/agent.py#L268) | Last resort: any legal one-step move of the biggest group to a non-hostile cell. |

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
| `state_to_dict` | function | [46](../../arena/referee.py#L46) | JSON-friendly board: lists of [x, y, n] for humans, vampires and werewolves. |
| `state_from_dict` | function | [53](../../arena/referee.py#L53) | Inverse of state_to_dict. |
| `play_game` | function | [59](../../arena/referee.py#L59) | Play one full game between two bots with the real server's rules (see module docstring). |

### [arena/run.py](../../arena/run.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `_play_task` | function | [39](../../arena/run.py#L39) | Worker: play one game (bot vs opponent on a map and side) and return its CSV row. |
| `_score` | function | [80](../../arena/run.py#L80) | Win rate (win 1, draw 0.5) with its standard error. |
| `report` | function | [89](../../arena/run.py#L89) | Print the results grouped by opponent, map, our side and first player. |
| `_cost` | function | [121](../../arena/run.py#L121) | Rough game duration, to schedule the longest games first (no idle workers at the end). |
| `compare` | function | [129](../../arena/run.py#L129) | Paired comparison of every bot with the first one: same opponent, map, side and seed. |
| `main` | function | [155](../../arena/run.py#L155) | Command line: build every (bot, opponent, map, side, game) task, run them in ONE pool, report. |

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
| `_doc` | function | [37](../../tools/gen_function_index.py#L37) | First line of a node's docstring (escaped for a markdown table). |
| `_entries` | function | [46](../../tools/gen_function_index.py#L46) | (name, kind, line, doc) for every top-level function, class and method of a file. |
| `render` | function | [63](../../tools/gen_function_index.py#L63) | The whole markdown index. |
| `check_chapter_links` | function | [92](../../tools/gen_function_index.py#L92) | Every [`name`](../../file.py#Lnn) link in the chapters must point at the line defining `name`. |
| `_definition_lines` | function | [118](../../tools/gen_function_index.py#L118) | Candidate definition lines of `name` ('Class.method', a function, class, constant or field). |
| `fix_chapter_links` | function | [134](../../tools/gen_function_index.py#L134) | Move every chapter line link to the current definition line of the function it names. |
| `main` | function | [171](../../tools/gen_function_index.py#L171) | Write the index, or with --check fail if it (or a chapter's line link) is out of date. |

### [tools/opponent_report.py](../../tools/opponent_report.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `_main_dest` | function | [32](../../tools/opponent_report.py#L32) |  |
| `_greedy_step` | function | [40](../../tools/opponent_report.py#L40) |  |
| `_planner_steps` | function | [49](../../tools/opponent_report.py#L49) |  |
| `analyse` | function | [61](../../tools/opponent_report.py#L61) |  |
| `main` | function | [136](../../tools/opponent_report.py#L136) |  |

### [tools/train_opponent_model.py](../../tools/train_opponent_model.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `load_games` | function | [42](../../tools/train_opponent_model.py#L42) | [(record, {side: [(obs, phase, mid, after, rflows, true_steps)]})] for every game. |
| `sequences` | function | [62](../../tools/train_opponent_model.py#L62) |  |
| `per_turn` | function | [67](../../tools/train_opponent_model.py#L67) |  |
| `policy_score` | function | [72](../../tools/train_opponent_model.py#L72) | Average log-likelihood per enemy-group step of the policy-HMM mixture prediction. |
| `main` | function | [94](../../tools/train_opponent_model.py#L94) |  |

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

### [tests/test_opponent_model.py](../../tests/test_opponent_model.py)

| Name | Kind | Line | Purpose (first docstring line) |
|---|---|---|---|
| `flows_of` | function | [28](../../tests/test_opponent_model.py#L28) |  |
| `TestObservation` | class | [32](../../tests/test_opponent_model.py#L32) |  |
| `TestObservation.check` | method | [33](../../tests/test_opponent_model.py#L33) |  |
| `TestObservation.test_plain_split_conversion` | method | [40](../../tests/test_opponent_model.py#L40) |  |
| `TestObservation.test_crossing_sources_are_not_a_split` | method | [47](../../tests/test_opponent_model.py#L47) |  |
| `TestObservation.test_long_shot_attack` | method | [53](../../tests/test_opponent_model.py#L53) |  |
| `TestObservation.test_tracker_end_to_end` | method | [58](../../tests/test_opponent_model.py#L58) |  |
| `TestHMM` | class | [69](../../tests/test_opponent_model.py#L69) |  |
| `TestHMM.test_forward_matches_brute_force` | method | [70](../../tests/test_opponent_model.py#L70) |  |
| `TestHMM.test_baum_welch_improves_likelihood` | method | [84](../../tests/test_opponent_model.py#L84) |  |
| `TestHMM.test_style_belief_recovers_a_splitter` | method | [100](../../tests/test_opponent_model.py#L100) |  |
| `TestHMM.test_goal_recognition_straight_walk` | method | [108](../../tests/test_opponent_model.py#L108) |  |
| `TestHMM.test_policy_hmm_identifies_greedy_opponent` | method | [121](../../tests/test_opponent_model.py#L121) |  |
| `TestIntegration` | class | [138](../../tests/test_opponent_model.py#L138) |  |
| `TestIntegration.test_agent_with_model_never_illegal` | method | [139](../../tests/test_opponent_model.py#L139) |  |
