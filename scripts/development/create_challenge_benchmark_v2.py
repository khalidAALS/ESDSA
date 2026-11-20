
import csv
import json
import random
from pathlib import Path

ROOT = Path("data")
INPUT = ROOT / "model_inputs/challenge_benchmark_v2.csv"
REFERENCE = ROOT / "reference/challenge_benchmark_v2_reference.csv"
RUBRIC = ROOT / "rubrics/SW-DEFECT-V1.json"

if INPUT.exists() or REFERENCE.exists():
    raise SystemExit("Output exists; no files overwritten.")

rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
assert rubric["rubric_id"] == "SW-DEFECT-V1"

families = [
    {
        "family": "F01",
        "question": (
            "A software update has introduced intermittent incorrect "
            "calculations for some users. Explain how you would "
            "identify the cause, correct it, and verify the result."
        ),
        "responses": {
            "BASE": (
                "I'd reproduce the calculation error using affected "
                "inputs, compare them with working cases, and inspect "
                "recent changes and logs. Once I've isolated the "
                "faulty calculation, I'd correct it, test the affected "
                "inputs again, and run regression tests."
            ),
            "STYLE": (
                "First I'd try the inputs that gave wrong numbers and "
                "compare them with ones that worked. Then I'd go "
                "through the logs and recent changes to find the "
                "calculation that's causing it. I'd fix that logic, "
                "check the failing inputs again, and run the related "
                "regression tests."
            ),
            "PARTIAL": (
                "I'd reproduce the issue with affected inputs, "
                "compare them with working cases and inspect the "
                "recent changes to isolate the faulty calculation. "
                "I'd then correct that logic."
            ),
            "CONTRADICTED": (
                "I'd reproduce the issue, compare affected inputs "
                "and inspect recent changes to identify the faulty "
                "calculation. I'd fix it and deploy immediately, "
                "without testing the correction, because the change "
                "would be small."
            )
        }
    },
    {
        "family": "F02",
        "question": (
            "Following a release, users report that saved changes "
            "sometimes disappear. Explain how you would investigate "
            "the defect, implement a correction, and verify it."
        ),
        "responses": {
            "BASE": (
                "I'd reproduce the lost-update behaviour and compare "
                "successful and failed saves. I'd inspect application "
                "logs and recent persistence changes to locate the "
                "fault, correct the responsible logic, then test "
                "failed-save scenarios and run regression tests."
            ),
            "STYLE": (
                "I'd start by getting the lost-save problem to happen "
                "again and looking at saves that worked versus ones "
                "that didn't. I'd check the application logs and "
                "recent persistence changes to track down the bad "
                "logic. After fixing it, I'd retest the failing saves "
                "and check the related regression tests."
            ),
            "PARTIAL": (
                "I'd reproduce the missing changes and compare "
                "successful and unsuccessful saves. I'd check logs "
                "and recent persistence changes, find the faulty "
                "logic and correct it."
            ),
            "CONTRADICTED": (
                "I'd reproduce the missing changes, compare working "
                "and failing saves, and inspect logs and recent "
                "persistence changes. Once I'd found the faulty "
                "logic, I'd fix it but avoid testing before release, "
                "since the cause would already be known."
            )
        }
    }
]

expected = {
    "BASE": "ADVANCE",
    "STYLE": "ADVANCE",
    "PARTIAL": "DEFER",
    "CONTRADICTED": "DO_NOT_ADVANCE"
}

records = []

for family in families:
    for variant, answer in family["responses"].items():
        records.append({
            "family": family["family"],
            "variant": variant,
            "question": family["question"],
            "answer": answer,
            "reference": expected[variant]
        })

rng = random.Random(20261119)
rng.shuffle(records)

model_inputs = []
local_references = []

for index, item in enumerate(records, start=1):
    response_id = f"ESDSA-V2-{index:04d}"

    model_inputs.append({
        "response_id": response_id,
        "question": item["question"],
        "answer": item["answer"],
        "rubric_id": rubric["rubric_id"]
    })

    local_references.append({
        "response_id": response_id,
        "family_id": item["family"],
        "variant": item["variant"],
        "provisional_decision": item["reference"],
        "semantic_validation": "PENDING",
        "reference_validation": "PENDING",
        "dataset_partition": "DEVELOPMENT"
    })

def write_csv(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(records[0].keys())
        )
        writer.writeheader()
        writer.writerows(records)

assert len(model_inputs) == 8
assert len({r["response_id"] for r in model_inputs}) == 8

write_csv(INPUT, model_inputs)
write_csv(REFERENCE, local_references)

print("ESDSA — CHALLENGE BENCHMARK V2")
print("Independent scenario families:", len(families))
print("Total responses:", len(model_inputs))
print("Meaning-preserving pairs:", len(families))
print("Evidence-change controls:", len(families) * 2)
print("Reference labels: PROVISIONAL")
print("Semantic validation: PENDING")
print("Model-facing inputs:", INPUT)
print("Local references:", REFERENCE)
print("Existing experiments unchanged.")
