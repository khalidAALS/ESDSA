
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

ROOT = Path("data")

INPUT = ROOT / "model_inputs/challenge_benchmark_v2.csv"
REFERENCE = ROOT / "reference/challenge_benchmark_v2_reference.csv"


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


inputs = read_csv(INPUT)
references = read_csv(REFERENCE)

assert len(inputs) == 8
assert len(references) == 8

input_ids = [row["response_id"] for row in inputs]
reference_ids = [row["response_id"] for row in references]

assert len(set(input_ids)) == 8
assert len(set(reference_ids)) == 8
assert set(input_ids) == set(reference_ids)

input_map = {
    row["response_id"]: row
    for row in inputs
}

families = defaultdict(dict)

for ref in references:
    family = ref["family_id"]
    variant = ref["variant"]

    assert variant not in families[family]

    families[family][variant] = {
        **ref,
        "question": input_map[ref["response_id"]]["question"],
        "answer": input_map[ref["response_id"]]["answer"]
    }

expected_variants = {
    "BASE",
    "STYLE",
    "PARTIAL",
    "CONTRADICTED"
}

expected_decisions = {
    "BASE": "ADVANCE",
    "STYLE": "ADVANCE",
    "PARTIAL": "DEFER",
    "CONTRADICTED": "DO_NOT_ADVANCE"
}

assert set(families) == {"F01", "F02"}

for family_id, group in sorted(families.items()):
    assert set(group) == expected_variants

    questions = {row["question"] for row in group.values()}
    assert len(questions) == 1

    answers = {row["answer"] for row in group.values()}
    assert len(answers) == 4

    print("\n" + "=" * 70)
    print("SCENARIO FAMILY:", family_id)
    print("=" * 70)

    for variant in (
        "BASE", "STYLE", "PARTIAL", "CONTRADICTED"
    ):
        record = group[variant]

        assert (
            record["provisional_decision"]
            == expected_decisions[variant]
        )

        assert record["dataset_partition"] == "DEVELOPMENT"

        assert record["semantic_validation"] == "PENDING"
        assert record["reference_validation"] == "PENDING"

        print(f"\n{variant}")
        print("ID:", record["response_id"])
        print("Answer:", record["answer"])
        print("Expected:", record["provisional_decision"])

print("\n" + "=" * 70)
print("STRUCTURAL VALIDATION: PASS")
print("Scenario families:", len(families))
print("Total responses:", len(inputs))
print("Unique answers:", len({r["answer"] for r in inputs}))
print("Input SHA256:", sha256(INPUT))
print("Reference SHA256:", sha256(REFERENCE))
print("Semantic equivalence: NOT INDEPENDENTLY VALIDATED")
print("Reference judgments: PROVISIONAL")
print("No files modified.")
