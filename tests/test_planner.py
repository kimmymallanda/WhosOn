import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import planner as pl  # noqa: E402
import rules_checker as rc  # noqa: E402

ROSTER = rc.load_json("roster.json")
CONFIG = rc.load_json("league_config.json")
STATE = rc.build_state(rc.load_json("season_history.json"))
EVERYONE = {p["id"] for p in ROSTER["players"]}
AVAIL = EVERYONE - {"p07", "p09", "p10", "p14"}  # demo week: Gina, Isla, Jess, Nora are out
BASE = [["p01", "p02"], ["p03", "p12"], ["p05", "p06"], ["p13", "p15"], ["p08", "p16"]]
LENA = {"p12": "until 16:00"}  # has to leave by 4:00 PM
FIRST = "13:00"


def run(available=AVAIL, **kw):
    return pl.plan(ROSTER, CONFIG, STATE, available, FIRST, **kw)


def legal(option, available=AVAIL):
    return rc.check_lineup(option["lineup"], ROSTER, CONFIG, set(available), STATE) == []


def line_of(option, pid):
    """Line the player plays, or None if she is on the bench."""
    return next((i for i, pair in enumerate(option["lineup"], 1) if pid in pair), None)


def test_every_option_is_legal_and_distinct():
    r = run(windows=LENA)
    assert r["complete"] and len(r["options"]) == 3
    assert all(legal(o) for o in r["options"])
    assert len({str(o["lineup"]) for o in r["options"]}) == 3
    assert [o["score"] for o in r["options"]] == sorted(o["score"] for o in r["options"])


def test_keeps_last_weeks_lineup_when_nothing_changed():
    assert run(windows=LENA)["options"][0]["lineup"] == BASE


def test_player_who_must_leave_early_stays_on_the_first_lines():
    for o in run(windows=LENA)["options"]:
        # Lena: lines 1-2 start 1:00 PM, so even a 3-hour line ends by 4:00 PM
        assert line_of(o, "p12") in (1, 2)


def test_carla_drops_dana_takes_line_2_and_nothing_else_moves():
    r = run(AVAIL - {"p03"}, windows=LENA, baseline=BASE)
    best = r["options"][0]
    assert best["lineup"] == [["p01", "p02"], ["p04", "p12"], ["p05", "p06"], ["p13", "p15"], ["p08", "p16"]]
    assert best["bench"] == ["p11"]
    assert all(line_of(o, "p11") != 2 for o in r["options"])  # Kara can never take line 2 (R6)
    assert all(legal(o, AVAIL - {"p03"}) for o in r["options"])


def test_finds_a_reshuffle_when_the_obvious_sub_is_missing():
    avail = AVAIL - {"p03", "p04"}  # Carla and Dana both out
    r = run(avail, windows=LENA, baseline=BASE)
    assert r["options"] and all(legal(o, avail) for o in r["options"])
    assert all(line_of(o, "p11") in (None, 3, 4, 5) for o in r["options"])  # Kara only reaches lines 3-5
    assert any(line_of(o, "p11") is not None for o in r["options"])  # and the planner does use her


def test_too_few_players():
    r = run(set(sorted(AVAIL)[:9]))
    assert r["options"] == [] and "Only 9 players are available and 10 are needed" in r["none_reason"]


def test_time_limit_that_fits_no_line_excludes_the_player():
    r = run(windows={"p12": "until 13:30"})  # a 1-hour line starting at 1:00 PM ends at 2:00 PM
    assert r["options"] and all("p12" not in sum(o["lineup"], []) for o in r["options"])


def test_risky_time_limit_is_flagged():
    # Leaves by 2:30 PM: fits a 1-hour line at 1:00 PM but not a long one.
    r = run(windows={"p12": "until 14:30"}, fixed={2: ["p03", "p12"]})
    best = r["options"][0]
    assert best["breakdown"]["risky"] == 12
    assert any("Lena may have to leave early" in w for w in best["warnings"])


def test_exclude_and_fixed():
    r = run(exclude=["p01"], fixed={3: ["p05", "p06"]})
    assert r["options"]
    for o in r["options"]:
        assert "p01" not in sum(o["lineup"], []) and o["lineup"][2] == ["p05", "p06"]


def test_fixed_pair_that_breaks_a_rule_gives_no_lineup():
    r = run(fixed={1: ["p11", "p12"]})  # Kara cannot play line 1
    assert r["options"] == [] and r["none_reason"]


def test_reserve_player_is_used_only_when_needed():
    reserve = ["p04"]
    plenty = run(AVAIL - {"p04"}, reserve=reserve)
    assert all("p04" not in sum(o["lineup"], []) for o in plenty["options"])
    short = set(sorted(AVAIL - {"p04"})[:9])
    needed = pl.plan(ROSTER, CONFIG, STATE, short, FIRST, reserve=reserve)
    assert needed["options"] and "p04" in sum(needed["options"][0]["lineup"], [])
    assert any("only if needed" in w for w in needed["options"][0]["warnings"])


def test_captain_ranking_sets_the_order_when_there_is_no_history():
    rank = ["p01", "p02", "p03", "p04", "p05", "p06", "p08", "p11", "p12", "p13"]
    r = pl.plan(ROSTER, CONFIG, rc.State(), set(rank), FIRST, ranking=rank)
    assert r["options"][0]["lineup"] == [["p01", "p02"], ["p03", "p04"], ["p05", "p06"], ["p08", "p11"], ["p12", "p13"]]
    assert r["options"][0]["breakdown"]["rank"] == 0


def test_every_line_has_a_reason_with_a_rule_id():
    for line in run(windows=LENA)["options"][0]["lines"]:
        assert line["reasons"] and any("(R" in x for x in line["reasons"])
    lena = run(windows=LENA)["options"][0]["lines"][1]
    assert any("Lena: done by 4:00 PM" in x for x in lena["reasons"])


def test_search_budget_is_reported():
    assert run(node_budget=5)["complete"] is False


def test_same_input_gives_same_output():
    assert run(windows=LENA) == run(windows=LENA)


def all_lineups(players):
    """Every way to put these players into 5 ordered pairs: 113,400 for 10 players."""
    def rec(left, chosen):
        if not left:
            yield chosen
            return
        for pair in combinations(sorted(left), 2):
            yield from rec(left - set(pair), chosen + [list(pair)])
    yield from rec(set(players), [])


def test_best_option_is_the_cheapest_legal_lineup_brute_force():
    """With exactly 10 players available, compare against trying every possible lineup."""
    players = ["p01", "p02", "p03", "p12", "p05", "p06", "p13", "p15", "p08", "p16"]
    windows = LENA
    r = pl.plan(ROSTER, CONFIG, STATE, set(players), FIRST, windows=windows, baseline=BASE, k=1)
    fit, allowed, pair_cost = pl.make_scorer(ROSTER, CONFIG, STATE, sorted(players), FIRST, windows, BASE)
    best, legal_count = None, 0
    for lineup in all_lineups(players):
        if any(fit[(p, line)]["status"] == "no" for line, pair in enumerate(lineup, 1) for p in pair):
            continue
        if rc.check_lineup(lineup, ROSTER, CONFIG, set(players), STATE):
            continue
        legal_count += 1
        cost = sum(sum(pair_cost(a, b, line).values()) for line, (a, b) in enumerate(lineup, 1))
        best = cost if best is None else min(best, cost)
    assert legal_count > 1 and r["options"]
    assert r["options"][0]["score"] == best
