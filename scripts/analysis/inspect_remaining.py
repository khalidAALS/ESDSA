
import csv
from pathlib import Path

root = Path("data")

with (
    root / "model_inputs/pilot_responses_v2.csv"
).open(newline="", encoding="utf-8") as f:
    responses = {
        row["response_id"]: row
        for row in csv.DictReader(f)
    }

with (
    root / "reference/pilot_remaining_review.csv"
).open(newline="", encoding="utf-8") as f:
    annotations = list(csv.DictReader(f))

assert len(annotations) == 24

valid_statuses = {
    "NEGATIVE_EVIDENCE",
    "INSUFFICIENT_EVIDENCE"
}

for annotation in annotations:
    response_id = annotation["response_id"]

    assert response_id in responses
    assert annotation["proposed_status"] in valid_statuses

    print("\n" + "=" * 70)
    print("RESPONSE:", response_id)
    print("CRITERION:", annotation["criterion_id"])
    print("PROPOSED:", annotation["proposed_status"])
    print("ANSWER:", responses[response_id]["answer"])
    print("SUPPORTING EXCERPT: NOT YET ANNOTATED")

print("\nAll 24 records passed structural checks.")
print("Substantive evidence review remains pending.")
