
import csv
from collections import defaultdict
from pathlib import Path

inputs_path = Path(
    "data/model_inputs/controlled_pairs_v1.csv"
)
references_path = Path(
    "data/reference/controlled_pairs_v1_reference.csv"
)

def read_csv(path):
    with path.open(
        newline="", encoding="utf-8"
    ) as f:
        return list(csv.DictReader(f))

inputs = read_csv(inputs_path)
references = read_csv(references_path)

assert len(inputs) == 6
assert len(references) == 6

input_map = {
    row["response_id"]: row
    for row in inputs
}

assert len(input_map) == 6
assert len({
    row["response_id"] for row in references
}) == 6

groups = defaultdict(list)

for ref in references:
    response_id = ref["response_id"]
    assert response_id in input_map

    groups[ref["pair_id"]].append({
        **ref,
        "answer": input_map[response_id]["answer"]
    })

assert set(groups) == {"A", "B", "C"}
assert all(len(group) == 2 for group in groups.values())

expected_variants = {
    "A": {"BASE", "STYLE"},
    "B": {"BASE", "REMOVED"},
    "C": {"BASE", "CONTRADICTED"}
}

for pair_id in sorted(groups):
    group = groups[pair_id]

    actual_variants = {
        row["variant"] for row in group
    }

    assert actual_variants == expected_variants[pair_id]

    print("\n" + "=" * 75)
    print(f"COMPARISON {pair_id}")
    print("=" * 75)

    for row in sorted(
        group, key=lambda x: x["variant"]
    ):
        print(f"\nVariant: {row['variant']}")
        print("Response ID:", row["response_id"])
        print("Answer:", row["answer"])
        print("Reference:", row["provisional_decision"])
        print("Validation:", row["validation_status"])

# Confirm that all three pairs reuse the same
# original response text.
base_answers = [
    row["answer"]
    for group in groups.values()
    for row in group
    if row["variant"] == "BASE"
]

assert len(base_answers) == 3
assert len(set(base_answers)) == 1

print("\n" + "=" * 75)
print("STRUCTURAL VALIDATION: PASS")
print("Comparison pairs: 3")
print("Response records: 6")
print("Unique baseline answers: 1")
print("Independent semantic validation: NOT PERFORMED")
print("No files modified.")
