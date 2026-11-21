import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from rules_checker import (  # noqa: E402
    allowed_lines_for_pair, allowed_lines_for_player, build_state, check_lineup, check_roster_add,
    load_json, pair_status, parse_level_flight, strength_index,
)

ROSTER = load_json("roster.json")
CONFIG = load_json("league_config.json")
STATE = build_state(load_json("season_history.json"))

# Players: p01 Ava, p02 Brooke, p03 Carla, p04 Dana, p05 Ellie, p06 Fran, p08 Hana, p11 Kara,
# p12 Lena, p13 Maya, p15 Priya, p16 Sam. Out for the demo week: Gina p07, Isla p09, Jess p10, Nora p14.
AVAILABLE = {p["id"] for p in ROSTER["players"]} - {"p07", "p09", "p10", "p14"}

# Same pairs on the same lines as last week: the legal baseline for week 3.
BASE = [["p01", "p02"], ["p03", "p12"], ["p05", "p06"], ["p13", "p15"], ["p08", "p16"]]


def ids(violations):
    return {v.rule_id for v in violations}


def test_state_from_history():
    assert STATE.last_line["p11"] == 5  # Kara last played line 5 (week 2)
    assert STATE.pair_last[frozenset(["p01", "p02"])] == 1
    assert pair_status(STATE, ["p01", "p02"]) == "winning"  # 2-0
    assert pair_status(STATE, ["p08", "p16"]) == "losing"  # 0-1
    assert pair_status(STATE, ["p03", "p12"]) == "none"  # 1-1
    assert pair_status(STATE, ["p04", "p12"]) == "none"  # never played together


def test_valid_lineup_passes():
    assert check_lineup(BASE, ROSTER, CONFIG, AVAILABLE, STATE) == []


def test_wrong_line_count_r1():
    assert "R1" in ids(check_lineup(BASE[:4], ROSTER, CONFIG, AVAILABLE, STATE))


def test_wrong_pair_size_r1():
    bad = [["p01"]] + BASE[1:]
    assert "R1" in ids(check_lineup(bad, ROSTER, CONFIG, AVAILABLE, STATE))


def test_unknown_player_r2():
    bad = [["p01", "p99"]] + BASE[1:]
    assert "R2" in ids(check_lineup(bad, ROSTER, CONFIG, AVAILABLE, STATE))


def test_player_in_two_lines_r3():
    bad = [["p01", "p02"], ["p01", "p12"]] + BASE[2:]
    assert "R3" in ids(check_lineup(bad, ROSTER, CONFIG, AVAILABLE, STATE))


def test_unavailable_player_r4():
    out = check_lineup(BASE, ROSTER, CONFIG, AVAILABLE - {"p03"}, STATE)
    assert ids(out) == {"R4"}
    assert "Carla Ruiz" in out[0].message


def test_pair_moves_two_lines_r5():
    # Ava and Brooke last played together at line 1; line 3 is two lines away.
    lineup = [["p03", "p12"], ["p05", "p06"], ["p01", "p02"], ["p13", "p15"], ["p08", "p16"]]
    assert ids(check_lineup(lineup, ROSTER, CONFIG, AVAILABLE, STATE)) == {"R5"}


def test_player_moves_three_lines_r6():
    # Kara last played line 5; line 2 is three lines away. The pair is new, so only R6 applies.
    lineup = [["p01", "p02"], ["p11", "p12"], ["p05", "p06"], ["p13", "p15"], ["p08", "p16"]]
    out = check_lineup(lineup, ROSTER, CONFIG, AVAILABLE, STATE)
    assert ids(out) == {"R6"}
    assert "Kara Lewis" in out[0].message


def test_player_with_no_history_can_play_any_line():
    # Dana has not played this season, so line 2 is fine, and Dana + Lena is a new pair.
    lineup = [["p01", "p02"], ["p04", "p12"], ["p05", "p06"], ["p13", "p15"], ["p08", "p16"]]
    assert check_lineup(lineup, ROSTER, CONFIG, AVAILABLE, STATE) == []


def test_sandbagging_r7():
    # Winning pair Ava+Brooke moves down (1 to 2) while losing pair Hana+Sam moves up (5 to 4).
    lineup = [["p03", "p12"], ["p01", "p02"], ["p05", "p06"], ["p08", "p16"], ["p13", "p15"]]
    assert ids(check_lineup(lineup, ROSTER, CONFIG, AVAILABLE, STATE)) == {"R7"}


def test_winning_pair_moving_down_alone_is_not_sandbagging():
    lineup = [["p03", "p12"], ["p01", "p02"], ["p05", "p06"], ["p13", "p15"], ["p08", "p16"]]
    assert check_lineup(lineup, ROSTER, CONFIG, AVAILABLE, STATE) == []


