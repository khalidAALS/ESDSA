
import csv
import json
from collections import Counter
from pathlib import Path

root = Path(".")

scoring_path = root / "results/scoring_baseline_v1.jsonl"
evidence_path = root / "results/pilot_gpt-5.4-mini.jsonl"
reference_path = root / "data/reference/evaluation_pilot_v1_reference.csv"


def load_jsonl(path):
    with path.open(encoding="utf-8") as f:
        records = [
            json.loads(line)
            for line in f if line.strip()
        ]

    ids = [r["response_id"] for r in records]

    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate response IDs in {path}")

    return {r["response_id"]: r for r in records}


def load_references(path):
    with path.open(newline="", encoding="utf-8") as f:
        records = list(csv.DictReader(f))

    ids = [r["response_id"] for r in records]

    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate reference IDs")

    return {r["response_id"]: r for r in records}


scoring = load_jsonl(scoring_path)
evidence = load_jsonl(evidence_path)
references = load_references(reference_path)

assert len(scoring) == len(evidence) == len(references) == 12
assert set(scoring) == set(evidence) == set(references)

scoring_agreement = 0
evidence_agreement = 0
different_decisions = 0
insufficient_cases = 0
insufficient_rejections = 0

print("\nESDSA — BASELINE COMPARISON")
print("=" * 85)

for response_id in sorted(references):
    reference = references[response_id]["reference_decision"]

    scoring_output = scoring[response_id]["parsed_output"]
    evidence_output = evidence[response_id]["parsed_output"]

    scoring_decision = scoring_output["recommendation"]
    evidence_decision = evidence_output["recommendation"]

    scores = [
        item["score"]
        for item in scoring_output["criteria"]
    ]

    scoring_agreement += int(scoring_decision == reference)
    evidence_agreement += int(evidence_decision == reference)
    different_decisions += int(
        scoring_decision != evidence_decision
    )

    if reference == "DEFER":
        insufficient_cases += 1
        insufficient_rejections += int(
            scoring_decision == "DO_NOT_ADVANCE"
        )

    print(f"\n{response_id}")
    print("Reference:     ", reference)
    print("Scoring:       ", scoring_decision)
    print("Evidence-aware:", evidence_decision)
    print("Scores:        ", scores)

print("\n" + "=" * 85)
print("SUMMARY")
print("=" * 85)

print("Total cases:", len(references))
print("Scoring/reference agreement:", scoring_agreement, "/12")
print("Evidence/reference agreement:", evidence_agreement, "/12")
print("Different recommendations:", different_decisions)
print("Reference DEFER cases:", insufficient_cases)
print("Scoring rejections in DEFER cases:", insufficient_rejections)

print("\nREFERENCE STATUS: PROVISIONAL")
print("Development comparison only.")
print("No files modified.")
