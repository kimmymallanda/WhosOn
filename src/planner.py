"""Lineup planner (ALTA regular season).

Code finds the legal lineups and ranks them, so a proposed lineup is legal by construction and the
captain only chooses among options. The captain decides line order: she can give a strength ranking,
fix a pair on a line, or exclude a player, and the planner honors that. A model can phrase the message
to the captain later, but it never decides who is legal.

How it works
  1. Build every pair that may legally play each line (movement rules R5 and R6, and time limits).
  2. Search line by line for the cheapest set of pairs, then run the full rules checker (R1 to R7) on each
     complete lineup, so cross-line rules such as sandbagging (R7) are enforced.
  3. Return the best few lineups with a reason for every line.

Cost (lower is better; whole numbers so results are identical in JavaScript, see n8n/src/planner_core.js)
  move      a player changes line compared with where she last played (or with the baseline lineup)
  newcomer  a player is not in the baseline lineup (only when a baseline is given)
  new_pair  the pair has not played together before (or is not in the baseline)
  risky     the player's time limit fits a short line but not a long one
  played    matches already played this season (sits out the players who have played most)
  side      both players prefer the same side (ad/ad or deuce/deuce)
  rank      distance from where the captain's ranking would put her
  reserve   a player who said she would play only if needed
"""
from __future__ import annotations

from itertools import combinations
from typing import Dict, List, Optional, Sequence

import line_times as lt
import rules_checker as rc

WEIGHTS = {"move": 4, "newcomer": 3, "new_pair": 6, "risky": 12, "played": 1, "side": 2, "rank": 2, "reserve": 10}
COMPONENTS = ["move", "newcomer", "new_pair", "risky", "played", "side", "rank", "reserve"]


