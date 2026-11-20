

"""Revise two conceptually overlapping validation scenarios.

Creates a versioned validation draft. Original files untouched.
No API calls or candidate response generation.
"""

# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data" / "benchmark"

SOURCE = BASE / "validation_scenarios_v1.csv"
OUTPUT = BASE / "validation_scenarios_v2.csv"
REPORT = BASE / "validation_scenarios_revision_v2.json"

REVISIONS = {
    "ESDSA-SWE01-10": (
        "A previous investigation into missing records in a "
        "scheduled data export led to a software change, but "
        "the problem has returned for a different set of records. "
        "The original reproduction steps no longer expose the "
        "failure, and the team is uncertain whether the same "
        "defect is responsible. You have access to the earlier "
        "findings, export logs, sample records and a test "
        "environment. How would you approach diagnosing the "
        "problem now?"
    ),
    "ESDSA-OPS01-05": (
        "An operations team has limited staff available for "
        "three competing activities: inspecting a recently "
        "delivered batch of materials before production, "
        "preparing an important customer order for dispatch, "
        "and completing scheduled staff training. The inspection "
        "may reveal a quality issue, while delaying dispatch "
        "could affect an agreed customer deadline. How would "
        "you determine priorities and respond if new "
        "information changes the situation?"
    ),
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError(
            "Version 2 output already exists. "
            "No file will be overwritten."
        )

    with SOURCE.open(
        encoding="utf-8-sig", newline=""
    ) as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        rows = list(reader)

    if len(rows) != 24:
        raise ValueError("Expected 24 validation scenarios")

    ids = [r["family_id"] for r in rows]

    if len(set(ids)) != 24:
        raise ValueError("Duplicate family IDs")

    if not set(REVISIONS).issubset(ids):
        raise ValueError("One or more revision IDs are missing")

    changes = []

    for row in rows:
        family_id = row["family_id"]

        if row["partition"] != "VALIDATION":
            raise ValueError(
                f"Non-validation family found: {family_id}"
            )

        if family_id in REVISIONS:
            old_question = row["interview_question"]
            new_question = REVISIONS[family_id]

            if old_question == new_question:
                raise ValueError(
                    f"Question was not changed: {family_id}"
                )

            row["interview_question"] = new_question

            changes.append({
                "family_id": family_id,
                "reason": (
                    "Reduce conceptual overlap with an "
                    "existing development scenario"
                ),
                "previous_question": old_question,
                "revised_question": new_question,
            })

    if len(changes) != 2:
        raise ValueError("Exactly two revisions required")

    with OUTPUT.open(
        "w", encoding="utf-8", newline=""
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=columns
        )
        writer.writeheader()
        writer.writerows(rows)

    report = {
        "version": "validation-scenarios-v2",
        "source_sha256": sha256(SOURCE),
        "output_sha256": sha256(OUTPUT),
        "total_validation_families": len(rows),
        "revised_families": changes,
        "unchanged_family_count": 22,
        "status": "READY_FOR_FINAL_SCENARIO_CHECK",
        "candidate_responses_generated": False,
        "test_data_modified": False,
        "model_api_calls": 0,
        "notes": [
            "Scenario revisions occurred before validation "
            "response generation and evaluation.",
            "Textual and conceptual non-overlap are distinct.",
            "The original v1 draft is preserved.",
            "No reference labels were generated or changed.",
        ],
    }

    REPORT.write_text(
        json.dumps(
            report, indent=2, ensure_ascii=False
        ),
        encoding="utf-8",
    )

    print("ESDSA VALIDATION SCENARIO REVISION")
    print("=" * 60)
    print("Total validation scenarios:", len(rows))
    print("Revised scenarios:", len(changes))
    print("Unchanged scenarios: 22")
    print("Candidate responses generated: NO")
    print("Test data modified: NO")
    print("API calls: NONE")

    for change in changes:
        print("\n" + change["family_id"])
        print(change["revised_question"])

    print("\nSaved:", OUTPUT)
    print("Saved:", REPORT)


if __name__ == "__main__":
    main()
