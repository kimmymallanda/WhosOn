"""Which lines start when, and whether a player's time limit fits a line.

The parser only extracts a player's condition ("until 16:00"). This module compares it with the line
start times, because that comparison is a hard rule and belongs in code, not in the model.

A line can take 1 to 3 hours (config line_duration_hours), and later lines start "as listed or when a
court is free", so a listed start time is the earliest start and a later line can start late.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

PER_SLOT = 2  # lines 1-2 share a start time, lines 3-4 share the next, line 5 the last


def to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def fmt(minutes: int) -> str:
    """Minutes after midnight -> '1:00 PM'."""
    h, m = (minutes // 60) % 24, minutes % 60
    return f"{(h % 12) or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def line_start(line: int, start_times: List[str]) -> str:
    """Scheduled start of a line (1-based), as 'HH:MM'."""
    slot = min((line - 1) // PER_SLOT, len(start_times) - 1)
    return start_times[slot]


def line_schedule(n_lines: int, start_times: List[str]) -> Dict[int, str]:
    return {line: line_start(line, start_times) for line in range(1, n_lines + 1)}


def parse_window(text: Optional[str]) -> Dict[str, Optional[int]]:
    """'after 14:00' -> earliest start, 'until 16:00' -> latest finish (minutes after midnight)."""
    out = {"earliest_start": None, "latest_end": None}
    if not text:
        return out
    m = re.search(r"\b(after|until)\s+(\d{1,2}):(\d{2})\b", text.lower())
    if m:
        minutes = int(m.group(2)) * 60 + int(m.group(3))
        out["earliest_start" if m.group(1) == "after" else "latest_end"] = minutes
    return out


def time_fit(window: Optional[str], line: int, start_times: List[str], config: dict) -> dict:
    """How well a player's time limit fits one line.

    status: 'ok'         fits even if the line runs the longest expected time
            'risky'      fits a short line only; she may have to leave a long one early
            'no'         starts before she can arrive, or does not fit even a short line
    """
    start = to_min(line_start(line, start_times))
    short = start + int(config["line_duration_hours"]["min"] * 60)
    long_ = start + int(config["line_duration_hours"]["max"] * 60)
    w = parse_window(window)
    result = {"line": line, "start": fmt(start), "ends_if_short": fmt(short), "ends_if_long": fmt(long_)}
    if w["earliest_start"] is not None and start < w["earliest_start"]:
        return {**result, "status": "no", "why": f"starts at {fmt(start)}, before {fmt(w['earliest_start'])}"}
    if w["latest_end"] is not None:
        if long_ <= w["latest_end"]:
            return {**result, "status": "ok", "why": f"done by {fmt(long_)} even if it runs {config['line_duration_hours']['max']} hours"}
        if short <= w["latest_end"]:
            return {**result, "status": "risky", "why": f"fits a {config['line_duration_hours']['min']}-hour line, not a long one"}
        return {**result, "status": "no", "why": f"cannot finish by {fmt(w['latest_end'])}"}
    return {**result, "status": "ok", "why": "no time limit"}
