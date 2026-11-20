
import json
from collections import Counter
from pathlib import Path

path = Path("results/evidence_audit_v1.jsonl")

with path.open(encoding="utf-8") as f:
    records = [
        json.loads(line)
        for line in f if line.strip()
    ]

assert len(records) == 12, "Expected 12 audit records."

flagged = 0
total_warnings = 0
statuses = Counter()

for record in records:
    warnings = record.get("validation_warnings", [])

    if not warnings:
        continue

    flagged += 1
    total_warnings += len(warnings)

    criteria = {
        item["criterion_id"]: item
        for item in record["parsed_output"]["criteria"]
    }

    print("\n" + "=" * 75)
    print("RESPONSE:", record["response_id"])
    print("ORIGINAL:", record["original_recommendation"])
    print("AUDITED:", record["audited_recommendation"])

    for warning in warnings:
        criterion_id = warning["criterion_id"]
        item = criteria[criterion_id]

        statuses[item["evidence_status"]] += 1

        print("\nCRITERION:", criterion_id)
        print("STATUS:", item["evidence_status"])
        print("ISSUE:", warning["issue"])
        print("EXCERPT:", repr(item["supporting_excerpt"]))
        print("EXPLANATION:", item["explanation"])

print("\n" + "=" * 75)
print("AUDIT WARNING SUMMARY")
print("Flagged responses:", flagged)
print("Total warnings:", total_warnings)
print("Statuses involved:", dict(statuses))
print("No files modified.")

