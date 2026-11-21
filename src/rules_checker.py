"""Deterministic ALTA lineup checker (regular season). The model proposes lineups; this module decides if they are legal.

Every violation carries a rule ID so the agent can cite it. Limits come from data/league_config.json.
Rules are from ALTA General Rules Adult Leagues, Fall 2026. This is a pre-check: the ALTA Lineup Checker
in the member portal is the authority, so captains should still confirm there.

Rule IDs
  R1  Format: the right number of lines, two players on each        (League-Specific Rules)
  R2  Every player is on the team roster                            (I.I)
  R3  A player plays only one line per dual meet                    (I.B)
  R4  Every player is confirmed available                           (project rule)
  R5  A pair moves at most one line from the last line it played together    (III.E)
  R6  A player moves at most two lines from her own last legal line (III.E)
  R7  Sandbagging: a winning pair moves down while a losing pair moves up    (III.E, III.F)
  R8  A player added to the roster after schedules are posted must be eligible (I.G.5, I.G.6)

Not covered here: playoffs (movement rules do not apply), "stronger pair below weaker pair" beyond R7,
and match-day changes once a scorecard has been exchanged (IV.D).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

DATA = Path(__file__).resolve().parent.parent / "data"

# A lineup is a list of pairs. lineup[0] is line 1. Example: [["p01","p02"], ["p03","p12"], ...]
Lineup = List[List[str]]


@dataclass
class Violation:
    rule_id: str
    message: str


def load_json(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ season state

@dataclass
class State:
    """What the movement and sandbagging rules need to know about the season so far."""
    last_line: Dict[str, int] = field(default_factory=dict)  # player -> last legal line she played
    pair_last: Dict[frozenset, int] = field(default_factory=dict)  # pair -> last legal line played together
    pair_record: Dict[frozenset, List[int]] = field(default_factory=dict)  # pair -> [wins, losses]
    played: Dict[str, int] = field(default_factory=dict)  # player -> matches played


def build_state(history: dict) -> State:
    """Replay the regular season, oldest match first. Provisional lineups count as played
    but are not used to track positions (Handbook: Provisional Lineup)."""
    s = State()
    for m in history.get("matches", []):
        results = m.get("results") or [None] * len(m["lineup"])
        for line, pair in enumerate(m["lineup"], start=1):
            for pid in pair:
                s.played[pid] = s.played.get(pid, 0) + 1
            if m.get("provisional"):
                continue
            key = frozenset(pair)
            s.pair_last[key] = line
            rec = s.pair_record.setdefault(key, [0, 0])
            won = results[line - 1] if line - 1 < len(results) else None
            if won is True:
                rec[0] += 1
            elif won is False:
                rec[1] += 1
            for pid in pair:
                s.last_line[pid] = line
    return s


def pair_status(state: State, pair) -> str:
    """'winning' (more wins than losses), 'losing', or 'none' (even, or never played together)."""
    w, l = state.pair_record.get(frozenset(pair), [0, 0])
    return "winning" if w > l else "losing" if l > w else "none"


# ---------------------------------------------------------------- allowed lines

def allowed_lines_for_player(pid: str, state: State, config: dict) -> List[int]:
    """Lines a player may play on her own. A player with no history may play any line."""
    n = config["lines"]
    if pid not in state.last_line:
        return list(range(1, n + 1))
    last, lim = state.last_line[pid], config["individual_move_limit"]
    return [x for x in range(1, n + 1) if abs(x - last) <= lim]


def allowed_lines_for_pair(pair, state: State, config: dict) -> List[int]:
    """Lines a pair may play (R5 and R6 together). Useful as a constraint for the lineup planner."""
    n = config["lines"]
    ok = set(range(1, n + 1))
    for pid in pair:
        ok &= set(allowed_lines_for_player(pid, state, config))
    key = frozenset(pair)
    if key in state.pair_last:
        last, lim = state.pair_last[key], config["pair_move_limit"]
        ok &= {x for x in range(1, n + 1) if abs(x - last) <= lim}
    return sorted(ok)


# ------------------------------------------------------------------ the checker

def check_lineup(lineup: Lineup, roster: dict, config: dict, available: Set[str],
                 state: Optional[State] = None) -> List[Violation]:
    """Return every rule the lineup breaks. An empty list means the lineup is legal.

    roster: data/roster.json contents. config: data/league_config.json contents.
    available: player IDs confirmed available for this match.
    state: build_state(history). Leave out only when there is no regular-season history yet.
    """
    v: List[Violation] = []
    state = state or State()
    players = {p["id"]: p for p in roster["players"]}
    name = lambda pid: players.get(pid, {}).get("name", pid)  # noqa: E731

    # R1: right number of lines, right number of players on each
    if len(lineup) != config["lines"]:
        v.append(Violation("R1", f"Expected {config['lines']} lines, got {len(lineup)}."))
    for line, pair in enumerate(lineup, start=1):
        if len(pair) != config["players_per_line"]:
            v.append(Violation("R1", f"Line {line} needs {config['players_per_line']} players, got {len(pair)}."))

    everyone = [pid for pair in lineup for pid in pair]

    # R2: everyone is on the roster
    for pid in everyone:
        if pid not in players:
            v.append(Violation("R2", f"{pid} is not on the roster."))

    # R3: one line per player
    seen: Set[str] = set()
    for pid in everyone:
        if pid in seen:
            v.append(Violation("R3", f"{name(pid)} is in more than one line."))
        seen.add(pid)

    # R4: everyone is confirmed available
    for pid in dict.fromkeys(everyone):
        if pid in players and pid not in available:
            v.append(Violation("R4", f"{name(pid)} is not confirmed available."))

    # R5: pair movement, from the last line the pair played together
    moves = []  # (pair, last_line, new_line) for pairs with history, used by R7
    for line, pair in enumerate(lineup, start=1):
        key = frozenset(pair)
        if len(pair) == 2 and key in state.pair_last:
            last = state.pair_last[key]
            moves.append((pair, last, line))
            if abs(line - last) > config["pair_move_limit"]:
                v.append(Violation(
                    "R5",
                    f"{name(pair[0])} and {name(pair[1])} last played together at line {last}; "
                    f"a pair may move only {config['pair_move_limit']} line, so line {line} is not allowed.",
                ))

    # R6: individual movement, from the player's own last legal line
    for line, pair in enumerate(lineup, start=1):
        for pid in pair:
            if pid in state.last_line and abs(line - state.last_line[pid]) > config["individual_move_limit"]:
                v.append(Violation(
                    "R6",
                    f"{name(pid)} last played line {state.last_line[pid]}; a player may move only "
                    f"{config['individual_move_limit']} lines, so line {line} is not allowed.",
                ))

    # R7: sandbagging. A winning pair moved down while a losing pair moved up.
    down = [(p, a, b) for p, a, b in moves if b > a and pair_status(state, p) == "winning"]
    up = [(p, a, b) for p, a, b in moves if b < a and pair_status(state, p) == "losing"]
    if down and up:
        w, l = down[0], up[0]
        v.append(Violation(
            "R7",
            f"Sandbagging: winning pair {name(w[0][0])} and {name(w[0][1])} moves down (line {w[1]} to {w[2]}) "
            f"while losing pair {name(l[0][0])} and {name(l[0][1])} moves up (line {l[1]} to {l[2]}).",
        ))
    return v


# ------------------------------------------------------- roster add-ons (subs)

def _level_table() -> dict:
    return load_json("alta_leagues.json")["levels"]


def parse_level_flight(text) -> Optional[Tuple[str, Optional[int]]]:
    """'A-3' -> ('A', 3); 'AA' -> ('AA', None). None if it is not a valid ALTA level or flight.

    Levels are AA, A, B, C (AA strongest). Flights run 1-3 in AA and 1-8 in A, B and C.
    """
    m = re.fullmatch(r"\s*(AA|A|B|C)\s*-?\s*(\d)?\s*", str(text or "").upper())
    if not m:
        return None
    level, flight = m.group(1), int(m.group(2)) if m.group(2) else None
    if flight is not None and not 1 <= flight <= _level_table()["flights"][level]:
        return None
    return level, flight


def strength_index(level_flight) -> Optional[int]:
    """Where a level flight sits, strongest first: AA-1 is 0, AA-3 is 2, A-1 is 3, A-8 is 10, B-1 is 11, C-8 is 26.

    A smaller number is a stronger team. None if the flight is missing or invalid.
    """
    parsed = parse_level_flight(level_flight)
    if not parsed or parsed[1] is None:
        return None
    table = _level_table()
    order = table["strongest_first"]
    return sum(table["flights"][lv] for lv in order[: order.index(parsed[0])]) + parsed[1] - 1


def check_roster_add(candidate: dict, config: dict, addons_used: int, already_on_roster: bool,
                     minutes_before_start: Optional[int] = None) -> List[Violation]:
    """R8: can this player be added so she may play? Only needed for someone not already on the roster.

    candidate: {"name", "level_flight" (her most recent final level, such as "A-3"), "paid_member": bool}.
    Her level flight must be at or below the team's: the same flight or a weaker one (a higher number, or a
    lower level). If she is only known by level ("A"), a weaker level passes and the same level needs her flight.
    minutes_before_start: minutes until the scheduled start of the dual meet (negative means it has started).
    """
    if already_on_roster:
        return []
    v: List[Violation] = []
    nm = candidate.get("name", "Candidate")
    if not candidate.get("paid_member", False):
        v.append(Violation("R8", f"{nm} must be a paid ALTA member to be added."))
    cand_raw, team_raw = candidate.get("level_flight"), config["level_flight"]
    cand, team = parse_level_flight(cand_raw), parse_level_flight(team_raw)
    if cand is None:
        v.append(Violation("R8", f"{nm}'s level ({cand_raw}) is not a valid ALTA level flight, such as A-3."))
    else:
        ci, ti = strength_index(cand_raw), strength_index(team_raw)
        too_strong = f"{nm}'s level ({cand_raw}) must be at or below the team's level ({team_raw})."
        if ci is not None and ti is not None:
            if ci < ti:
                v.append(Violation("R8", too_strong))
        else:  # she is known only by level, so compare levels
            order = _level_table()["strongest_first"]
            if order.index(cand[0]) < order.index(team[0]):
                v.append(Violation("R8", too_strong))
            elif cand[0] == team[0]:
                v.append(Violation("R8", f"{nm} is {cand_raw}, the same level as the team ({team_raw}); her flight is needed to compare."))
    if addons_used >= config["max_roster_addons"]:
        v.append(Violation("R8", f"The team already used its {config['max_roster_addons']} roster add-ons."))
    if minutes_before_start is not None and minutes_before_start < 0:
        v.append(Violation("R8", f"{nm} can be added only until the scheduled start of the dual meet."))
    return v
