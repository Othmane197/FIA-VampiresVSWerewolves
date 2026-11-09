"""
rival_bots.py  (our own file; it does not modify any teammate's code)

Loads teammates' bots as benchmark opponents WITHOUT editing them.

Layout: put each teammate's branch in rivals/<Name>/ (e.g. `git archive origin/Othmane | tar -x -C rivals/Othmane`).
Each rival keeps its OWN game_engine.py (Othmane's differs from ours), but shares our game_state.py
(identical on every branch; sharing it matters because Species must be the same enum class).

    from rival_bots import make_rival
    agent = make_rival("Othmane")      # object with compute_moves(GameState)
"""
import importlib
import os
import sys

RIVALS_DIR = os.environ.get("VVW_RIVALS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "rivals"))

# modules that differ per branch: removed from sys.modules while a rival is imported, so the rival
# gets its own copy; game_state is NOT in the list (shared on purpose)
_PRIVATE = ("game_engine", "ai_agent", "apex_agent", "mcts_agent", "splitter")
_classes = {}


def _is_private(mod_name: str) -> bool:
    return mod_name.split(".")[0] in _PRIVATE


def _load(name: str):
    if name in _classes:
        return _classes[name]
    folder = os.path.join(RIVALS_DIR, name)
    if not os.path.isdir(folder):
        raise FileNotFoundError(f"{folder} not found (see the module docstring)")
    import game_state  # noqa: F401  make sure OUR game_state is the one the rival will share
    saved = {k: sys.modules.pop(k) for k in list(sys.modules) if _is_private(k)}
    sys.path.insert(0, folder)
    try:
        module = importlib.import_module("ai_agent")
        if os.path.isdir(os.path.join(folder, "splitter")):     # Mohamed's bot imports it lazily
            importlib.import_module("splitter.agent")
        cls = module.AIAgent
    finally:
        sys.path.remove(folder)
        private = {k: sys.modules.pop(k) for k in list(sys.modules) if _is_private(k)}
        sys.modules.update(saved)
    _classes[name] = (cls, private)
    return _classes[name]


def _instantiate(name: str):
    """Create the rival with ITS modules in place (some import lazily inside __init__)."""
    cls, private = _load(name)
    saved = {k: sys.modules.pop(k) for k in list(sys.modules) if _is_private(k)}
    sys.modules.update(private)
    try:
        return cls()
    finally:
        for k in [k for k in sys.modules if _is_private(k)]:
            private[k] = sys.modules.pop(k)
        sys.modules.update(saved)


class _Quiet:
    """Silences a rival's prints (some print every turn)."""

    def __init__(self, inner):
        self.inner = inner
        self.name = getattr(inner, "name", "rival")

    def compute_moves(self, state):
        stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
        try:
            return self.inner.compute_moves(state)
        finally:
            sys.stdout.close()
            sys.stdout = stdout


def make_rival(name: str):
    stdout = sys.stdout
    sys.stdout = open(os.devnull, "w")
    try:
        agent = _instantiate(name)
    finally:
        sys.stdout.close()
        sys.stdout = stdout
    return _Quiet(agent)
