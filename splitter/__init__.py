"""The Splitter: MCTS over joint plans with safe exact-size detachments. See docs/SPLITTER.md."""
from .agent import SplitterAgent
from .rules import V, W
from .state import State

__all__ = ["SplitterAgent", "State", "V", "W"]
