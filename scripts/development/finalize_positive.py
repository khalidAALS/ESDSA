
import csv
from pathlib import Path

source = Path("data/reference/pilot_positive_revision_proposals.csv")
output = Path("data/reference/pilot_positive_final_proposals.csv")

revisions = {
    "PILOT-SW-01-POSITIVE-V0": (
        "I would reproduce the error first, then compare affected "
        "and unaffected cases to narrow down the cause. I'd inspect "
        "logs and recent code changes to identify the faulty logic "
        "and correct the code responsible. I'd write a test that "
        "captures the original failure, check that the correction "
        "passes it, and run regression tests before releasing."
    ),
    "PILOT-SW-01-POSITIVE-V1": (
        "First I'd try to get the same error happening again. Then "
        "I'd compare affected users with those who aren't having "
        "the issue, check logs and recent changes, and work out "
        "which bit of logic caused it. I'd write a test for that "
        "failure, fix the responsible code, rerun the test, and "
        "check the other relevant tests before shipping."
    ),
    "PILOT-SW-01-POSITIVE-V2": (
        "I'd start by reproducing it. Compare affected and working "
        "cases, look through logs and recent changes to find where "
        "the logic goes wrong. Make a test showing the failure, "
        "fix the code causing it, then rerun that test and check "
        "related regression tests before deployment."
    )
}

if output.exists():
    raise SystemExit(f"File already exists: {output}")

with source.open(newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

assert {r["response_id"] for r in rows} == set(revisions)

with output.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "response_id",
            "original_answer",
            "final_proposed_answer",
            "validation_status"
        ]
    )
    writer.writeheader()

    for row in rows:
        writer.writerow({
            "response_id": row["response_id"],
            "original_answer": row["original_answer"],
            "final_proposed_answer": revisions[row["response_id"]],
            "validation_status": "PENDING_REVIEW"
        })

print(f"Created: {output}")
print(f"Final proposals: {len(rows)}")
print("All proposals remain pending review.")
print("Original benchmark and references unchanged.")
