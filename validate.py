"""Evaluate the current decision rule on a reproducible train/holdout split.

The confidence thresholds are fixed in postprocess.py. This script reports
coverage and false accepts for each side of a deterministic split; it does not
change the thresholds or write answers.
"""

import argparse
import json
import random
from pathlib import Path
from typing import Any

import postprocess as pp


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def normalized(value: Any) -> str:
    return " ".join(str(value or "").split()).upper()


def score(records: list[dict[str, Any]], labels: dict[str, dict[str, Any]]) -> dict[str, int]:
    accepted = wrong = 0
    for record in records:
        fields = pp.candidate_fields(record)
        if fields is None:
            continue
        accepted += 1
        truth = labels[record["doc_id"]]
        if any(normalized(fields.get(name)) != normalized(truth.get(name)) for name in pp.FIELDS):
            wrong += 1
    return {"total": len(records), "accepted": accepted,
            "rejected": len(records) - accepted, "wrong_accepts": wrong}


def print_score(name: str, result: dict[str, int]) -> None:
    accepted = result["accepted"]
    total = result["total"]
    precision = "n/a" if accepted == 0 else f"{(accepted - result['wrong_accepts']) / accepted:.1%}"
    coverage = "n/a" if total == 0 else f"{accepted / total:.1%}"
    print(f"{name}: total={total}, accepted={accepted}, rejected={result['rejected']}, "
          f"wrong_accepts={result['wrong_accepts']}, coverage={coverage}, "
          f"precision_among_accepted={precision}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", type=Path, help="train_predictions.jsonl")
    parser.add_argument("labels", type=Path, help="train_labels.jsonl")
    parser.add_argument("--fit-fraction", type=float, default=0.75)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not 0.1 <= args.fit_fraction <= 0.9:
        parser.error("--fit-fraction must be between 0.1 and 0.9")

    records = load_jsonl(args.predictions)
    labels = {item["doc_id"]: item["fields"] for item in load_jsonl(args.labels)}
    if {r["doc_id"] for r in records} != set(labels):
        parser.error("prediction and label doc_id sets do not match")

    random.Random(args.seed).shuffle(records)
    cut = int(len(records) * args.fit_fraction)
    print(f"split: fit_fraction={args.fit_fraction:.2f}, seed={args.seed}, "
          f"MIN_CHAR_CONF={pp.MIN_CHAR_CONF:.3f}")
    print_score("fit", score(records[:cut], labels))
    print_score("holdout", score(records[cut:], labels))
    print("Note: use the fit part to choose thresholds; do not tune on holdout results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
