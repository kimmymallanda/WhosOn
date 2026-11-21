"""Proves the n8n Code-node JavaScript gives the same answers as the Python rules code.

Needs Node.js. Run `python n8n/build_nodes.py` after changing n8n/src/*.js or any data file.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "n8n"))
import build_nodes  # noqa: E402

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is not installed")


def run_node(node_file, items, tmp_path):
    items_file = tmp_path / "items.json"
    items_file.write_text(json.dumps(items), encoding="utf-8")
    res = subprocess.run(
        [NODE, str(ROOT / "n8n" / "test_runner.js"), str(ROOT / "n8n" / "nodes" / node_file), str(items_file)],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def test_generated_files_are_up_to_date():
    for name, text in build_nodes.build().items():
        assert (ROOT / "n8n" / name).read_text(encoding="utf-8") == text, f"n8n/{name} is stale: run python n8n/build_nodes.py"


def test_rules_checker_matches_python(tmp_path):
    data = json.loads((ROOT / "n8n" / "checker_cases.json").read_text(encoding="utf-8"))
    got = run_node("rules_checker.js", data["lineups"], tmp_path)
    assert got == data["expected"]["lineups"]


def test_lineup_cases_cover_every_rule():
    data = json.loads((ROOT / "n8n" / "checker_cases.json").read_text(encoding="utf-8"))
    seen = {v["rule_id"] for c in data["expected"]["lineups"] for v in c["violations"]}
    assert seen == {"R1", "R2", "R3", "R4", "R5", "R6", "R7"}
    assert any(c["ok"] for c in data["expected"]["lineups"])  # and some legal lineups


def test_line_time_fit_matches_python(tmp_path):
    data = json.loads((ROOT / "n8n" / "checker_cases.json").read_text(encoding="utf-8"))
    expected = data["expected"]["times"]
    items = [{"match_time": c["match_time"], "time_window": c["time_window"], "player_id": f"p{i}"} for i, c in enumerate(expected)]
    got = run_node("line_time_fit.js", items, tmp_path)
    assert len(got) == len(expected)
    for g, e in zip(got, expected):
        for key in ("line_fit", "safe_lines", "risky_lines", "blocked_lines", "line_fit_notes"):
            assert g[key] == e[key], (e["match_time"], e["time_window"], key)
        assert g["match_time"] == e["match_time"]  # incoming fields are kept


def test_planner_matches_python(tmp_path):
    data = json.loads((ROOT / "n8n" / "checker_cases.json").read_text(encoding="utf-8"))
    got = run_node("lineup_planner.js", data["planner_cases"], tmp_path)
    expected = data["expected"]["planner"]
    assert len(got) == len(expected) == 9
    for g, e in zip(got, expected):
        assert g == e, e["scenario"]


def test_planner_scenarios_cover_the_interesting_cases():
    data = json.loads((ROOT / "n8n" / "checker_cases.json").read_text(encoding="utf-8"))
    by_name = {e["scenario"]: e for e in data["expected"]["planner"]}
    assert by_name["Carla drops at 9pm"]["options"][0]["lineup"][1] == ["p04", "p12"]  # Dana takes line 2
    assert by_name["Only nine players"]["options"] == [] and by_name["Only nine players"]["none_reason"]
    assert by_name["Search limit reached"]["complete"] is False
    assert all(o["warnings"] for o in by_name["Time limit might not fit"]["options"])
    assert any("only if needed" in w for w in by_name["Emergency sub needed"]["options"][0]["warnings"])


def test_planner_options_pass_the_rules_checker_end_to_end(tmp_path):
    """planner -> options_to_check -> rules_checker, the same path the n8n workflow runs."""
    data = json.loads((ROOT / "n8n" / "checker_cases.json").read_text(encoding="utf-8"))
    planned = run_node("lineup_planner.js", data["planner_cases"][:4], tmp_path)
    to_check = run_node("options_to_check.js", planned, tmp_path)
    assert len(to_check) == sum(len(p["options"]) for p in planned) > 0
    checked = run_node("rules_checker.js", to_check, tmp_path)
    assert all(c["ok"] for c in checked), [c for c in checked if not c["ok"]]


def test_planner_scenarios_node_outputs_the_demo_cases(tmp_path):
    data = json.loads((ROOT / "n8n" / "checker_cases.json").read_text(encoding="utf-8"))
    assert run_node("planner_scenarios.js", [{}], tmp_path) == data["planner_cases"][:4]


def test_lineups_node_outputs_the_cases(tmp_path):
    data = json.loads((ROOT / "n8n" / "checker_cases.json").read_text(encoding="utf-8"))
    assert run_node("lineups_to_check.js", [{}], tmp_path) == data["lineups"]
