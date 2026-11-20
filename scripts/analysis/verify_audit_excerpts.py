
import csv
import json
from pathlib import Path

results_path = Path("results/evidence_audit_v1.jsonl")
inputs_path = Path("data/model_inputs/evaluation_pilot_v1.csv")
output_path = Path("results/evidence_excerpt_verification_v1.csv")

if output_path.exists():
    raise SystemExit(
        f"Output already exists: {output_path}"
    )

with inputs_path.open(newline="", encoding="utf-8") as f:
    inputs = {
        row["response_id"]: row["answer"]
        for row in csv.DictReader(f)
    }

with results_path.open(encoding="utf-8") as f:
    records = [
        json.loads(line)
        for line in f if line.strip()
    ]

assert len(records) == 12
assert len(inputs) == 12

def normalize_outer_quotes(value):
    value = value.strip()

    quote_pairs = [
        ('"', '"'),
        ("'", "'"),
        ("“", "”"),
        ("‘", "’")
    ]

    for left, right in quote_pairs:
        if value.startswith(left) and value.endswith(right):
            return value[1:-1].strip()

    return value

verification = []

for record in records:
    response_id = record["response_id"]
    answer = inputs[response_id]

    for criterion in record["parsed_output"]["criteria"]:
        excerpt = criterion["supporting_excerpt"]

        if not excerpt:
            status = "EMPTY_EXCERPT"
        elif excerpt in answer:
            status = "EXACT_MATCH"
        elif normalize_outer_quotes(excerpt) in answer:
            status = "OUTER_QUOTES_ONLY"
        else:
            status = "UNVERIFIED_EXCERPT"

        verification.append({
            "response_id": response_id,
            "criterion_id": criterion["criterion_id"],
            "evidence_status": criterion["evidence_status"],
            "verification_status": status,
            "original_excerpt": excerpt
        })

assert len(verification) == 48

with output_path.open(
    "w", newline="", encoding="utf-8"
) as f:
    writer = csv.DictWriter(
        f,
        fieldnames=list(verification[0].keys())
    )
    writer.writeheader()
    writer.writerows(verification)

from collections import Counter

counts = Counter(
    row["verification_status"]
    for row in verification
)

print("\nESDSA — EVIDENCE EXCERPT VERIFICATION")
print("=" * 60)

for status, count in sorted(counts.items()):
    print(f"{status}: {count}")

print("\nTotal criterion records:", len(verification))
print("Output:", output_path)
print("Original audit results unchanged.")
