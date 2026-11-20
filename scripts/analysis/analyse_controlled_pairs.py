
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

inputs_path = Path("data/model_inputs/controlled_pairs_v1.csv")
reference_path = Path(
    "data/reference/controlled_pairs_v1_reference.csv"
)
results_path = Path(
    "results/controlled_pairs_gpt-5.4-mini.jsonl"
)

def load_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

inputs = load_csv(inputs_path)
references = load_csv(reference_path)

with results_path.open(encoding="utf-8") as f:
    results = [
        json.loads(line)
        for line in f if line.strip()
    ]

assert len(inputs) == 6
assert len(references) == 6
assert len(results) == 4

predictions = {}

for record in results:
    recommendation = record["parsed_output"]["recommendation"]

    for response_id in record["response_ids"]:
        if response_id in predictions:
            raise ValueError("Duplicate response mapping")

        predictions[response_id] = recommendation

assert len(predictions) == 6

input_ids = {row["response_id"] for row in inputs}
assert set(predictions) == input_ids

groups = defaultdict(dict)

for ref in references:
    response_id = ref["response_id"]

    groups[ref["pair_id"]][ref["variant"]] = {
        "response_id": response_id,
        "prediction": predictions[response_id],
        "reference": ref["provisional_decision"]
    }

comparisons = {
    "A": ("BASE", "STYLE"),
    "B": ("BASE", "REMOVED"),
    "C": ("BASE", "CONTRADICTED")
}

print("\nESDSA — CONTROLLED PAIR ANALYSIS")
print("=" * 70)

expected_matches = 0

for pair_id, (base_key, variant_key) in comparisons.items():
    base = groups[pair_id][base_key]
    modified = groups[pair_id][variant_key]

    reference_match = (
        base["prediction"] == base["reference"]
        and modified["prediction"] == modified["reference"]
    )

    expected_matches += int(reference_match)

    print(f"\nComparison {pair_id}")
    print("Baseline:", base["prediction"])
    print("Modified:", modified["prediction"])
    print(
        "Reference agreement:",
        "YES" if reference_match else "NO"
    )

warnings = sum(
    len(record.get("validation_warnings", []))
    for record in results
)

print("\nSUMMARY")
print("=" * 70)
print("Unique model evaluations:", len(results))
print("Response mappings:", len(predictions))
print("Pairs matching expected outcomes:", expected_matches, "/3")
print("Evidence-excerpt warnings:", warnings)
print("Reference validation: UNREVIEWED")
print("No files modified.")
