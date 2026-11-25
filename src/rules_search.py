"""Finds the rulebook sections that best match a captain's question (BM25 keyword search).

No model and no embeddings: the rulebook is about 70 short sections, and the same code runs in
an n8n Code node (n8n/src/search_core.js). Keep the two in step.

Run:  python src/rules_search.py "Can I move a pair up two lines?"
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ROOT / "data" / "rulebook" / "sections.json"

K1, B = 1.4, 0.6
MIN_SCORE = 2.0  # below this nothing really matched, so say so instead of guessing

STOPWORDS = set("""a about an and any are as at be been but by can could do does for from get had has have how i if in
into is it its may many me much must my no not of on or our out shall should so than that the their them then there
these they this to up us we what when where which who will with would you your""".split())

# Words captains use -> words the rulebook uses (both stemmed before matching).
SYNONYMS = {
    "rain": ["inclement", "weather"], "raining": ["inclement", "weather"], "lightning": ["inclement", "weather"],
    "degrees": ["temperature"], "hot": ["temperature"], "cold": ["temperature"],
    "late": ["default"], "short": ["default"], "sandbagging": ["sandbag"],
    "sub": ["roster", "lineup", "player"], "add": ["added"], "sidelines": ["spectators", "coaching"],
    "string": ["racquet"], "racket": ["racquet"], "penalty": ["forfeit"], "lines": ["position"], "line": ["position"],
}


def stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "ls":
        word = word[:-1]
    return word[:-1] if len(word) > 3 and word.endswith("e") else word


def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower().replace("’", "'").replace("'s", ""))
    return [stem(w) for w in words if w not in STOPWORDS]


def query_terms(question: str) -> dict[str, float]:
    """Each term with its weight: the captain's own words count fully, synonyms half."""
    terms = {t: 1.0 for t in tokens(question)}
    for word in re.findall(r"[a-z]+", question.lower()):
        for extra in SYNONYMS.get(word, []):
            terms.setdefault(stem(extra), 0.5)
    return terms


def load_sections() -> list[dict]:
    return json.loads(SECTIONS.read_text(encoding="utf-8"))


def search(question: str, sections: list[dict], k: int = 4) -> list[dict]:
    """The k best sections, best first, each with a score. Empty when nothing matches well."""
    docs = [Counter(tokens(f"{s['id']} {s['title']} {s['text']}")) for s in sections]
    lengths = [sum(d.values()) for d in docs]
    average = sum(lengths) / len(lengths)
    terms = query_terms(question)
    seen_in = {t: sum(1 for d in docs if t in d) for t in terms}
    scored = []
    for index, (doc, length) in enumerate(zip(docs, lengths)):
        score = 0.0
        for term, weight in terms.items():
            if term in doc:
                idf = math.log(1 + (len(docs) - seen_in[term] + 0.5) / (seen_in[term] + 0.5))
                score += weight * idf * doc[term] * (K1 + 1) / (doc[term] + K1 * (1 - B + B * length / average))
        if score >= MIN_SCORE:
            scored.append((-score, index))
    return [{**sections[i], "score": round(-neg, 3)} for neg, i in sorted(scored)[:k]]


def sections_for_rule(rule_id: str, sections: list[dict]) -> list[dict]:
    """The rulebook sections behind a rules-checker ID such as "R5". R4 is a project rule: none."""
    return [s for s in sections if rule_id in s["checker_rules"]]


if __name__ == "__main__":
    for hit in search(" ".join(sys.argv[1:]), load_sections()):
        print(f"[{hit['id']}] p.{hit['page']} score {hit['score']}\n  {hit['text'][:300]}\n")
