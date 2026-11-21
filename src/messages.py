"""Per-player texts built from a lineup. Facts (line, partner, times) come from data, never from a model.

A model may soften the tone later, but it must not write the line number or the times.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List

from line_times import fmt, line_start, to_min


def _when(match: dict) -> str:
    d = date.fromisoformat(match["date"])
    return f"{d.strftime('%A')}, {d.strftime('%b')} {d.day}"


def availability_request(first_name: str, match: dict, start_times: List[str]) -> str:
    """The first text of the week. Lists the staggered start times so replies can name a time limit."""
    t = [fmt(to_min(x)) for x in start_times]
    slots = f"Lines 1-2 start at {t[0]}, lines 3-4 at {t[1]}" + (f", line 5 at {t[2]}" if len(t) > 2 else "")
    where = "away" if not match.get("home", True) else "home"
    return (
        f"Hi {first_name}! Can you play {_when(match)} vs {match['opponent']} ({where})? "
        f"{slots}, and a line can run 1 to 3 hours. Reply in your own words, and tell me if you have a time limit."
    )


def line_assignment(first_name: str, line: int, partner: str, match: dict, start_times: List[str], config: dict) -> str:
    start = to_min(line_start(line, start_times))
    warm = start - config["warmup_minutes"]
    stay = start + int(config["line_duration_hours"]["max"] * 60)
    return (
        f"{first_name}, you're on Line {line} with {partner} for {_when(match)} vs {match['opponent']}. "
        f"Start: {fmt(start)}. Arrive by {fmt(warm)} to warm up. A line can run up to "
        f"{config['line_duration_hours']['max']} hours, so plan to stay until about {fmt(stay)}. "
        f"Reply here if anything changes."
    )


def backup_note(first_name: str, match: dict) -> str:
    return f"{first_name}, you're a backup for {_when(match)}. I'll only text you if someone drops."


def sub_request(first_name: str, line: int, partner: str, match: dict, start_times: List[str], config: dict) -> str:
    start = to_min(line_start(line, start_times))
    return (
        f"Hi {first_name}, a spot just opened: {_when(match)} vs {match['opponent']}, Line {line} with {partner}, "
        f"{fmt(start)} start. A line can run up to {config['line_duration_hours']['max']} hours. Can you play?"
    )


def lineup_messages(lineup: List[List[str]], roster: dict, match: dict, start_times: List[str], config: dict) -> Dict[str, str]:
    """One text per player in the lineup, keyed by player id."""
    names = {p["id"]: p["name"] for p in roster["players"]}
    out: Dict[str, str] = {}
    for line, pair in enumerate(lineup, start=1):
        for pid in pair:
            partner = names[next(x for x in pair if x != pid)]
            out[pid] = line_assignment(names[pid].split()[0], line, partner, match, start_times, config)
    return out
