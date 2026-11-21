import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from line_times import fmt, line_schedule, parse_window, time_fit, to_min  # noqa: E402
from messages import availability_request, backup_note, line_assignment, lineup_messages, sub_request  # noqa: E402
from rules_checker import load_json  # noqa: E402

CONFIG = load_json("league_config.json")
LEAGUES = load_json("alta_leagues.json")["leagues"]
ROSTER = load_json("roster.json")
SUNDAY = LEAGUES["Sunday Women"]["start_times"]
MATCH = {"date": "2027-04-25", "home": False, "opponent": "Oak Hill TC"}


def test_team_config_matches_its_league():
    assert CONFIG["lines"] == LEAGUES[CONFIG["league"]]["lines"] == 5


def test_line_schedule_sunday_women():
    assert line_schedule(5, SUNDAY) == {1: "13:00", 2: "13:00", 3: "14:00", 4: "14:00", 5: "15:00"}


def test_line_schedule_fewer_lines():
    assert line_schedule(3, LEAGUES["Senior Day Women"]["start_times"]) == {1: "10:00", 2: "10:00", 3: "11:00"}
    assert line_schedule(4, LEAGUES["Senior Mixed"]["start_times"]) == {1: "10:00", 2: "10:00", 3: "11:00", 4: "11:00"}


def test_every_league_has_enough_start_times():
    for name, lg in LEAGUES.items():
        slots = -(-lg["lines"] // 2)  # ceil(lines / 2)
        assert len(lg["start_times"]) == slots, name


def test_fmt_and_parse():
    assert fmt(to_min("13:00")) == "1:00 PM" and fmt(to_min("09:30")) == "9:30 AM" and fmt(to_min("12:05")) == "12:05 PM"
    assert parse_window("until 16:00") == {"earliest_start": None, "latest_end": 960}
    assert parse_window("after 14:00") == {"earliest_start": 840, "latest_end": None}
    assert parse_window(None) == {"earliest_start": None, "latest_end": None}


def test_leave_by_four_fits_only_the_first_slot():
    # Lena has to leave by 4:00 PM. Lines 1-2 start 1:00 PM, so even a 3-hour line is done by 4:00.
    assert time_fit("until 16:00", 1, SUNDAY, CONFIG)["status"] == "ok"
    assert time_fit("until 16:00", 2, SUNDAY, CONFIG)["status"] == "ok"
    assert time_fit("until 16:00", 3, SUNDAY, CONFIG)["status"] == "risky"  # 2:00 start, long line ends 5:00
    assert time_fit("until 16:00", 5, SUNDAY, CONFIG)["status"] == "risky"  # 3:00 start, short line ends 4:00
    assert time_fit("until 15:30", 5, SUNDAY, CONFIG)["status"] == "no"


def test_start_after_a_time():
    assert time_fit("after 14:00", 1, SUNDAY, CONFIG)["status"] == "no"  # 1:00 PM is too early
    assert time_fit("after 14:00", 3, SUNDAY, CONFIG)["status"] == "ok"
    assert time_fit(None, 1, SUNDAY, CONFIG)["status"] == "ok"


def test_messages_carry_the_right_facts():
    t = line_assignment("Carla", 2, "Lena Fischer", MATCH, SUNDAY, CONFIG)
    for expected in ("Line 2", "Lena Fischer", "Sunday, Apr 25", "Oak Hill TC", "1:00 PM", "12:50 PM", "4:00 PM"):
        assert expected in t, expected
    late = line_assignment("Maya", 5, "Priya Shah", MATCH, SUNDAY, CONFIG)
    assert "3:00 PM" in late and "2:50 PM" in late and "6:00 PM" in late


def test_request_lists_all_start_times():
    t = availability_request("Lena", MATCH, SUNDAY)
    assert "1:00 PM" in t and "2:00 PM" in t and "3:00 PM" in t and "1 to 3 hours" in t


def test_lineup_messages_one_per_player():
    lineup = [["p01", "p02"], ["p03", "p12"], ["p05", "p06"], ["p13", "p15"], ["p08", "p16"]]
    msgs = lineup_messages(lineup, ROSTER, MATCH, SUNDAY, CONFIG)
    assert len(msgs) == 10
    assert "Line 3" in msgs["p05"] and "Fran Okafor" in msgs["p05"] and "2:00 PM" in msgs["p05"]
    assert "Line 5" in msgs["p16"] and "Hana Sato" in msgs["p16"]


def test_other_message_types():
    assert "backup" in backup_note("Kara", MATCH)
    s = sub_request("Dana", 2, "Lena Fischer", MATCH, SUNDAY, CONFIG)
    assert "Line 2" in s and "1:00 PM" in s and "Lena Fischer" in s
