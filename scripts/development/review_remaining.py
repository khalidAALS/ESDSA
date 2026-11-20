
import csv
from pathlib import Path

root = Path("data")

responses_path = root / "model_inputs/pilot_responses_v2.csv"
reference_path = root / "reference/pilot_reference.csv"
output_path = root / "reference/pilot_remaining_review.csv"

if output_path.exists():
    raise SystemExit(f"File already exists: {output_path}")

with responses_path.open(newline="", encoding="utf-8") as f:
    responses = list(csv.DictReader(f))

with reference_path.open(newline="", encoding="utf-8") as f:
    references = {
        row["response_id"]: row
        for row in csv.DictReader(f)
    }

criteria = ["C1", "C2", "C3", "C4"]

proposed_status = {
    "negative": {
        "C1": "NEGATIVE_EVIDENCE",
        "C2": "NEGATIVE_EVIDENCE",
        "C3": "NEGATIVE_EVIDENCE",
        "C4": "NEGATIVE_EVIDENCE"
    },
    "insufficient": {
        "C1": "INSUFFICIENT_EVIDENCE",
        "C2": "INSUFFICIENT_EVIDENCE",
        "C3": "INSUFFICIENT_EVIDENCE",
        "C4": "INSUFFICIENT_EVIDENCE"
    }
}

records = []

for response in responses:
    ref = references[response["response_id"]]
    condition = ref["evidence_condition"]

    if condition not in proposed_status:
        continue

    for criterion in criteria:
        records.append({
            "response_id": response["response_id"],
            "criterion_id": criterion,
            "evidence_condition": condition,
            "proposed_status": proposed_status[condition][criterion],
            "supporting_excerpt": "",
            "reviewer_notes": "",
            "validation_status": "PENDING_REVIEW"
        })

assert len(records) == 24, (
    f"Expected 24 review records; found {len(records)}"
)

with output_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=list(records[0].keys())
    )
    writer.writeheader()
    writer.writerows(records)

print(f"Created: {output_path}")
print(f"Review records: {len(records)}")
print("All judgments remain provisional.")
print("Original benchmark unchanged.")
