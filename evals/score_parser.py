"""Score availability-parser predictions against a labeled set.

Usage:
  python evals/score_parser.py preds.jsonl                  # data/labeled_replies.jsonl (tuning set)
  python evals/score_parser.py preds.jsonl --heldout        # data/heldout_replies.jsonl (never tune on this)
  python evals/score_parser.py preds.jsonl --labels FILE    # any other labeled file

preds.jsonl: one JSON object per line, in the same order as the labels file.
Each needs {"status": "..."}. If it also has these keys, they are checked too:
  time_window   compared to label.time_window (exact string, 24-hour form)
  conditions    must contain label.conditions_contains (case-insensitive), when the label has one
  follow_up     must be non-empty when label.needs_follow_up is true
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def load(path: Path) -> list:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def check_row(gold: dict, pred: dict) -> dict:
    """Return {check_name: True/False} for every check that applies to this row."""
    label = gold["label"]
    results = {"status": pred.get("status") == label["status"]}
    if "time_window" in pred:
        results["time_window"] = pred.get("time_window") == label.get("time_window")
    if label.get("conditions_contains") and "conditions" in pred:
        results["conditions"] = label["conditions_contains"].lower() in (pred.get("conditions") or "").lower()
    if label.get("needs_follow_up") and "follow_up" in pred:
        results["follow_up"] = bool((pred.get("follow_up") or "").strip())
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("preds")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--heldout", action="store_true", help="score against data/heldout_replies.jsonl")
    group.add_argument("--labels", help="path to a labeled .jsonl file")
    args = ap.parse_args()

    labels_path = (
        DATA / "heldout_replies.jsonl" if args.heldout else Path(args.labels) if args.labels else DATA / "labeled_replies.jsonl"
    )
    gold = load(labels_path)
    preds = load(Path(args.preds))
    if len(gold) != len(preds):
        sys.exit(f"Expected {len(gold)} predictions for {labels_path.name}, got {len(preds)}.")

    totals, passed = Counter(), Counter()
    strict_ok = 0
    status_misses = Counter()
    unneeded_follow_ups = 0
    for g, p in zip(gold, preds):
        checks = check_row(g, p)
        for name, ok in checks.items():
            totals[name] += 1
            passed[name] += ok
        if all(checks.values()):
            strict_ok += 1
        else:
            failed = ", ".join(n for n, ok in checks.items() if not ok)
            print(f"MISS [{failed}]  want={g['label']['status']:12} got={p.get('status')!s:12} text={g['text']!r}")
            if not checks["status"]:
                status_misses[(g["label"]["status"], p.get("status"))] += 1
        if "follow_up" in p and (p.get("follow_up") or "").strip() and g["label"].get("needs_follow_up") is False:
            unneeded_follow_ups += 1

    n = len(gold)
    print(f"\nFile: {labels_path.name}  ({n} replies)")
    print(f"Status accuracy: {passed['status']}/{n} = {passed['status'] / n:.0%} (target 95%)")
    for name in ("time_window", "conditions", "follow_up"):
        if totals[name]:
            print(f"  {name}: {passed[name]}/{totals[name]}")
    print(f"All applicable checks: {strict_ok}/{n} = {strict_ok / n:.0%}")
    if unneeded_follow_ups:
        print(f"  Follow-ups sent when none was needed: {unneeded_follow_ups} (annoys players; not counted as a miss)")
    for (want, got), count in status_misses.most_common():
        print(f"  {want} -> {got}: {count}")


if __name__ == "__main__":
    main()