def test_split_pair_example_from_the_rules():
    # ALTA III.E: a pair at line 2 splits; one goes to line 4, one to line 3.
    # When the pair plays together again, they may not play lower than line 3.
    history = {"matches": [
        {"match_id": "a", "lineup": [["x1", "x2"], ["p01", "p02"]]},
        {"match_id": "b", "lineup": [["x1", "x2"], ["x3", "x4"], ["p02", "x5"], ["p01", "x6"]]},
    ]}
    state = build_state(history)
    assert state.pair_last[frozenset(["p01", "p02"])] == 2
    assert state.last_line["p01"] == 4 and state.last_line["p02"] == 3
    # Pair rule allows lines 1-3 (one line from line 2); p01 (last line 4) allows 2-5; p02 (last line 3) allows 1-5.
    assert allowed_lines_for_pair(["p01", "p02"], state, CONFIG) == [2, 3]
    # Together again at line 4 is "lower than line 3": R5. Line 3 is fine.
    at_4 = [["x1", "x2"], ["x3", "x4"], ["x5", "x6"], ["p01", "p02"], ["x7", "x8"]]
    at_3 = [["x1", "x2"], ["x3", "x4"], ["p01", "p02"], ["x5", "x6"], ["x7", "x8"]]
    roster = {"players": [{"id": i, "name": i} for i in ["p01", "p02"] + [f"x{n}" for n in range(1, 9)]]}
    everyone = {p["id"] for p in roster["players"]}
    assert "R5" in ids(check_lineup(at_4, roster, CONFIG, everyone, state))
    assert "R5" not in ids(check_lineup(at_3, roster, CONFIG, everyone, state))


def test_provisional_lineup_does_not_change_positions():
    history = {"matches": [
        {"match_id": "a", "lineup": [["p01", "p02"], ["p03", "p12"]]},
        {"match_id": "b", "provisional": True, "lineup": [["x1", "x2"], ["x3", "x4"], ["x5", "x6"], ["p01", "p02"]]},
    ]}
    state = build_state(history)
    assert state.pair_last[frozenset(["p01", "p02"])] == 1  # tracked from the previous legal position
    assert state.played["p01"] == 2  # but it still counts as a match played


def test_allowed_lines():
    assert allowed_lines_for_player("p11", STATE, CONFIG) == [3, 4, 5]  # Kara, last line 5
    assert allowed_lines_for_player("p04", STATE, CONFIG) == [1, 2, 3, 4, 5]  # Dana, no history
    assert allowed_lines_for_pair(["p01", "p02"], STATE, CONFIG) == [1, 2]
    assert allowed_lines_for_pair(["p04", "p12"], STATE, CONFIG) == [1, 2, 3, 4]  # Lena last line 2


def test_roster_add_rules():
    ok = {"name": "Zoe", "level_flight": "B-3", "paid_member": True}
    assert check_roster_add(ok, CONFIG, addons_used=2, already_on_roster=False, minutes_before_start=600) == []
    assert check_roster_add(ok, CONFIG, 2, already_on_roster=True) == []  # already rostered: nothing to check
    assert ids(check_roster_add({**ok, "level_flight": "AA-2"}, CONFIG, 2, False, 600)) == {"R8"}  # stronger than the team
    assert ids(check_roster_add(ok, CONFIG, 6, False, 600)) == {"R8"}  # six add-ons already used
    assert ids(check_roster_add(ok, CONFIG, 2, False, -5)) == {"R8"}  # after the scheduled start
    assert ids(check_roster_add({**ok, "paid_member": False}, CONFIG, 2, False, 600)) == {"R8"}


def test_level_flight_order():
    # Lower numbers are stronger: AA-1 strongest, C-8 weakest.
    order = ["AA-1", "AA-2", "AA-3", "A-1", "A-2", "A-8", "B-1", "B-8", "C-1", "C-8"]
    assert [strength_index(x) for x in order] == sorted(strength_index(x) for x in order)
    assert strength_index("AA-1") == 0 and strength_index("A-1") == 3 and strength_index("C-8") == 26
    assert strength_index("a-3") == strength_index("A3") == strength_index(" A - 3 ") == 5  # forgiving about format
    assert strength_index("A") is None  # no flight


def test_level_flight_parsing():
    assert parse_level_flight("AA-3") == ("AA", 3) and parse_level_flight("B") == ("B", None)
    for bad in ("AA-4", "A-9", "A-0", "D-1", "", None, "AAA-1"):
        assert parse_level_flight(bad) is None, bad


def test_team_is_aa3_so_who_may_be_added():
    assert CONFIG["level_flight"] == "AA-3"
    cases = {"AA-3": True, "A-1": True, "A-8": True, "B-1": True, "C-8": True,  # same flight or weaker
             "AA-2": False, "AA-1": False}  # stronger
    for lf, allowed in cases.items():
        got = check_roster_add({"name": "Z", "level_flight": lf, "paid_member": True}, CONFIG, 0, False, 600)
        assert (got == []) is allowed, lf


def test_player_known_only_by_level():
    def add(lf):
        return check_roster_add({"name": "Z", "level_flight": lf, "paid_member": True}, CONFIG, 0, False, 600)
    assert add("A") == [] and add("B") == [] and add("C") == []  # a weaker level always passes
    assert "flight is needed" in add("AA")[0].message  # same level as the team (AA-3): need her flight
    # Against an A-4 team: a stronger level fails outright and the same level needs her flight.
    a4 = {**CONFIG, "level_flight": "A-4"}
    sub = lambda lf: check_roster_add({"name": "Z", "level_flight": lf, "paid_member": True}, a4, 0, False, 600)  # noqa: E731
    assert ids(sub("AA")) == {"R8"} and "must be at or below" in sub("AA")[0].message
    assert "flight is needed" in sub("A")[0].message and sub("B") == []
    assert "not a valid ALTA level flight" in check_roster_add({"name": "Z", "level_flight": "D-1", "paid_member": True}, CONFIG, 0, False, 600)[0].message