def _start_times(first_start: str, n_lines: int) -> List[str]:
    first = lt.to_min(first_start)
    slots = -(-n_lines // lt.PER_SLOT)
    return ["%02d:%02d" % (((first + 60 * k) // 60) % 24, (first + 60 * k) % 60) for k in range(slots)]


def _key(pair) -> str:
    return "-".join(sorted(pair))


def make_scorer(roster, config, state, pool, first_start, windows=None, baseline=None, ranking=None, reserve=None):
    """Precompute what the cost needs. Returns (fit, allowed, pair_cost)."""
    n, size = config["lines"], config["players_per_line"]
    windows, reserve = windows or {}, set(reserve or [])
    side = {p["id"]: p.get("side", "either") for p in roster["players"]}
    times = _start_times(first_start, n)

    fit = {(p, line): lt.time_fit(windows.get(p), line, times, config) for p in pool for line in range(1, n + 1)}
    allowed = {
        p: [line for line in rc.allowed_lines_for_player(p, state, config) if fit[(p, line)]["status"] != "no"]
        for p in pool
    }

    base_line, base_pairs = {}, set()
    for i, pair in enumerate(baseline or [], start=1):
        for p in pair:
            base_line[p] = i
        base_pairs.add(_key(pair))

    ideal = {}
    if ranking:
        order = [p for p in ranking if p in pool] + [p for p in pool if p not in ranking]
        ideal = {p: min(n, 1 + i // size) for i, p in enumerate(order)}

    def pair_cost(a: str, b: str, line: int) -> Dict[str, int]:
        c = {name: 0 for name in COMPONENTS}
        for p in (a, b):
            c["played"] += WEIGHTS["played"] * state.played.get(p, 0)
            if baseline:
                if p in base_line:
                    c["move"] += WEIGHTS["move"] * abs(line - base_line[p])
                else:
                    c["newcomer"] += WEIGHTS["newcomer"]
            elif p in state.last_line:
                c["move"] += WEIGHTS["move"] * abs(line - state.last_line[p])
            if fit[(p, line)]["status"] == "risky":
                c["risky"] += WEIGHTS["risky"]
            if ranking:
                c["rank"] += WEIGHTS["rank"] * abs(line - ideal[p])
            if p in reserve:
                c["reserve"] += WEIGHTS["reserve"]
        key = _key([a, b])
        is_new = (key not in base_pairs) if baseline else (frozenset([a, b]) not in state.pair_last)
        if is_new:
            c["new_pair"] += WEIGHTS["new_pair"]
        if side[a] == side[b] and side[a] in ("ad", "deuce"):
            c["side"] += WEIGHTS["side"]
        return c

    return fit, allowed, pair_cost


def _reasons(a, b, line, roster_by_id, config, state, fit, windows):
    first = lambda pid: roster_by_id[pid]["name"].split()[0]  # noqa: E731
    out = []
    pk = frozenset([a, b])
    if pk in state.pair_last:
        last = state.pair_last[pk]
        w, l = state.pair_record.get(pk, [0, 0])
        rec = f" Record together: {w}-{l}." if w + l else ""
        if last == line:
            out.append(f"Same pair as before, last played line {line}.{rec} (R5)")
        else:
            out.append(f"Played together at line {last}, so line {line} is one move.{rec} (R5)")
    else:
        parts = []
        for p in (a, b):
            if p in state.last_line:
                parts.append(f"{first(p)} last played line {state.last_line[p]}")
            else:
                parts.append(f"{first(p)} hasn't played this season")
        out.append("New pair. " + ", ".join(parts) + f"; line {line} is within two lines for each. (R6)")
    for p in (a, b):
        if windows.get(p):
            r = fit[(p, line)]
            out.append(f"{first(p)}: {r['why']}.")
    return out


def plan(roster, config, state, available, first_start, windows=None, baseline=None, ranking=None,
         exclude=None, reserve=None, fixed=None, k=3, node_budget=200000) -> dict:
    """Return up to k legal lineups, best first. See the module docstring."""
    n, size = config["lines"], config["players_per_line"]
    windows = windows or {}
    by_id = {p["id"]: p for p in roster["players"]}
    reserve_set = set(reserve or [])
    pool = sorted(p for p in (set(available) | reserve_set) - set(exclude or []) if p in by_id)
    fixed = {int(line): sorted(pair) for line, pair in (fixed or {}).items()}
    fit, allowed, pair_cost = make_scorer(roster, config, state, pool, first_start, windows, baseline, ranking, reserve_set)

    cands = {}
    for line in range(1, n + 1):
        rows = []
        for a, b in combinations(pool, 2):
            if line in fixed and fixed[line] != [a, b]:
                continue
            if line not in allowed[a] or line not in allowed[b]:
                continue
            pk = frozenset([a, b])
            if pk in state.pair_last and abs(line - state.pair_last[pk]) > config["pair_move_limit"]:
                continue
            comps = pair_cost(a, b, line)
            rows.append((sum(comps.values()), a, b, comps))
        rows.sort(key=lambda r: (r[0], r[1], r[2]))
        cands[line] = rows

    best: list = []  # (total, key, lineup, comps list)
    stats = {"nodes": 0, "exhausted": False, "rejected": {}}

    def dfs(line, used, total, chosen, comps_list):
        if stats["exhausted"]:
            return
        if len(best) == k and total >= best[-1][0]:
            return
        if line > n:
            lineup = [[a, b] for a, b in chosen]
            violations = rc.check_lineup(lineup, roster, config, set(pool), state)
            if violations:
                for rid in sorted({v.rule_id for v in violations}):
                    stats["rejected"][rid] = stats["rejected"].get(rid, 0) + 1
                return
            best.append((total, ";".join("-".join(p) for p in lineup), lineup, list(comps_list)))
            best.sort(key=lambda r: (r[0], r[1]))
            del best[k:]
            return
        for cost, a, b, comps in cands[line]:
            stats["nodes"] += 1
            if stats["nodes"] > node_budget:
                stats["exhausted"] = True
                return
            if a in used or b in used:
                continue
            dfs(line + 1, used | {a, b}, total + cost, chosen + [(a, b)], comps_list + [comps])

    dfs(1, frozenset(), 0, [], [])

    options = []
    for rank, (total, _, lineup, comps_list) in enumerate(best, start=1):
        breakdown = {name: sum(c[name] for c in comps_list) for name in COMPONENTS}
        lines, warnings = [], []
        for line, ((a, b), comps) in enumerate(zip(lineup, comps_list), start=1):
            lines.append({
                "line": line, "start": fit[(a, line)]["start"],
                "players": [{"id": p, "name": by_id[p]["name"]} for p in (a, b)],
                "reasons": _reasons(a, b, line, by_id, config, state, fit, windows),
            })
            for p in (a, b):
                if fit[(p, line)]["status"] == "risky":
                    warnings.append(f"{by_id[p]['name'].split()[0]} may have to leave early if line {line} runs long.")
                if p in reserve_set:
                    warnings.append(f"{by_id[p]['name']} said she would play only if needed.")
        used = {p for pair in lineup for p in pair}
        options.append({
            "rank": rank, "lineup": lineup, "score": total, "breakdown": breakdown, "lines": lines,
            "bench": [p for p in pool if p not in used], "warnings": warnings,
        })

    lines_counts = [len(cands[line]) for line in range(1, n + 1)]
    reason = None
    if not options:
        need = n * size
        if len(pool) < need:
            reason = f"Only {len(pool)} players are available and {need} are needed."
        elif stats["exhausted"]:
            reason = "The search hit its limit before finding a legal lineup."
        elif 0 in lines_counts:
            line = lines_counts.index(0) + 1
            reason = f"No legal pair is available for line {line}."
        else:
            reason = "No combination of legal pairs works together (for example, the same players are needed on two lines, or sandbagging rule R7 blocks every order)."
    return {
        "options": options, "pool": pool, "complete": not stats["exhausted"], "candidates_per_line": lines_counts,
        "rejected_at_leaf": stats["rejected"], "none_reason": reason,
    }
