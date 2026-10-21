"""
Registry of every bot the arena can play, behind one interface:

    bot = make_bot("Apex", time_limit=0.3)
    bot.reset()
    moves = bot.play(state, side)          # state: splitter.state.State (a copy, may be mutated)

The team uses two agent interfaces; adapters translate:
    GameStateBot   compute_moves(GameState)            repo starter, Dana's bots, our AIAgent
    BoardBot       compute_moves(BoardState, Species)  Othmane's and Ronita's bots
    SplitterBot    SplitterAgent.choose(State, side)   our bot (fast path, true ply)

Bots INSIDE the repo:
    "Splitter"            the flagship (splitter.agent.MODELS["flagship"])
    "Splitter-Calibrated" the backup (MODELS["backup"]: evaluation fitted on game outcomes)
    "Splitter:k=v,..."    any variant inline, e.g. "Splitter:splits=0" (the deathball ablation),
                          "Splitter:gamble=always,c=0.9" (an aggressive style), "Splitter:c=0.8"
    "Snap:<version>[:k=v,..]"  a frozen copy of splitter/ (arena/snapshot.py)
    "Styled:<n>"          a reproducible random opponent STYLE (styled_config): a third validation
                          set against over-fitting to the teammates' bots (chapter 14)
    teammates' bots       Apex, RaceMCTS, Expecti, Grabber, ... loaded from arena/vendor/<branch>/
                          (run `python -m arena.fetch_opponents`)
Bots OUTSIDE the repo:
    "py:<path/to/bot.py>[:ClassName]"   any Python class with compute_moves(GameState) or
                          compute_moves(BoardState, Species) (detected automatically)
    any program, any language: tools/server_match.py plays it over the real network protocol
"""
import importlib
import importlib.util
import inspect
import os
import sys
from typing import Any, Callable, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game_state import Species
from splitter.rules import V

VENDOR = os.path.join(ROOT, "arena", "vendor")
_SHADOWED = ("ai_agent",)                       # module names that exist both here and in a vendor dir
_loaded: Dict[str, Dict[str, object]] = {}


def _species(side: int):
    """V / W -> game_state.Species."""
    return Species.VAMPIRE if side == V else Species.WEREWOLF


def load_vendor(branch: str, modules) -> List[Any]:
    """Import `modules` from arena/vendor/<branch> without clashing with the repo's modules."""
    cache = _loaded.setdefault(branch, {})
    missing = [m for m in modules if m not in cache]
    if not missing:
        return [cache[m] for m in modules]
    path = os.path.join(VENDOR, branch)
    if not os.path.isdir(path):
        raise RuntimeError(f"{path} missing: run `python -m arena.fetch_opponents` first")
    saved = {m: sys.modules.pop(m) for m in _SHADOWED if m in sys.modules}
    sys.path.insert(0, path)
    try:
        for m in missing:
            cache[m] = importlib.import_module(m)
    finally:
        sys.path.remove(path)
        for m in _SHADOWED:                      # keep the vendor copy under a private name
            mod = sys.modules.pop(m, None)
            if mod is not None and getattr(mod, "__file__", "").startswith(path):
                sys.modules[f"_vendor_{branch}_{m}"] = mod
        sys.modules.update(saved)
    return [cache[m] for m in modules]


class Bot:
    """Common interface of every arena bot: reset() and play(state, side) -> moves."""
    name = "bot"

    def reset(self):
        """Prepare for a new game."""

    def play(self, state, side):
        """Moves for `side` in `state` (implemented by the adapters)."""
        raise NotImplementedError


class GameStateBot(Bot):
    """Adapter for agents with compute_moves(GameState) (repo starter, Dana's bots, AIAgent)."""
    def __init__(self, name: str, factory: Callable[[], Any]):
        """Wrap an agent factory; a fresh agent is built for every game."""
        self.name = name
        self.factory = factory
        self.agent = factory()
        self.home = None

    def reset(self):
        """Fresh agent instance for a new game."""
        self.agent = self.factory()
        self.home = None

    def play(self, state, side):
        """Convert the State to a GameState and ask the agent."""
        if self.home is None:
            self.home = next(iter(state.groups[side]))
        gs = state.to_game_state(side, self.home)
        return self.agent.compute_moves(gs)


