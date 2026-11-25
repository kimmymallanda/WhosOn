"""Splits the ALTA General Rules text into citable sections for retrieval.

Input:  data/rulebook/general_rules_fall2026.txt, made from ALTA's PDF with
        osascript -l JavaScript src/pdf_text.jxa.js /full/path/2026FallAdultLeagueRules.pdf
Output: data/rulebook/sections.json  (both are gitignored: the repo is public)

Run:  python src/build_rulebook.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "rulebook" / "general_rules_fall2026.txt"
OUTPUT = ROOT / "data" / "rulebook" / "sections.json"

TOP = re.compile(r"^(VII|VI|V|IV|III|II|I)\. ([A-Z][A-Za-z ,]+)$")
LETTER = re.compile(r"^([A-K])\. (.*)$")
TERM = re.compile(r"^([A-Z][A-Z’' ]{2,}|Level|Flight|Division) ?- ?(.*)$")

# Which of the rules checker's IDs each section backs (see src/rules_checker.py).
CHECKER_RULES = {
    "League format": ["R1"], "I.I": ["R2"], "V.A": ["R2"], "I.B": ["R3"],
    "III.E": ["R5", "R6", "R7"], "III.F": ["R7"], "I.G": ["R8"],
}


def clean_lines(text: str) -> list[tuple[int, str]]:
    """(page, line) pairs without page markers or printed page numbers."""
    page, out = 0, []
    for raw in text.splitlines():
        line = raw.strip()
        marker = re.match(r"^=== PAGE (\d+) ===$", line)
        if marker:
            page = int(marker.group(1))
        elif line and not re.fullmatch(r"\d{1,2}", line):
            out.append((page, line))
    return out


def join(lines: list[str]) -> str:
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def numbered_sections(lines: list[tuple[int, str]]) -> list[dict]:
    out: list[dict] = []
    top = title = None
    current: dict | None = None
    expected = "A"
    for page, line in lines:
        if line == "LEAGUE-SPECIFIC RULES":
            break
        heading = TOP.match(line)
        # "I. Any person..." is letter I of section I, so headings must be all caps or "PLAYOFFS".
        if heading and sum(c.isupper() for c in heading.group(2)) > len(heading.group(2)) / 2:
            top, title, expected, current = heading.group(1), heading.group(2).title(), "A", None
            continue
        if top is None:
            continue
        letter = LETTER.match(line)
        if letter and letter.group(1) == expected:
            current = {"id": f"{top}.{expected}", "title": title, "page": page, "lines": [letter.group(2)]}
            out.append(current)
            expected = chr(ord(expected) + 1)
            continue
        if current is None:  # a section with no lettered parts (II. Level Placement)
            current = {"id": top, "title": title, "page": page, "lines": []}
            out.append(current)
        current["lines"].append(line)
    return out


def block(lines, start: str, stop: str, ident: str, title: str) -> dict:
    """The text from the first line starting with `start` up to the line starting with `stop`."""
    first = next(i for i, (_, s) in enumerate(lines) if s.startswith(start))
    last = next((i for i in range(first + 1, len(lines)) if lines[i][1].startswith(stop)), len(lines))
    return {"id": ident, "title": title, "page": lines[first][0], "lines": [s for _, s in lines[first:last]]}


def league_sections(lines) -> list[dict]:
    return [
        block(lines, "Adult leagues are divided", "During playoffs", "League format", "League-Specific Rules"),
        block(lines, "During playoffs and City Finals, if a dual meet ends", "END OF REGULAR", "Playoff ties", "League-Specific Rules"),
        block(lines, "END OF REGULAR SEASON (WEEK 7) INCLEMENT WEATHER MAKE-UP", "SENIOR AND SENIOR DAY LEAGUE RULES", "Final week makeups", "League-Specific Rules"),
        block(lines, "SENIOR MEN’S AND SENIOR WOMEN’S LEAGUES", "END OF REGULAR", "Senior league format", "Senior and Senior Day League Rules"),
        block(lines, "SENIOR MEN - Matches rescheduled", "GLOSSARY OF TERMS", "Senior final week makeups", "Senior and Senior Day League Rules"),
    ]


def clock(hhmm: str) -> str:
    hour, minute = (int(x) for x in hhmm.split(":"))
    return f"{(hour - 1) % 12 + 1}:{minute:02d} {'PM' if hour >= 12 else 'AM'}"


def start_times() -> dict:
    """ALTA's start-time table does not survive text extraction, so use the checked JSON copy."""
    data = json.loads((ROOT / "data" / "alta_leagues.json").read_text(encoding="utf-8"))
    rows = [f"{name}: {v['day']} matches start at {', then '.join(clock(t) for t in v['start_times'])}."
            for name, v in data["leagues"].items()]
    return {"id": "League start times", "title": "League-Specific Rules", "page": 8,
            "lines": ["Scheduled day and start times by league."] + rows}


def glossary(lines) -> list[dict]:
    first = next(i for i, (_, s) in enumerate(lines) if s == "GLOSSARY OF TERMS")
    out: list[dict] = []
    for page, line in lines[first + 1:]:
        term = TERM.match(line)
        if term:
            name = term.group(1).strip().title()
            out.append({"id": f"Glossary: {name}", "title": "Glossary of Terms", "page": page, "lines": [line]})
        elif out:
            out[-1]["lines"].append(line)
    return out


def build(text: str) -> list[dict]:
    lines = clean_lines(text)
    # Skip the table of contents, which repeats several headings.
    body = lines[next(i for i, (_, s) in enumerate(lines) if s == "I. TEAMS AND PLAYERS"):]
    sections = numbered_sections(body) + league_sections(body) + [start_times()] + glossary(body)
    return [{"id": s["id"], "title": s["title"], "page": s["page"], "text": join(s["lines"]),
             "checker_rules": CHECKER_RULES.get(s["id"], [])} for s in sections]


if __name__ == "__main__":
    result = build(SOURCE.read_text(encoding="utf-8"))
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(result)} sections -> {OUTPUT.relative_to(ROOT)}")
