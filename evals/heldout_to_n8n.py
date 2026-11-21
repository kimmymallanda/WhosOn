"""Print the held-out replies as JavaScript you can paste into the n8n workflow.

Usage:  python evals/heldout_to_n8n.py > heldout_code_node.js

In n8n, open the first Code node ("Code in JavaScript"), replace its code with this
output, run the workflow, and read the SCORE row from the scoring Code node.
Put the original code back afterwards (or work in a duplicate of the workflow) so
the tuning set stays available.

Do not edit the system prompt after reading the held-out results without writing a
fresh held-out set. See CLAUDE.md.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    gold = [json.loads(l) for l in (DATA / "heldout_replies.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    schedule = json.loads((DATA / "schedule.json").read_text(encoding="utf-8"))
    matches = {m["match_id"]: m for m in schedule["matches"]}
    match_id = gold[0]["match_id"]
    m = matches[match_id]
    match = {
        "match_date": m["date"],
        "match_time": m["time"],
        "home_away": "home" if m["home"] else "away",
        "opponent": m["opponent"],
        "history": "none",
    }
    lines = []
    for g in gold:
        if g["match_id"] != match_id:
            raise SystemExit("All held-out replies must be for one match.")
        label = g["label"]
        expected = {"status": label["status"], "time_window": label.get("time_window")}
        item = {"player_id": g["player_id"], "reply_text": g["text"], "expected": expected}
        lines.append("  " + json.dumps(item, ensure_ascii=False) + ",")
    print(f"const match = {json.dumps(match, ensure_ascii=False)};\n")
    print("const replies = [")
    print("\n".join(lines))
    print("];\n")
    print("return replies.map(r => ({ json: { ...match, ...r, player_name: r.player_id } }));")


if __name__ == "__main__":
    main()
