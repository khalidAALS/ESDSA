
import csv
from pathlib import Path

root = Path("data")

source = root / "model_inputs/pilot_responses_v2.csv"
output = root / "model_inputs/pilot_blinded_v2.csv"
mapping = root / "reference/pilot_blinding_map_v2.csv"

if output.exists() or mapping.exists():
    raise SystemExit(
        "Blinded output or mapping already exists. "
        "Existing files have not been overwritten."
    )

with source.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

assert len(rows) == 9, "Expected nine pilot responses."

assert len({r["response_id"] for r in rows}) == len(rows), (
    "Duplicate source response IDs detected."
)

import random
rng = random.Random(20261119)
rng.shuffle(rows)

blinded_rows = []
mapping_rows = []

for index, row in enumerate(rows, start=1):
    blinded_id = f"ESDSA-PILOT-{index:03d}"

    blinded_rows.append({
        "response_id": blinded_id,
        "question": row["question"],
        "answer": row["answer"],
        "rubric_id": row["rubric_id"]
    })

    mapping_rows.append({
        "blinded_id": blinded_id,
        "original_response_id": row["response_id"],
        "scenario_id": row["scenario_id"],
        "benchmark_version": "pilot-v2"
    })

output.parent.mkdir(parents=True, exist_ok=True)
mapping.parent.mkdir(parents=True, exist_ok=True)

with output.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "response_id",
            "question",
            "answer",
            "rubric_id"
        ]
    )
    writer.writeheader()
    writer.writerows(blinded_rows)

with mapping.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "blinded_id",
            "original_response_id",
            "scenario_id",
            "benchmark_version"
        ]
    )
    writer.writeheader()
    writer.writerows(mapping_rows)

print(f"Blinded benchmark: {output}")
print(f"Reference mapping: {mapping}")
print(f"Total responses: {len(blinded_rows)}")
print("Original benchmark unchanged.")
print("No evidence-condition labels in blinded identifiers.")
