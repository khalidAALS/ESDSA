
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path("data/benchmark")
REGISTRY = ROOT / "scenario_registry_v1.csv"
RUBRIC_DIR = ROOT / "rubrics_v1"
MANIFEST = RUBRIC_DIR / "rubric_manifest.json"
OUTPUT = ROOT / "development_scenarios_v1.csv"

if OUTPUT.exists():
    raise SystemExit(
        f"Output already exists: {OUTPUT}. "
        "Nothing overwritten."
    )

SCENARIOS = {
    "SWE01": (
        "After a software release, some users report that "
        "a dashboard displays different totals for the same "
        "records. Other users report no problem. You have "
        "access to a test environment and a record of recent "
        "changes. How would you approach identifying the defect?"
    ),
    "SWE02": (
        "An application becomes intermittently slow after "
        "an update. Available information includes server "
        "logs, request timings, deployment records and "
        "database metrics. Several potential causes have "
        "been suggested. How would you investigate?"
    ),
    "SWE03": (
        "An online ordering system occasionally creates "
        "duplicate orders. Initial investigation suggests "
        "that retry requests may interact with order-creation "
        "logic. Explain how you would decide what to correct "
        "and why that correction would address the problem."
    ),
    "SWE04": (
        "A defect causing incorrect invoice totals has "
        "been corrected in a development environment. "
        "The change affects code shared with several "
        "other billing functions. What would you do "
        "before deciding whether the correction is ready?"
    ),
    "CSS01": (
        "A customer contacts support saying that their "
        "account is broken and that they need urgent help. "
        "They provide no further details. How would you "
        "establish what has happened and what matters most?"
    ),
    "CSS02": (
        "A customer reports that a payment was taken twice, "
        "but the customer-facing account page shows only "
        "one transaction. You can consult approved internal "
        "payment records. How would you gather and assess "
        "the information needed to investigate?"
    ),
    "CSS03": (
        "A customer requests an immediate refund for a "
        "service interruption. The account history confirms "
        "an outage, but eligibility information is incomplete "
        "and an exception may require approval. How would "
        "you determine the appropriate next action?"
    ),
    "CSS04": (
        "A customer's technical issue requires specialist "
        "investigation and cannot be resolved during the "
        "initial conversation. The estimated completion "
        "time is uncertain. How would you communicate "
        "with the customer and manage follow-up?"
    ),
    "OPS01": (
        "You are coordinating three activities: a routine "
        "inventory review, an urgent delivery affecting a "
        "major customer, and scheduled maintenance that "
        "could disrupt the delivery process. Resources "
        "are limited. How would you determine priorities?"
    ),
    "OPS02": (
        "A critical supplier reports that an upcoming "
        "shipment may be delayed. Current stock could "
        "support normal operations for a short period, "
        "but demand forecasts are uncertain. How would "
        "you assess and respond to the operational risk?"
    ),
    "OPS03": (
        "A delivery schedule shows that an important "
        "shipment is ready, but the warehouse and carrier "
        "records disagree about whether it has been "
        "collected. Several teams need an updated plan. "
        "How would you coordinate the next steps?"
    ),
    "OPS04": (
        "A project is approaching a critical milestone. "
        "One dependent task is incomplete, and the "
        "responsible team has not confirmed when it "
        "will finish. How would you monitor the situation "
        "and decide whether escalation is necessary?"
    )
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


with REGISTRY.open(newline="", encoding="utf-8") as f:
    registry = list(csv.DictReader(f))

manifest = json.loads(
    MANIFEST.read_text(encoding="utf-8")
)

if manifest["registry_sha256"] != sha256(REGISTRY):
    raise ValueError("Registry fingerprint mismatch")

rubric_entries = {
    entry["competency_code"]: entry
    for entry in manifest["rubrics"]
}

if len(rubric_entries) != 12:
    raise ValueError("Expected 12 rubric entries")

if set(rubric_entries) != set(SCENARIOS):
    raise ValueError("Rubric/scenario competency mismatch")

by_competency = defaultdict(list)

for row in registry:
    if row["partition"] == "DEVELOPMENT":
        by_competency[row["competency_code"]].append(row)

selected = []

for code in sorted(SCENARIOS):
    candidates = sorted(
        by_competency[code],
        key=lambda r: r["family_id"]
    )

    if len(candidates) != 6:
        raise ValueError(
            f"Expected 6 development families for {code}"
        )

    family = candidates[0]
    entry = rubric_entries[code]
    rubric_path = RUBRIC_DIR / entry["file"]

    if sha256(rubric_path) != entry["sha256"]:
        raise ValueError(
            f"Rubric fingerprint mismatch: {code}"
        )

    rubric = json.loads(
        rubric_path.read_text(encoding="utf-8")
    )

    if rubric["competency_code"] != code:
        raise ValueError(
            f"Rubric competency mismatch: {code}"
        )

    if len(rubric["criteria"]) != 3:
        raise ValueError(
            f"Expected three criteria: {code}"
        )

    criterion_ids = [
        c["id"] for c in rubric["criteria"]
    ]

    if len(set(criterion_ids)) != 3:
        raise ValueError(
            f"Duplicate criterion IDs: {code}"
        )

    selected.append({
        "family_id": family["family_id"],
        "role_code": family["role_code"],
        "role_name": family["role_name"],
        "competency_code": code,
        "competency_name": family["competency_name"],
        "scenario_profile": family["scenario_profile"],
        "partition": "DEVELOPMENT",
        "interview_question": SCENARIOS[code],
        "rubric_id": rubric["rubric_id"],
        "rubric_file": entry["file"],
        "draft_status": "RESEARCHER_AUTHORED",
        "expert_review": "PENDING",
        "reference_validation": "PENDING",
        "candidate_responses_generated": "NO"
    })

assert len(selected) == 12
assert len({r["family_id"] for r in selected}) == 12


assert len({r["role_code"] for r in selected}) == 3
assert len({r["competency_code"] for r in selected}) == 12

with OUTPUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f, fieldnames=list(selected[0].keys())
    )
    writer.writeheader()
    writer.writerows(selected)

print("\nESDSA — DEVELOPMENT SCENARIOS V1")
print("=" * 60)
print("Rubric files validated:", len(rubric_entries))
print("Scenario families prepared:", len(selected))
print("Occupational roles:", 3)
print("Competencies covered:", 12)
print("Partition: DEVELOPMENT ONLY")

for row in selected:
    print(
        f"{row['family_id']} | "
        f"{row['competency_name']}"
    )

print("\nOutput:", OUTPUT)
print("SHA256:", sha256(OUTPUT))
print("Candidate responses: NOT GENERATED")
print("Expert review: PENDING")
print("API calls: NONE")
print("Held-out test families: UNCHANGED")
print("Original experimental files unchanged.")
