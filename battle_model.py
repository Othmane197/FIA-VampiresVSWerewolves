"""
battle_model.py  (our own file; it does not modify any shared repo file)

Describes what can happen in ONE battle, so that a search algorithm can reason about
chance (the "chance nodes" of expectiminimax).

Rules used (Projectv10.pdf, section "Random battle"), attackers E1 against defenders E2:
  * humans:   E1 >= E2        -> certain conversion of everybody: E1 + E2 friendly creatures
  * monsters: E1 >= 1.5 * E2  -> certain win, no losses
  * otherwise the attackers win with probability P (there is NO certain loss: the official server,
    read from VVSW.Model.dll, gives 3 attackers against 5 monsters a 30% chance, see server_rules.py):
        E1 == E2 : P = 0.5 | E1 < E2 : P = E1 / (2 * E2) | E1 > E2 : P = E1 / E2 - 0.5
      - attackers win : each attacker survives with probability P; against humans each human
                        also survives AND is converted with probability P
      - attackers lose: every attacker dies, each defender survives with probability 1 - P
        (verified in the server DLL)

Because every creature survives independently, survivor counts are binomial:
  win vs humans   : friendly ~ Bin(E1 + E2, P)   (attackers and converted humans, same P)
  win vs monsters : friendly ~ Bin(E1, P)
  lose vs humans  : humans left ~ Bin(E2, 1 - P)
  lose vs monsters: enemies left ~ Bin(E2, 1 - P)

Three levels of detail (argument `level`):
  "mean": ONE outcome holding the average numbers (floats).
  "two" : ONE outcome per branch (win / lose), each holding its rounded average survivors.
  "full": every possible survivor count with its exact probability.
"""
from collections import defaultdict
from math import comb
from typing import Dict, List, NamedTuple, Tuple


class Outcome(NamedTuple):
    prob: float       # probability of this outcome
    friendly: float   # attacking-side creatures left on the cell (converted humans included)
    enemy: float      # defending monsters left on the cell
    humans: float     # humans left on the cell


def win_probability(e1: int, e2: int) -> float:
    """P that the attackers (E1) win against defenders (E2), from the spec."""
    if e1 <= 0:
        return 0.0
    if e2 <= 0:
        return 1.0
    if e1 == e2:
        return 0.5
    if e1 < e2:
        return e1 / (2.0 * e2)
    return e1 / e2 - 0.5


def _binomial_pmf(n: int, p: float) -> List[float]:
    """P(K = k) for k = 0..n when K ~ Bin(n, p)."""
    q = 1.0 - p
    return [comb(n, k) * (p ** k) * (q ** (n - k)) for k in range(n + 1)]


def _round_half_up(x: float) -> int:
    return int(x + 0.5)


def certain_outcome(attackers: int, defenders: int, target_is_humans: bool):
    """The single Outcome if the battle is not random, else None."""
    if defenders <= 0:                                   # empty cell: just move in
        return Outcome(1.0, attackers, 0, 0)
    if target_is_humans:
        if attackers >= defenders:
            return Outcome(1.0, attackers + defenders, 0, 0)
        return None
    if attackers >= 1.5 * defenders:
        return Outcome(1.0, attackers, 0, 0)
    return None                                          # no certain loss on the real server


def battle_outcomes(attackers: int, defenders: int, target_is_humans: bool,
                    level: str = "two", min_prob: float = 0.0) -> List[Outcome]:
    """
    All outcomes of attackers attacking defenders (humans if target_is_humans, else monsters).
    The probabilities of the returned outcomes sum to 1.
    `min_prob` (only for level "full") drops very unlikely outcomes and renormalizes.
    """
    if level not in ("mean", "two", "full"):
        raise ValueError(f"unknown level {level!r}")
    sure = certain_outcome(attackers, defenders, target_is_humans)
    if sure is not None:
        return [sure]

    p = win_probability(attackers, defenders)
    win_n = attackers + defenders if target_is_humans else attackers   # creatures that may survive on a win
    lose_n = defenders                                                 # defenders that may survive on a loss

    def lose_outcome(prob, left):
        return Outcome(prob, 0, 0 if target_is_humans else left, left if target_is_humans else 0)

    if level == "mean":
        friendly = p * (p * win_n)
        left = (1 - p) * ((1 - p) * lose_n)
        return [Outcome(1.0, friendly, 0 if target_is_humans else left, left if target_is_humans else 0)]

    if level == "two":
        merged: Dict[Tuple[int, int, int], float] = defaultdict(float)
        merged[(_round_half_up(p * win_n), 0, 0)] += p
        o = lose_outcome(1 - p, _round_half_up((1 - p) * lose_n))
        merged[(0, o.enemy, o.humans)] += 1 - p
        return [Outcome(pr, *key) for key, pr in merged.items()]

    # level == "full"
    merged = defaultdict(float)
    for k, pr in enumerate(_binomial_pmf(win_n, p)):
        merged[(k, 0, 0)] += p * pr
    for k, pr in enumerate(_binomial_pmf(lose_n, 1 - p)):
        o = lose_outcome(0, k)
        merged[(0, o.enemy, o.humans)] += (1 - p) * pr
    items = [(key, pr) for key, pr in merged.items() if pr >= min_prob]
    total = sum(pr for _, pr in items)
    return [Outcome(pr / total, *key) for key, pr in sorted(items)]


def expected_outcome(attackers: int, defenders: int, target_is_humans: bool) -> Outcome:
    """Average numbers over all possibilities (level "mean")."""
    return battle_outcomes(attackers, defenders, target_is_humans, level="mean")[0]
