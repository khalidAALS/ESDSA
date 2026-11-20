
import csv
from pathlib import Path

output = Path("data/reference/pilot_challenge_proposals.csv")

if output.exists():
    raise SystemExit(f"File already exists: {output}")

cases = [
    {
        "case_id": "CHALLENGE-A",
        "case_type": "PARTIAL_EVIDENCE",
        "answer": (
            "I'd reproduce the problem, compare affected and unaffected "
            "cases, and examine the logs and recent changes to identify "
            "the cause. Once I'd found the faulty logic, I'd correct it."
        ),
        "expected_decision": "DEFER",
        "rationale": (
            "Diagnosis and correction are supported, but verification "
            "evidence is missing."
        )
    },
    {
        "case_id": "CHALLENGE-B",
        "case_type": "MIXED_EVIDENCE",
        "answer": (
            "I'd reproduce the error, compare the affected cases and "
            "inspect the logs to identify the cause. I'd correct the "
            "responsible code, but I wouldn't run additional tests "
            "before releasing because the fix should be straightforward."
        ),
        "expected_decision": "DO_NOT_ADVANCE",
        "rationale": (
            "Provides diagnostic evidence but explicitly rejects "
            "verification before release."
        )
    },
    {
        "case_id": "CHALLENGE-C",
        "case_type": "CONCISE_COMPLETE",
        "answer": (
            "I'd reproduce the issue, compare failing and working cases, "
            "and inspect the logs to isolate the cause. Then I'd correct "
            "the responsible code, rerun a test covering the failure, "
            "and check for regressions."
        ),
        "expected_decision": "ADVANCE",
        "rationale": (
            "Concise response containing evidence for all four criteria."
        )
    }
]

output.parent.mkdir(parents=True, exist_ok=True)

with output.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=list(cases[0].keys())
    )
    writer.writeheader()
    writer.writerows(cases)

print(f"Created: {output}")
print(f"Challenge cases: {len(cases)}")
print("Reference decisions are PROVISIONAL.")
print("Existing benchmark unchanged.")