class BoardBot(Bot):
    """Adapter for agents with compute_moves(BoardState, Species) (Othmane's and Ronita's bots)."""
    def __init__(self, name: str, factory: Callable[[], Any]):
        """Wrap an agent factory; a fresh agent is built for every game."""
        self.name = name
        self.factory = factory
        self.agent = factory()

    def reset(self):
        """Fresh agent instance for a new game."""
        self.agent = self.factory()

    def play(self, state, side):
        """Convert the State to a BoardState and ask the agent."""
        return self.agent.compute_moves(state.to_board(), _species(side))


class SplitterBot(Bot):
    """Our bot through its fast choose(State, side) interface."""
    def __init__(self, name: str, kwargs: dict):
        """SplitterAgent with the given keyword arguments (game clock disabled in the arena)."""
        from splitter import SplitterAgent
        self.name = name
        self.kwargs = kwargs
        self.agent = SplitterAgent(name=name, **{"game_seconds": None, **kwargs})

    def reset(self):
        """Forget the previous game."""
        self.agent.reset()

    def play(self, state, side):
        """Moves chosen by the SplitterAgent."""
        return self.agent.choose(state, side)


def _parse_value(v: str):
    """'3' -> 3, '0.5' -> 0.5, 'true' -> True, else the string (for 'Splitter:key=value')."""
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    return {"true": True, "false": False}.get(v.lower(), v)


# name -> builder(time_limit) ; time_limit is the per-move budget given to search bots
def _registry() -> Dict[str, Callable[[float], Bot]]:
    """name -> builder(time_limit) for every non-Splitter bot (teammates' bots are loaded lazily)."""
    def othmane(cls_name, **kw):
        def make(_t):
            (rv,) = load_vendor("Othmane", ["rival_agents"])
            cls = getattr(rv, cls_name)
            return BoardBot(cls_name, lambda: cls(**kw))
        return make

    def apex(t):
        (ax,) = load_vendor("Othmane", ["apex_agent"])
        return BoardBot("Apex", lambda: ax.ApexAlphaBetaAgent("Apex", max_time_seconds=t))

    def race_mcts(t):
        (mc,) = load_vendor("Ronita", ["mcts_agent"])
        return BoardBot("RaceMCTS", lambda: mc.MCTSAgent("RaceMCTS", max_time_seconds=t))

    def dana(cls_name):
        def make(_t):
            (sp,) = load_vendor("Dana", ["sparring_agents"])
            cls = getattr(sp, cls_name)
            return GameStateBot(cls_name, lambda: cls())
        return make

    def expecti(t):
        (sa,) = load_vendor("Dana", ["search_agent"])
        return GameStateBot("Expecti", lambda: sa.SearchAgent("Expecti", time_limit=t))

    def starter(_t):
        from ai_agent import StarterAgent
        return GameStateBot("Starter", lambda: StarterAgent("Starter"))

    def aiagent(t):
        from ai_agent import AIAgent
        return GameStateBot("AIAgent", lambda: AIAgent("AIAgent", time_limit=t, game_seconds=None))

    return {
        "Starter": starter,
        "AIAgent": aiagent,                 # our full tournament path (GameState interface)
        "Apex": apex,
        "RaceMCTS": race_mcts,
        "Expecti": expecti,
        "Grabber": dana("Grabber"),
        "Rusher": dana("Rusher"),
        "Turtle": dana("Turtle"),
        "Random": othmane("RandomAgent"),
        "Greedy": othmane("GreedyReflexAgent"),
        "PotentialField": othmane("PotentialFieldAgent"),
        "ShallowMinimax": othmane("ShallowMinimaxAgent"),
        "MonteCarlo": othmane("MonteCarloAgent"),
        "TacticalSplitter": othmane("TacticalSplitterAgent"),
    }


# Default sparring panel: every teammate's main bot + the most instructive simple ones
PANEL = ["Apex", "RaceMCTS", "Expecti", "TacticalSplitter", "Grabber", "Rusher", "Greedy", "Starter"]

def _models():
    """The two kept models, named for the arena (defined once, in splitter/agent.py)."""
    from splitter.agent import MODELS
    return {"Splitter": dict(MODELS["flagship"]), "Splitter-Calibrated": dict(MODELS["backup"])}


VARIANTS = _models()


