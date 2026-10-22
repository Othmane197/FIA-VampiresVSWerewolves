# ⚔️ Vampires VS Werewolves — Python Client Starter Kit
**FIA (Fondements de l'Intelligence Artificielle) — CentraleSupélec / Centrale Casablanca**

A clean, lightweight, and complete Python template to connect to the official game server and build your own competitive AI agent.

---

## 🔀 This branch: "The Splitter" (MCTS + safe splitting)

`main.py` now plays **The Splitter** (`ai_agent.AIAgent` → [`splitter/`](splitter/)). Full strategy documentation (every algorithm, script and function): [docs/strategy/](docs/strategy/README.md). Real-server rules (probed and disassembled, with differences from the PDF): [docs/SERVER_FINDINGS.md](docs/SERVER_FINDINGS.md).

```bash
python main.py <IP> <PORT> --name MyTeam                 # tournament: the flagship (1.5 s/move, watchdog at 1.8 s)
SPLITTER_MODEL=backup python main.py <IP> <PORT>         # the backup model (calibrated evaluation)
python -m unittest discover tests                        # 39 tests incl. end-to-end protocol vs tools/fake_server.py
python tools/gen_function_index.py --check               # docs/strategy line links still match the code
python -m arena.fetch_opponents --fetch                  # copy the teammates' latest bots from their branches
python -m arena.run --games 2 --time 0.2                 # flagship vs the panel on 14 maps, both species
python -m arena.run --bot Splitter Splitter-Calibrated --slots arena/slots/holdout.json --drop-worse --time 0.25
                                                         # paired comparison on the informative games only (2-3x faster)
python -m arena.run --opp "py:../Other/ai_agent.py"      # any external Python bot file
python tools/teammate_matches.py                         # REAL conditions, teammates' LATEST code: 4 games each (2 per role), recorded
python tools/server_match.py --a "python main.py {host} {port}" --b "<any client cmd> {host} {port}"
python -m arena.history                                  # every stored run and comparison
python tools/play_bot.py Apex 127.0.0.1 5555             # any arena bot on the real server GUI
```

Two models are kept: the flagship **Splitter** (what `main.py` plays) and the backup
**Splitter-Calibrated** (the same bot with its evaluation fitted on game outcomes). How they were
chosen: [docs/strategy/14_campaign2.md](docs/strategy/14_campaign2.md); every idea that failed, so
it is not retried: [docs/strategy/15_failed_strategies.md](docs/strategy/15_failed_strategies.md).

---

## 🚀 Quick Start

### 1. Requirements
* **Python 3.8+**
* **Zero external dependencies** — uses only standard Python libraries (`socket`, `sys`, `time`, `random`, `math`). No `pip install` required!

### 2. Connect to the Game Server

#### Method A: Interactive Connection Wizard (Easiest)
Simply run:
```bash
python connect.py
```
It will guide you through entering the Server IP, Port, and your Team Name.  
*(Windows users can also just double-click `connect.bat`)*

#### Method B: One-Liner
```bash
python connect.py <SERVER_IP> <PORT> --name MyTeamName
```
*Example:*
```bash
python connect.py 192.168.1.50 5555 --name CentraleLions
```

#### Method C: Direct Client
```bash
python main.py <SERVER_IP> <PORT> --name MyTeamName --delay 0.0
```

---

## 🛠️ How to Build Your AI Agent

Everything you need to write is inside [`ai_agent.py`](ai_agent.py).

### Implement `compute_moves(state)`

```python
class AIAgent:
    def __init__(self, name: str = "MyBot"):
        self.name = name

    def compute_moves(self, state: GameState) -> List[Tuple[int, int, int, int, int]]:
        # 1. Inspect the state
        our_groups = state.get_our_groups()      # [((x, y), count), ...]
        enemy_groups = state.get_enemy_groups()  # [((x, y), count), ...]
        human_groups = state.get_human_groups()  # [((x, y), count), ...]

        # 2. Compute your decision (Heuristics, Minimax, Alpha-Beta, MCTS...)

        # 3. Return your moves
        return [(src_x, src_y, count, dst_x, dst_y)]
```

### Game Rules Reminder
1. **Time limit**: Your bot must send its moves within **2.0 seconds** per turn.
2. **Move format**: Each move is `(src_x, src_y, count, dst_x, dst_y)`.
3. **8-neighborhood**: Movement is limited to adjacent squares (Chebyshev distance $= 1$).
4. **Rule 5**: A cell cannot be both a source and a destination during the same turn.
5. **Deterministic vs Probabilistic Battles**:
   * If attacking force $E_1 \ge 1.5 \times E_2$ (defenders), victory is guaranteed at 0 losses!
   * Otherwise, the outcome is probabilistic. Converting humans safely to reach the $1.5\times$ threshold is key!

---

## 🎮 Local Testing (Self-Play)

You can run matches on your own machine before the official competition:

1. Launch the server:
   * Double-click `VampiresVSWerewolvesGameServer.exe`
2. Connect Bot 1 in a terminal:
   ```bash
   python main.py 127.0.0.1 5555 --name BotA --delay 0.5
   ```
3. Connect Bot 2 in a second terminal:
   ```bash
   python main.py 127.0.0.1 5555 --name BotB --delay 0.5
   ```
4. Watch the match unfold in real-time on the server GUI!

---

## 📁 Repository Structure

```text
├── main.py                   # Main network loop & game dispatch
├── ai_agent.py               # YOUR AI AGENT GOES HERE (Starter template included)
├── game_state.py             # Board state representation & helper methods
├── game_engine.py            # Battle mechanics, distance metrics & move validation
├── network.py                # Binary TCP client communicating with the server
│
├── connect.py                # Interactive / CLI fast connection launcher
├── connect.bat               # Windows double-click shortcut
├── connect.sh                # Linux/macOS shortcut
│
├── Projectv10.pdf            # Official project specification & tournament rules
├── requirements.txt          # Python requirements info
├── testmap.xml               # Sample map file
├── thetrap.xml               # Sample map file
└── VampiresVSWerewolves*     # Official WPF local server executable & DLLs
```

---

## 🤝 Git Workflow

```bash
# Get the latest changes from the team
git pull

# Commit and push your improvements
git add ai_agent.py
git commit -m "Improve heuristic evaluation for human conversion"
git push
```
