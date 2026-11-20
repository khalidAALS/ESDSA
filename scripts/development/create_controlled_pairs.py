
import csv
import json
import random
from pathlib import Path

root = Path("data")
inputs_path = root / "model_inputs/controlled_pairs_v1.csv"
reference_path = root / "reference/controlled_pairs_v1_reference.csv"
rubric_path = root / "rubrics/SW-DEFECT-V1.json"

if inputs_path.exists() or reference_path.exists():
    raise SystemExit("Output exists. No files overwritten.")

rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
assert rubric["rubric_id"] == "SW-DEFECT-V1"

question = (
    "A software update causes an application to return "
    "incorrect results for some users. Explain how you "
    "would investigate the problem and determine whether "
    "your proposed correction works."
)

base = (
    "I'd reproduce the issue, compare failing and working "
    "cases, and inspect logs and recent changes to identify "
    "the faulty logic. I'd correct the responsible code, "
    "run a test reproducing the original failure, and "
    "check related regression tests before deployment."
)

style_variant = (
    "First I'd get the error happening again. I'd look at "
    "the cases that fail alongside those that work, then "
    "check logs and recent changes to find the faulty logic. "
    "After fixing that code, I'd run a test covering the "
    "original failure and check the related regression tests "
    "before releasing it."
)

missing_verification = (
    "I'd reproduce the issue, compare failing and working "
    "cases, and inspect logs and recent changes to identify "
    "the faulty logic. I'd correct the responsible code."
)

contradictory_verification = (
    "I'd reproduce the issue, compare failing and working "
    "cases, and inspect logs and recent changes to identify "
    "the faulty logic. I'd correct the responsible code, "
    "but skip testing before deployment because the fix "
    "looks straightforward."
)

cases = [
    ("A", "BASE", base, "ADVANCE"),
    ("A", "STYLE", style_variant, "ADVANCE"),
    ("B", "BASE", base, "ADVANCE"),
    ("B", "REMOVED", missing_verification, "DEFER"),
    ("C", "BASE", base, "ADVANCE"),
    ("C", "CONTRADICTED",
     contradictory_verification, "DO_NOT_ADVANCE"),
]

rng = random.Random(20261119)
rng.shuffle(cases)

inputs = []
references = []

for index, (pair, variant, answer, decision) in enumerate(
    cases, start=1
):
    response_id = f"ESDSA-CTRL-{index:03d}"

    inputs.append({
        "response_id": response_id,
        "question": question,
        "answer": answer,
        "rubric_id": "SW-DEFECT-V1"
    })

    references.append({
        "response_id": response_id,
        "pair_id": pair,
        "variant": variant,
        "provisional_decision": decision,
        "validation_status": "UNREVIEWED"
    })

def save_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(rows)

save_csv(inputs_path, inputs)
save_csv(reference_path, references)

assert len(inputs) == 6
assert len({x["response_id"] for x in inputs}) == 6

print("Controlled comparison benchmark created.")
print("Model inputs:", inputs_path)
print("Local references:", reference_path)
print("Response records:", len(inputs))
print("Comparison pairs: 3")
print("Reference status: UNREVIEWED")
print("Existing pilot preserved.")

