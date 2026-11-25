"""Retrieval tests. Skipped when the gitignored rulebook has not been built."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import rules_search as rs  # noqa: E402

pytestmark = pytest.mark.skipif(not rs.SECTIONS.exists(), reason="run src/build_rulebook.py first")


def questions():
    return [c["q"] for name in ("rules_questions", "rules_questions_heldout")
            for c in json.loads((ROOT / "data" / f"{name}.json").read_text(encoding="utf-8"))]


def test_movement_question_cites_the_movement_rule():
    assert rs.search("Can a pair move up two lines?", rs.load_sections())[0]["id"] == "III.E"


def test_unrelated_question_finds_nothing():
    assert rs.search("recipe for banana bread", rs.load_sections()) == []


@pytest.mark.parametrize("rule", ["R1", "R2", "R3", "R5", "R6", "R7", "R8"])
def test_every_checker_rule_has_a_source(rule):
    assert rs.sections_for_rule(rule, rs.load_sections())


@pytest.mark.skipif(not shutil.which("node"), reason="needs Node.js")
def test_javascript_returns_the_same_sections(tmp_path):
    script = tmp_path / "run.js"
    script.write_text(
        (ROOT / "n8n" / "src" / "search_core.js").read_text(encoding="utf-8")
        + f"\nconst s = JSON.parse(require('fs').readFileSync({json.dumps(str(rs.SECTIONS))}, 'utf8'));"
        + f"\nconsole.log(JSON.stringify({json.dumps(questions())}.map((q) => search(q, s).map((h) => h.id))));",
        encoding="utf-8")
    got = json.loads(subprocess.run(["node", str(script)], capture_output=True, text=True, check=True).stdout)
    sections = rs.load_sections()
    assert got == [[h["id"] for h in rs.search(q, sections)] for q in questions()]