def styled_config(n: int) -> dict:
    """
    Opponent style number n (deterministic): random risk taking, splitting, caution, search depth.
    These bots share our planner, so they are not independent of our bot, but each plays a style
    that none of the teammates' bots represents (from reckless gambler to timid deathball).
    """
    import random
    r = random.Random(1000 + n)
    cfg = {
        "splits": r.random() < 0.7,
        "gamble": r.choice(["never", "adaptive", "always"]),
        "c": round(r.uniform(0.3, 1.2), 2),
        "rollout_depth": r.choice([0, 1, 2, 3]),
        "reserve_radius": r.randint(2, 10),
        "safety_margin": r.randint(0, 2),
        "max_detachments": r.randint(1, 4),
        "danger_weight": round(r.uniform(0.5, 6.0), 2),
        "danger_strike_p": round(r.uniform(0.25, 0.7), 2),
        "commit_bonus": round(r.uniform(0.0, 0.8), 2),
        "hunt_bonus": round(r.uniform(0.0, 1.0), 2),
    }
    if r.random() < 0.25:
        cfg["search"] = "greedy"
    return cfg


STYLED_PANEL = [f"Styled:{n}" for n in range(1, 7)]


def bot_names():
    """Every bot name make_bot() accepts."""
    return sorted(set(_registry()) | set(VARIANTS))


class SnapshotBot(SplitterBot):
    """A frozen copy of splitter/ (arena/snapshots/splitter_<version>), see arena/snapshot.py."""

    def __init__(self, name: str, version: str, kwargs: dict):
        """SplitterAgent imported from arena/snapshots/splitter_<version>/."""
        mod = importlib.import_module(f"arena.snapshots.splitter_{version}.agent")
        self.name = name
        self.kwargs = kwargs
        self.agent = mod.SplitterAgent(name=name, **{"game_seconds": None, **kwargs})


def load_external(spec: str) -> Bot:
    """
    'py:<path>[:ClassName]' -> a Bot around an external Python agent class. Without ClassName the
    first class defining compute_moves is used. The interface is detected from compute_moves'
    signature: one argument = GameState (repo / Dana style), two = (BoardState, Species).
    """
    body = spec[3:]
    path, cls_name = body, None
    if body.count(":") >= 1 and not os.path.exists(body):      # 'file.py:Class' (keep 'C:\...' paths)
        path, _, cls_name = body.rpartition(":")
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"external bot file not found: {path}")
    folder = os.path.dirname(path)
    mod_name = "_external_" + "".join(c if c.isalnum() else "_" for c in path)
    sys.path.insert(0, folder)                    # its own sibling imports
    try:
        spec_obj = importlib.util.spec_from_file_location(mod_name, path)
        if spec_obj is None or spec_obj.loader is None:
            raise ImportError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec_obj)
        spec_obj.loader.exec_module(module)
    finally:
        sys.path.remove(folder)
    if cls_name is None:
        found = [c for _, c in inspect.getmembers(module, inspect.isclass)
                 if c.__module__ == module.__name__ and hasattr(c, "compute_moves")]
        if not found:
            raise ValueError(f"no class with compute_moves in {path}")
        cls: Any = found[0]
    else:
        cls = getattr(module, cls_name)
    n_args = len(inspect.signature(cls.compute_moves).parameters) - 1       # minus self

    def factory():
        try:
            return cls()
        except TypeError:
            return cls(cls.__name__)               # constructors that require a name
    label = f"{os.path.basename(path)}:{cls.__name__}"
    return BoardBot(label, factory) if n_args >= 2 else GameStateBot(label, factory)


def make_bot(spec: str, time_limit: float = 0.3) -> Bot:
    """spec: registry name, Splitter variant, 'Splitter:k=v,..', 'Snap:<version>[:k=v,..]' or 'py:<file>[:Class]'."""
    if spec.startswith("py:"):
        return load_external(spec)
    if spec.startswith("Snap:"):
        _, version, *rest = spec.split(":")
        kwargs = {}
        for kv in (rest[0].split(",") if rest else []):
            k, _, v = kv.partition("=")
            kwargs[k.strip()] = _parse_value(v.strip())
        kwargs.setdefault("time_limit", time_limit)
        return SnapshotBot(spec, version, kwargs)
    if spec.startswith("Styled:"):
        kwargs = styled_config(int(spec.split(":")[1]))
        kwargs["time_limit"] = time_limit
        return SplitterBot(spec, kwargs)
    name, _, args = spec.partition(":")
    if name in VARIANTS or name.startswith("Splitter"):
        kwargs = dict(VARIANTS.get(name, {}))
        if args:
            for kv in args.split(","):
                k, _, v = kv.partition("=")
                kwargs[k.strip()] = _parse_value(v.strip())
        kwargs.setdefault("time_limit", time_limit)
        return SplitterBot(spec, kwargs)
    reg = _registry()
    if name not in reg:
        raise KeyError(f"unknown bot {spec!r}; known: {bot_names()}")
    return reg[name](time_limit)
