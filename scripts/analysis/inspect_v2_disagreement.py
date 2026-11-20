
import csv
import json
from pathlib import Path

ROOT = Path(".")

INPUT = ROOT / "data/model_inputs/challenge_benchmark_v2.csv"
SCORING = ROOT / "results/scoring_baseline_v2.jsonl"
AUDIT = ROOT / "results/evidence_audit_v2.jsonl"

TARGETS = ["ESDSA-V2-0006", "ESDSA-V2-0007"]


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return {
            row["response_id"]: row
            for row in csv.DictReader(f)
        }


def read_jsonl(path):
    with path.open(encoding="utf-8") as f:
        records = [
            json.loads(line)
            for line in f if line.strip()
        ]

    ids = [r["response_id"] for r in records]

    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate result IDs")

    return {r["response_id"]: r for r in records}


inputs = read_csv(INPUT)
scoring = read_jsonl(SCORING)
audits = read_jsonl(AUDIT)

for response_id in TARGETS:
    response = inputs[response_id]
    score = scoring[response_id]["parsed_output"]
    audit = audits[response_id]

    print("\n" + "=" * 78)
    print("RESPONSE:", response_id)
    print("=" * 78)

    print("\nCANDIDATE ANSWER:")
    print(response["answer"])

    print("\nSCORING-ONLY ASSESSMENT:")

    for item in score["criteria"]:
        print(
            f"{item['criterion_id']} | "
            f"Score: {item['score']} | "
            f"{item['reason']}"
        )

    print("\nSCORING RECOMMENDATION:")
    print(score["recommendation"])

    print("\nINDEPENDENT EVIDENCE AUDIT:")

    for item in audit["parsed_output"]["criteria"]:
        print(f"\n{item['criterion_id']}")
        print("Status:", item["evidence_status"])
        print("Excerpt:", repr(item["supporting_excerpt"]))
        print("Explanation:", item["explanation"])

    print("\nAUDIT VERDICT:")
    print(audit["audit_verdict"])
    print("Evidence supports:", audit["evidence_supported_decision"])
    print("Audited outcome:", audit["audited_recommendation"])

    print("\nEXCERPT WARNINGS:")

    warnings = audit.get("validation_warnings", [])

    if not warnings:
        print("None")
    else:
        for warning in warnings:
            print(warning)

print("\nInspection complete. No files modified.")
