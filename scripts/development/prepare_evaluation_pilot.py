
import csv
import json
import random
from pathlib import Path

root = Path("data")
model_dir = root / "model_inputs"
reference_dir = root / "reference"

blinded_path = model_dir / "pilot_blinded_v2.csv"
mapping_path = reference_dir / "pilot_blinding_map_v2.csv"
reference_path = reference_dir / "pilot_reference.csv"
challenge_path = reference_dir / "pilot_challenge_proposals.csv"
rubric_path = root / "rubrics/SW-DEFECT-V1.json"

output_inputs = model_dir / "evaluation_pilot_v1.csv"
output_references = reference_dir / "evaluation_pilot_v1_reference.csv"

if output_inputs.exists() or output_references.exists():
    raise SystemExit("Output already exists. No files overwritten.")

def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

blinded = read_csv(blinded_path)
mapping = read_csv(mapping_path)
references = read_csv(reference_path)
challenges = read_csv(challenge_path)

rubric = json.loads(rubric_path.read_text(encoding="utf-8"))

assert len(blinded) == 9
assert len(mapping) == 9
assert len(references) == 9
assert len(challenges) == 3
assert rubric["rubric_id"] == "SW-DEFECT-V1"

id_map = {
    r["blinded_id"]: r["original_response_id"]
    for r in mapping
}

ref_map = {
    r["response_id"]: r
    for r in references
}

question = blinded[0]["question"]

assert all(r["question"] == question for r in blinded)

combined = []

for row in blinded:
    original_id = id_map[row["response_id"]]
    ref = ref_map[original_id]

    combined.append({
        "source_id": original_id,
        "question": row["question"],
        "answer": row["answer"],
        "rubric_id": row["rubric_id"],
        "reference_decision": ref["reference_decision"],
        "case_type": ref["evidence_condition"]
    })

for row in challenges:
    combined.append({
        "source_id": row["case_id"],
        "question": question,
        "answer": row["answer"],
        "rubric_id": rubric["rubric_id"],
        "reference_decision": row["expected_decision"],
        "case_type": row["case_type"]
    })

rng = random.Random(20261119)
rng.shuffle(combined)

inputs = []
local_references = []

for index, row in enumerate(combined, start=1):
    neutral_id = f"ESDSA-EVAL-{index:04d}"

    inputs.append({
        "response_id": neutral_id,
        "question": row["question"],
        "answer": row["answer"],
        "rubric_id": row["rubric_id"]
    })

    local_references.append({
        "response_id": neutral_id,
        "source_id": row["source_id"],
        "reference_decision": row["reference_decision"],
        "case_type": row["case_type"],
        "validation_status": "PROVISIONAL"
    })

def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

write_csv(output_inputs, inputs)
write_csv(output_references, local_references)

assert len(inputs) == len(local_references) == 12
assert len({r["response_id"] for r in inputs}) == 12

print(f"Model-facing dataset: {output_inputs}")
print(f"Local reference file: {output_references}")
print(f"Total responses: {len(inputs)}")
print("Neutral identifiers: YES")
print("Reference labels excluded from model inputs: YES")
print("Reference validation: PROVISIONAL")
print("No model evaluations performed.")
