
import csv
from pathlib import Path

source = Path("data/model_inputs/pilot_responses.csv")
output = Path("data/reference/pilot_positive_revision_proposals.csv")

revisions = {
    "PILOT-SW-01-POSITIVE-V0": (
        "I would reproduce the error first, compare affected and unaffected "
        "cases, and inspect logs and recent changes to identify the faulty "
        "logic. I would correct the code responsible, write a test for the "
        "original failure, and run regression tests before releasing."
    ),
    "PILOT-SW-01-POSITIVE-V1": (
        "First I'd reproduce the issue, compare which users were affected, "
        "and check the logs and recent changes. Once I'd identified the "
        "faulty logic, I'd fix that part, test the original problem again, "
        "and run the relevant regression tests before shipping."
    ),
    "PILOT-SW-01-POSITIVE-V2": (
        "I'd start by reproducing it. Compare affected and working cases, "
        "look at logs and recent changes to find the faulty logic. "
        "Fix the code causing it, test the original issue again, "
        "and check related regression tests before deployment."
    )
}

if output.exists():
    raise SystemExit(f"File already exists: {output}")

with source.open(newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

with output.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["response_id", "original_answer", "proposed_answer"]
    )
    writer.writeheader()

    count = 0
    for row in rows:
        if row["response_id"] in revisions:
            writer.writerow({
                "response_id": row["response_id"],
                "original_answer": row["answer"],
                "proposed_answer": revisions[row["response_id"]]
            })
            count += 1

print(f"Created: {output}")
print(f"Proposed revisions: {count}")
print("Original benchmark unchanged.")
