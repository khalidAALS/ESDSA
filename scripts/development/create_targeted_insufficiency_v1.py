
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path("data/benchmark")
SCENARIOS = ROOT / "development_scenarios_v1.csv"
INPUT = ROOT / "targeted_insufficiency_v1.csv"
DESIGN = ROOT / "targeted_insufficiency_design_v1.csv"

if INPUT.exists() or DESIGN.exists():
    raise SystemExit("Outputs exist. Nothing overwritten.")



CASES = {
    "CSS01": (
        3,
        "I'd ask what happened when the customer tried to "
        "access the account and which features have stopped "
        "working. I'd also ask how urgently those features "
        "are needed and whether other services are affected."
    ),
    "CSS02": (
        2,
        "I'd ask when the payment occurred and whether the "
        "customer received a transaction receipt. I'd use "
        "only approved internal records and wouldn't ask "
        "the customer for passwords or full card details."
    ),
    "CSS03": (
        2,
        "I'd compare the available refund options with the "
        "confirmed outage details. Since eligibility information "
        "is incomplete, I'd gather the missing details before "
        "deciding which resolution is appropriate."
    ),
    "CSS04": (
        3,
        "I'd explain that a specialist needs to investigate "
        "the issue and describe what information will be "
        "passed to them. Since the completion time is unknown, "
        "I wouldn't promise a particular resolution date."
    ),
    "OPS01": (
        3,
        "I'd prioritise the urgent customer delivery because "
        "of its deadline and impact, then arrange maintenance "
        "so it doesn't disrupt the delivery. I'd use the "
        "remaining capacity for the routine inventory review."
    ),
    "OPS02": (
        3,
        "I'd identify the risk of the delayed shipment interrupting "
        "normal operations. I'd compare stock coverage with "
        "expected demand and consider how higher-than-forecast "
        "volumes could affect the time available."
    ),
    "OPS03": (
        3,
        "I'd compare the warehouse and carrier records, then "
        "contact the responsible people on both sides to "
        "clarify whether collection happened. I'd coordinate "
        "the teams involved in the next handoff."
    ),
    "OPS04": (
        3,
        "I'd track the unfinished task against the milestone "
        "plan, ask the responsible team for its latest estimate "
        "and check whether the remaining time is enough. "
        "I'd identify when the delay threatens the deadline."
    ),
    "SWE01": (
        3,
        "I'd reproduce the incorrect dashboard totals using "
        "the affected records and user accounts. I'd compare "
        "those results against unaffected users to establish "
        "which inputs and circumstances differ."
    ),
    "SWE02": (
        3,
        "I'd examine server logs, request timings, deployment "
        "history and database metrics. I'd compare slow and "
        "fast requests and test whether the slowdown changes "
        "with different endpoints or database loads."
    ),
    "SWE03": (
        3,
        "I'd investigate whether retries cause repeated "
        "order creation. If that was confirmed, I'd correct "
        "the responsible order-creation logic to handle "
        "repeated requests."
    ),
    "SWE04": (
        2,
        "I'd rerun the invoice scenario that originally failed "
        "to check whether the correction works. If the result "
        "was still wrong, I'd hold the release and investigate "
        "the failed verification before proceeding."
    )
}

with SCENARIOS.open(newline="", encoding="utf-8") as f:
    scenarios = list(csv.DictReader(f))

assert len(scenarios) == 12
assert {r["competency_code"] for r in scenarios} == set(CASES)

inputs = []
design = []

for row in scenarios:
    code = row["competency_code"]
    missing_number, answer = CASES[code]
    response_id = f"{row['family_id']}-TARGET-01"

    rubric_path = (
        ROOT / "rubrics_v1" /
        f"{code}_rubric_v1.json"
    )

    rubric = json.loads(
        rubric_path.read_text(encoding="utf-8")
    )
    target_id = f"{code}-C{missing_number}"

    if target_id not in {
        c["id"] for c in rubric["criteria"]
    }:
        raise ValueError(f"Invalid indicator: {target_id}")

    inputs.append({
        "response_id": response_id,
        "family_id": row["family_id"],
        "role_code": row["role_code"],
        "competency_code": code,
        "question": row["interview_question"],
        "answer": answer,
        "rubric_id": row["rubric_id"]
    })

    design.append({
        "response_id": response_id,
        "target_missing_indicator": target_id,
        "intended_condition": "INSUFFICIENT",
        "partition": "DEVELOPMENT",
        "answer_sha256": hashlib.sha256(
            answer.encode("utf-8")
        ).hexdigest(),
        "evidence_validation": "PENDING",
        "expert_review": "PENDING"
    })


def save(path, records):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(records[0].keys())
        )
        writer.writeheader()
        writer.writerows(records)


save(INPUT, inputs)
save(DESIGN, design)

print("\nESDSA — TARGETED INSUFFICIENCY V1")
print("=" * 60)
print("New development responses:", len(inputs))
print("Competencies:", len(CASES))

for item in design:
    print(
        item["response_id"],
        "| intended missing:",
        item["target_missing_indicator"]
    )

print("\nModel-facing inputs:", INPUT)
print("Private design metadata:", DESIGN)
print("Evidence validation: PENDING")
print("API calls: NONE")
print("Original 108-response benchmark: UNCHANGED")
