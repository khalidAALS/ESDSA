
import csv
import json
from pathlib import Path
from collections import Counter

results_path = Path("results/pilot_gpt-5.4-mini.jsonl")
reference_path = Path(
    "data/reference/evaluation_pilot_v1_reference.csv"
)

with results_path.open(encoding="utf-8") as f:
    results = [json.loads(line) for line in f if line.strip()]

with reference_path.open(newline="", encoding="utf-8") as f:
    references = {
        row["response_id"]: row
        for row in csv.DictReader(f)
    }

ids = [r["response_id"] for r in results]

assert len(results) == 12, "Expected 12 evaluations."
assert len(set(ids)) == 12, "Duplicate evaluation IDs."
assert set(ids) == set(references), "Reference mismatch."

agreements = 0
disagreements = []
recommendations = Counter()
warnings = 0

print("\nESDSA — DEVELOPMENT PILOT ANALYSIS")
print("=" * 75)

for record in sorted(results, key=lambda x: x["response_id"]):
    response_id = record["response_id"]
    prediction = record["parsed_output"]["recommendation"]
    reference = references[response_id]["reference_decision"]
    case_type = references[response_id]["case_type"]

    match = prediction == reference

    agreements += int(match)
    recommendations[prediction] += 1
    warnings += len(record.get("validation_warnings", []))

    if not match:
        disagreements.append(response_id)

    print(
        f"{response_id} | "
        f"Reference: {reference:<14} | "
        f"Prediction: {prediction:<14} | "
        f"{'MATCH' if match else 'DISAGREEMENT'}"
    )

print("\nSUMMARY")
print("=" * 75)
print(f"Total evaluations: {len(results)}")
print(f"Reference agreements: {agreements}/12")
print(f"Agreement percentage: {agreements / 12 * 100:.1f}%")
print(f"Disagreements: {len(disagreements)}")
print(f"Recommendation distribution: {dict(recommendations)}")
print(f"Recorded excerpt warnings: {warnings}")

legacy = sum(
    "validation_warnings" not in r
    for r in results
)
print(f"Records without warning field: {legacy}")

print("\nREFERENCE VALIDATION: PROVISIONAL")
print("This is development-set agreement, not validated accuracy.")
print("No files modified.")
