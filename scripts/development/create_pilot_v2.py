
import csv
from pathlib import Path

root = Path("data")

original = root / "model_inputs/pilot_responses.csv"
proposals = root / "reference/pilot_positive_final_proposals.csv"
output = root / "model_inputs/pilot_responses_v2.csv"

if output.exists():
    raise SystemExit(f"Output already exists: {output}")

with original.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    fields = list(reader.fieldnames)

with proposals.open(newline="", encoding="utf-8") as f:
    revisions = {
        row["response_id"]: row
        for row in csv.DictReader(f)
    }

assert len(rows) == 9, "Unexpected number of pilot responses."
assert len(revisions) == 3, "Expected three positive revisions."

for row in rows:
    response_id = row["response_id"]

    if response_id in revisions:
        proposal = revisions[response_id]

        if row["answer"] != proposal["original_answer"]:
            raise ValueError(
                f"Original response mismatch: {response_id}"
            )

        row["answer"] = proposal["final_proposed_answer"]

fields.append("benchmark_version")

for row in rows:
    row["benchmark_version"] = "pilot-v2"

with output.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print(f"Created: {output}")
print(f"Total responses: {len(rows)}")
print(f"Positive revisions applied: {len(revisions)}")
print("Original pilot preserved.")
print("Reference labels remain provisional.")
