"""Tests for the captain's setup checks (league and season, roster upload, schedule upload).

The checks are JavaScript (they run in n8n), so these tests run the generated node files in Node.js.
All spreadsheets in tests/fixtures are made up.
"""
import csv
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "n8n"))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is not installed")

LEAGUES = json.loads((ROOT / "data" / "alta_leagues.json").read_text(encoding="utf-8"))["leagues"]


def run_node(node_file, items, tmp_path, others=None):
    items_file = tmp_path / "items.json"
    items_file.write_text(json.dumps(items), encoding="utf-8")
    args = [NODE, str(ROOT / "n8n" / "test_runner.js"), str(ROOT / "n8n" / "nodes" / node_file), str(items_file)]
    if others is not None:
        other_file = tmp_path / "others.json"
        other_file.write_text(json.dumps(others), encoding="utf-8")
        args.append(str(other_file))
    res = subprocess.run(args, capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def rows(name):
    with open(ROOT / "tests" / "fixtures" / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def run_check(tmp_path, **item):
    """The shared helper node: one item in, one answer out."""
    return run_node("setup_checks.js", [item], tmp_path)[0]


def roster(tmp_path, data, **ctx):
    ctx = {"league": "Sunday Women", "roster_min": 12, **ctx}
    return run_check(tmp_path, kind="roster", rows=data, **ctx)


def schedule(tmp_path, data, **ctx):
    ctx = {"league": "Sunday Women", "year": 2027, **ctx}
    return run_check(tmp_path, kind="schedule", rows=data, **ctx)


def msgs(result, severity=None):
    return [p["message"] for p in result["problems"] if severity in (None, p["severity"])]


# ------------------------------------------------------------------ league and season

def check_league(tmp_path, league, season, level_flight=None):
    return run_check(tmp_path, kind="league", league=league, season=season, level_flight=level_flight)


def test_sunday_women_spring_is_read_back(tmp_path):
    r = check_league(tmp_path, "Sunday Women", "Spring")
    assert r["ok"] and r["lines"] == 5 and r["roster_min"] == 12 and r["day"] == "Sunday"
    for expected in ("Sunday Women plays on Sundays", "5 doubles lines", "lines 1-2 at 1:00 PM", "lines 3-4 at 2:00 PM", "line 5 at 3:00 PM", "at least 12"):
        assert expected in r["summary"], expected


def test_wrong_season_for_the_league(tmp_path):
    r = check_league(tmp_path, "Sunday Women", "Summer")
    assert not r["ok"] and "Spring or Fall" in r["error"]
    assert not check_league(tmp_path, "Mixed Doubles (Winter)", "Summer")["ok"]
    assert "don't know the league" in check_league(tmp_path, "Pickleball", "Fall")["error"]


def test_fewer_lines_are_described_correctly(tmp_path):
    r = check_league(tmp_path, "Senior Day Women", "Fall")
    assert r["ok"] and r["lines"] == 3
    assert "lines 1-2 at 10:00 AM, line 3 at 11:00 AM" in r["summary"]


def test_every_league_accepts_each_season_it_plays(tmp_path):
    pairs = [(name, s) for name, lg in LEAGUES.items() for s in lg["seasons"]]
    assert len(pairs) >= 15
    assert all(check_league(tmp_path, name, s)["ok"] for name, s in pairs)


def test_level_flight_is_checked_and_tidied(tmp_path):
    ok = check_league(tmp_path, "Sunday Women", "Spring", "aa3")
    assert ok["ok"] and ok["level_flight"] == "AA-3" and "Your team is AA-3." in ok["summary"]
    assert check_league(tmp_path, "Sunday Women", "Spring", " A - 5 ")["level_flight"] == "A-5"
    assert check_league(tmp_path, "Sunday Women", "Spring")["level_flight"] is None  # optional
    for bad in ("AA-4", "A-9", "A", "D-1", "fast"):
        r = check_league(tmp_path, "Sunday Women", "Spring", bad)
        assert not r["ok"] and "level flight like AA-3" in r["error"], bad


def test_unknown_kind_and_team_id_passthrough(tmp_path):
    assert not run_check(tmp_path, kind="shoe size")["ok"]
    assert run_check(tmp_path, kind="league", league="Men", season="Fall", team_id="abc")["team_id"] == "abc"


# ------------------------------------------------------------------ roster

def test_good_roster_with_messy_headings(tmp_path):
    r = roster(tmp_path, rows("roster_ok.csv"))
    assert r["summary"] == {"rows_read": 14, "errors": 0, "warnings": 0, "ok": True}
    p = {x["name"]: x for x in r["players"]}
    assert len(p) == 14 and p["Avery Stone"]["name"] == "Avery Stone"  # first and last name columns are joined
    assert p["Avery Stone"]["mobile"] == "+14045550101" and p["Blake Hart"]["mobile"] == "+14045550102"
    assert p["Casey Lane"]["mobile"] == "+14045550103" and p["Drew Moss"]["mobile"] is None
    assert p["Blake Hart"]["level_flight"] == "AA-3"  # "aa3" is understood
    assert [p["Avery Stone"]["side"], p["Blake Hart"]["side"], p["Drew Moss"]["side"]] == ["ad", "deuce", "either"]


def test_roster_below_the_league_minimum_warns(tmp_path):
    r = roster(tmp_path, rows("roster_ok.csv"), roster_min=16)
    assert r["summary"]["ok"] and any("found 14 players" in m and "at least 16" in m for m in msgs(r, "warning"))


def test_roster_problems_are_found_and_numbered_like_excel_rows(tmp_path):
    r = roster(tmp_path, rows("roster_problems.csv"))
    assert not r["summary"]["ok"] and r["summary"]["errors"] == 4
    by_row = {(p["row"], p["field"]): p for p in r["problems"]}
    assert by_row[(3, "name")]["severity"] == "error"  # row 1 is the heading
    assert by_row[(4, "email")]["severity"] == "error" and "no email" in by_row[(4, "email")]["message"]
    assert "does not look right" in by_row[(5, "email")]["message"]
    assert "already used in row 2" in by_row[(6, "email")]["message"]
    assert by_row[(7, "name")]["severity"] == "warning" and "Ava Test appears twice" in by_row[(7, "name")]["message"]
    assert by_row[(9, "mobile")]["severity"] == "warning" and by_row[(9, "level_flight")]["severity"] == "warning"
    assert by_row[(9, "side")]["severity"] == "warning"
    assert [x["name"] for x in r["players"]] == ["Ava Test", "Ava Test", "Eli Test"]  # rows with errors are left out
    assert r["players"][2]["mobile"] is None and r["players"][2]["level_flight"] is None and r["players"][2]["side"] == "either"
    assert "needs 4 fixes" in r["report_html"] and "Nothing was saved" in r["report_html"]


def test_missing_email_column_is_a_clear_error(tmp_path):
    r = roster(tmp_path, [{"Name": "Avery Stone", "Cell": "404-555-0101"}])
    assert not r["summary"]["ok"] and any('"Email" column' in m for m in msgs(r, "error"))
    assert r["players"] == []  # no half-read roster


def test_missing_name_column_is_a_clear_error(tmp_path):
    r = roster(tmp_path, [{"Email": "a@example.com"}])
    assert any('"Name" column' in m for m in msgs(r, "error"))


def test_roster_report_escapes_html(tmp_path):
    r = roster(tmp_path, [{"Name": "<b>Eve</b>", "Email": "eve@example.com"}])
    assert "<b>Eve</b>" not in r["report_html"] and "&lt;b&gt;Eve&lt;/b&gt;" in r["report_html"]


def test_blank_rows_are_ignored(tmp_path):
    r = roster(tmp_path, [{"Name": "A B", "Email": "ab@example.com"}, {"Name": "", "Email": ""}, {}])
    assert r["summary"]["rows_read"] == 1 and len(r["players"]) == 1


# ------------------------------------------------------------------ schedule

def test_good_schedule_with_mixed_date_formats(tmp_path):
    r = schedule(tmp_path, rows("schedule_ok.csv"))
    assert r["summary"] == {"rows_read": 6, "errors": 0, "warnings": 0, "ok": True}
    assert [m["date"] for m in r["matches"]] == ["2027-04-11", "2027-04-18", "2027-04-25", "2027-05-02", "2027-05-09", "2027-05-16"]
    assert [m["week"] for m in r["matches"]] == [1, 2, 3, 4, 5, 6]
    assert [m["home_away"] for m in r["matches"]] == ["home", "away", "away", "home", "away", "home"]
    assert r["matches"][0]["facility"] == "Our courts" and r["matches"][1]["facility"] is None


def test_schedule_problems(tmp_path):
    r = schedule(tmp_path, rows("schedule_problems.csv"))
    assert not r["summary"]["ok"]
    by_row = {(p["row"], p["field"]): p for p in r["problems"]}
    assert by_row[(3, "date")]["severity"] == "warning" and "Monday" in by_row[(3, "date")]["message"]
    assert "no opponent" in by_row[(4, "opponent")]["message"]
    assert '"Neutral" is not Home or Away' in by_row[(5, "home_away")]["message"]
    assert "already used in row 2" in by_row[(6, "date")]["message"]
    assert "could not read the date" in by_row[(7, "date")]["message"]
    assert r["summary"]["errors"] == 4 and any("usually 6 or 7 matches" in m for m in msgs(r, "warning"))


def test_excel_date_numbers_and_missing_year(tmp_path):
    serial = (datetime.date(2027, 4, 11) - datetime.date(1899, 12, 30)).days
    r = schedule(tmp_path, [{"Date": serial, "Opponent": "A", "Home/Away": "Home"}, {"Date": str(serial + 7), "Opponent": "B", "Home/Away": "@"},
                            {"Date": "Apr 25", "Opponent": "C", "Home/Away": "Away"}])
    assert [m["date"] for m in r["matches"]] == ["2027-04-11", "2027-04-18", "2027-04-25"]
    assert r["matches"][1]["home_away"] == "away"
    no_year = schedule(tmp_path, [{"Date": "Apr 25", "Opponent": "C", "Home/Away": "Away"}], year=None)
    assert any("could not read the date" in m for m in msgs(no_year, "error"))


def test_schedule_uses_the_leagues_own_weekday(tmp_path):
    saturday = [{"Date": "2027-04-10", "Opponent": "A", "Home/Away": "Home"}]
    assert not any("plays on" in m for m in msgs(schedule(tmp_path, saturday, league="Men")))  # Men play Saturdays
    assert any("plays on Sundays" in m for m in msgs(schedule(tmp_path, saturday)))


def test_missing_schedule_columns(tmp_path):
    r = schedule(tmp_path, [{"Date": "2027-04-11", "Team": "A"}])
    assert any('"Home/Away" column' in m for m in msgs(r, "error")) and r["matches"] == []


# ------------------------------------------------------------------ emails

INVITE = {"captain_name": "Sam Captain", "captain_email": " Sam@Example.com ", "base_url": "https://example.n8n.cloud",
          "team_id": "abc123", "now_iso": "2027-03-01T12:00:00.000Z"}


def test_invite_email(tmp_path):
    r = run_node("invite_email.js", [INVITE], tmp_path)[0]
    assert r["link"] == "https://example.n8n.cloud/form/tca-setup-2-league?team_id=abc123"
    assert r["expires_at"] == "2027-03-08T12:00:00.000Z" and r["captain_email"] == "sam@example.com"
    assert r["subject"] == "Set up your team with WhosOn"
    for expected in ("Hi Sam,", r["link"], "Set up my team", "approve every lineup", "works for 7 days"):
        assert expected in r["html"], expected


def test_invite_makes_a_private_hard_to_guess_id_when_none_is_given(tmp_path):
    item = {k: v for k, v in INVITE.items() if k != "team_id"}
    a, b = run_node("invite_email.js", [item], tmp_path)[0], run_node("invite_email.js", [item], tmp_path)[0]
    assert a["team_id"] != b["team_id"]
    assert len(a["team_id"]) == 36 and all(c in "0123456789abcdef" for c in a["team_id"])
    assert a["team_id"] in a["link"]


def test_invite_escapes_hostile_names(tmp_path):
    r = run_node("invite_email.js", [{**INVITE, "captain_name": "<script>alert(1)</script> Eve"}], tmp_path)[0]
    assert "<script>" not in r["html"] and "&lt;script&gt;" in r["html"]


def test_intro_emails_one_per_player(tmp_path):
    players = [{"name": "Avery Stone", "email": "avery@example.com"}, {"name": "Blake Hart", "email": "blake@example.com"},
               {"name": "<b>Eve</b> Moss", "email": "eve@example.com"}]
    out = run_node("intro_emails.js", [{"captain_name": "Sam Captain", "league": "Sunday Women", "season": "Spring", "players": players}], tmp_path)
    assert [e["to"] for e in out] == ["avery@example.com", "blake@example.com", "eve@example.com"]
    assert out[0]["subject"] == "Sam Captain is using WhosOn for your Sunday Women team"
    for expected in ("Hi Avery,", "this Spring season", "reply in your own words", "approves every lineup"):
        assert expected in out[0]["html"], expected
    assert "<b>Eve</b>" not in out[2]["html"]


# ---------------------------------------------------------------- schedule from ALTA's PDF text

PDF_TEXT = (ROOT / "tests" / "fixtures" / "schedule_pdf_text.txt").read_text(encoding="utf-8")


def pdf_schedule(tmp_path, text=PDF_TEXT, **ctx):
    ctx = {"league": "Sunday Women", "season": "Fall", "year": 2026, "level_flight": "AA-3", **ctx}
    return run_check(tmp_path, kind="schedule", rows=[{"text": text}], pdf_text=text, **ctx)


def test_pdf_schedule_for_one_team(tmp_path):
    r = pdf_schedule(tmp_path, team_no=1)
    assert r["ok"] and r["summary"]["errors"] == 0
    assert [(m["week"], m["date"], m["home_away"], m["opponent"]) for m in r["matches"]] == [
        (1, "2026-09-13", "home", "Team 4 (TEST ACADEMY/OUTDOOR COURTS)"),
        (2, "2026-09-20", "away", "Team 2 (EXAMPLE CLUB)"),
        (3, "2026-09-27", "away", "Team 3 (DEMO TENNIS CENTER)"),
        (4, "2026-10-04", "home", "Team 3 (DEMO TENNIS CENTER)"),
        (5, "2026-10-11", "home", "Team 4 (TEST ACADEMY/OUTDOOR COURTS)"),
        (6, "2026-10-18", "away", "Team 4 (TEST ACADEMY/OUTDOOR COURTS)"),
    ]


def test_pdf_facility_is_where_the_match_is_played(tmp_path):
    r = pdf_schedule(tmp_path, team_no=1)
    assert r["matches"][0]["facility"] == "SAMPLE PARK/HARD COURTS"   # home
    assert r["matches"][1]["facility"] == "EXAMPLE CLUB"              # away at team 2


def test_pdf_team_found_from_the_captains_name(tmp_path):
    r = pdf_schedule(tmp_path, captain_name="Casey Hart")
    assert r["ok"] and r["team_no"] == 2
    assert any("matched you to Team 2" in m for m in msgs(r, "warning"))
    r = pdf_schedule(tmp_path, captain_name="Drew Lane")  # a co-captain counts too
    assert r["team_no"] == 2


def test_pdf_asks_which_team_when_it_cannot_tell(tmp_path):
    r = pdf_schedule(tmp_path, captain_name="Kim")
    assert not r["ok"] and r["matches"] == []
    assert any("Which team are you" in m and "Team 3: DEMO TENNIS CENTER" in m for m in msgs(r, "error"))


def test_pdf_wrong_team_number(tmp_path):
    r = pdf_schedule(tmp_path, team_no=9)
    assert not r["ok"] and any("Team 9 does not play" in m for m in msgs(r, "error"))


def test_pdf_must_match_the_league_season_and_year_chosen(tmp_path):
    r = pdf_schedule(tmp_path, team_no=1, season="Spring", year=2027, league="Men")
    errs = " ".join(msgs(r, "error"))
    assert not r["ok"] and "Sunday Women" in errs and "Fall season" in errs and "2026" in errs
    r = pdf_schedule(tmp_path, team_no=1, level_flight="A-4")
    assert r["ok"] and any("AA-3" in m for m in msgs(r, "warning"))


def test_pdf_with_no_schedule_in_it(tmp_path):
    r = pdf_schedule(tmp_path, text="Hello, this is a menu.", team_no=1)
    assert not r["ok"] and any("could not find any matches" in m for m in msgs(r, "error"))


def test_pdf_bye_week_is_skipped_with_a_note(tmp_path):
    text = PDF_TEXT.replace("Team 4 at Team 1 Team 3 at Team 2", "Team 4 at Team 3")
    r = pdf_schedule(tmp_path, text=text, team_no=1)
    assert len(r["matches"]) == 5 and any("bye week" in m for m in msgs(r, "warning"))


def test_pdf_text_with_everything_on_one_line(tmp_path):
    r = pdf_schedule(tmp_path, text=" ".join(PDF_TEXT.splitlines()), team_no=1)
    assert r["ok"] and len(r["matches"]) == 6


# ---------------------------------------------------------------- the lineup entry sheet

ENTRY = {
    "captain_name": "Sam Captain", "captain_email": "sam@example.com", "league": "Sunday Women", "season": "Fall", "year": 2026,
    "level_flight": "AA-3", "week": 1, "date": "2026-09-13", "home_away": "away", "opponent": "Team 6", "facility": "GSU-Clarkston Campus",
    "start_times": ["13:00", "14:00", "15:00"],
    "lineup": [["Tracey Yang", "Isabella Herrero"], ["Kelsey O'Regan", "Hayden Smith"], ["Keyu Jin", "Michelle Samson"],
               ["Lindsey King", "Kimberly Hackworth"], ["Ava Chen", "Brooke Patel"]],
}


def test_entry_sheet_looks_like_alta_page(tmp_path):
    out = run_node("entry_sheet.js", [ENTRY], tmp_path)[0]
    assert out["to"] == "sam@example.com" and out["subject"].startswith("Week 1 lineup")
    h = out["html"]
    for expected in ("2026 Fall Sunday Women AA-3", "Week 1 (Sep 13) AT GSU-CLARKSTON CAMPUS", "1D", "5D", "TRACEY YANG", "ISABELLA HERRERO",
                     "09/13/2026 1:00 PM", "09/13/2026 2:00 PM", "09/13/2026 3:00 PM", "press <b>Publish</b> yourself"):
        assert expected in h, expected
    assert h.count("09/13/2026 1:00 PM") == 2 and "different from the usual time" not in h


def test_entry_sheet_line_time_override_and_comment(tmp_path):
    a = {**ENTRY, "line_times": {"3": "10:00"}, "comment": "Line 3 plays at 10 am at Bitsy Grant.\nEveryone else at 1 pm.", "home_away": "home"}
    h = run_node("entry_sheet.js", [a], tmp_path)[0]["html"]
    assert "09/13/2026 10:00 AM" in h and "different from the usual time" in h
    assert "Comment to paste into ALTA" in h and "Bitsy Grant" in h and "HOME" in h


def test_entry_sheet_escapes_names(tmp_path):
    a = {**ENTRY, "lineup": [["<b>X</b>", "Y"]] + ENTRY["lineup"][1:]}
    assert "<b>X</b>" not in run_node("entry_sheet.js", [a], tmp_path)[0]["html"]
