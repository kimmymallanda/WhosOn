"""How often the right rulebook section is retrieved. Run: python evals/score_rules_search.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import rules_search as rs  # noqa: E402


def score(k: int) -> tuple[int, list[tuple[str, list[str], list[str]]]]:
    sections = rs.load_sections()
    cases = json.loads((ROOT / "data" / "rules_questions.json").read_text(encoding="utf-8"))
    misses = []
    for case in cases:
        found = [h["id"] for h in rs.search(case["q"], sections, k)]
        if not set(found) & set(case["expect"]):
            misses.append((case["q"], case["expect"], found))
    return len(cases), misses


if __name__ == "__main__":
    for k in (1, 4):
        total, misses = score(k)
        print(f"top {k}: {total - len(misses)}/{total}")
    for q, want, got in misses:
        print(f"  MISS {q}  expected {want}  got {got}")
