
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

INPUT = Path("data/model_inputs/controlled_pairs_v1.csv")
PAIRS = Path(
    "data/reference/controlled_pairs_v1_reference.csv"
)
RESULTS = Path(
    "results/controlled_pairs_gpt-5.4-mini.jsonl"
)
OUTPUT = Path("results/decision_stability_v1.csv")


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_jsonl(path):
    with path.open(encoding="utf-8") as f:
        return [
            json.loads(line)
            for line in f if line.strip()
        ]


def sha256(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def main():
    if OUTPUT.exists():
        raise SystemExit(
            f"Output already exists: {OUTPUT}"
        )

    inputs = read_csv(INPUT)
    metadata = read_csv(PAIRS)
    results = read_jsonl(RESULTS)

    assert len(inputs) == 6
    assert len(metadata) == 6
    assert len(results) == 4

    input_map = {
        row["response_id"]: row
        for row in inputs
    }

    assert len(input_map) == 6

    metadata_ids = [
        row["response_id"] for row in metadata
    ]

    assert len(set(metadata_ids)) == 6
    assert set(metadata_ids) == set(input_map)

    predictions = {}
    model_versions = set()
    seen_hashes = set()

    for result in results:
        answer_hash = result["answer_sha256"]

        if answer_hash in seen_hashes:
            raise ValueError("Duplicate model evaluation")

        seen_hashes.add(answer_hash)
        model_versions.add(result["returned_model"])

        decision = result[
            "parsed_output"
        ]["recommendation"]

        for response_id in result["response_ids"]:
            if response_id in predictions:
                raise ValueError(
                    f"Duplicate response: {response_id}"
                )

            if response_id not in input_map:
                raise ValueError(
                    f"Unknown response: {response_id}"
                )

            actual_hash = sha256(
                input_map[response_id]["answer"]
            )

            if actual_hash != answer_hash:
                raise ValueError(
                    f"Answer fingerprint mismatch: {response_id}"
                )

            predictions[response_id] = decision

    assert len(model_versions) == 1
    assert len(predictions) == 6

    grouped = defaultdict(dict)

    for row in metadata:
        pair_id = row["pair_id"]
        variant = row["variant"]
        response_id = row["response_id"]

        if variant in grouped[pair_id]:
            raise ValueError("Duplicate pair variant")

        grouped[pair_id][variant] = {
            "response_id": response_id,
            "prediction": predictions[response_id],
            "reference": row["provisional_decision"]
        }

    specifications = {
        "A": {
            "variants": ("BASE", "STYLE"),
            "test_type": "SEMANTIC_STABILITY"
        },
        "B": {
            "variants": ("BASE", "REMOVED"),
            "test_type": "EVIDENCE_REMOVAL"
        },
        "C": {
            "variants": ("BASE", "CONTRADICTED"),
            "test_type": "CONTRADICTORY_EVIDENCE"
        }
    }

    assert set(grouped) == set(specifications)

    analysis = []

    for pair_id, spec in specifications.items():
        base_key, modified_key = spec["variants"]

        assert set(grouped[pair_id]) == {
            base_key, modified_key
        }

        base = grouped[pair_id][base_key]
        modified = grouped[pair_id][modified_key]

        changed = (
            base["prediction"] !=
            modified["prediction"]
        )

        expected = (
            base["prediction"] == base["reference"]
            and
            modified["prediction"] == modified["reference"]
        )

        if pair_id == "A":
            outcome = (
                "STABLE" if not changed else "UNSTABLE"
            )
        else:
            outcome = (
                "DECISION_CHANGED"
                if changed else "DECISION_UNCHANGED"
            )

        analysis.append({
            "pair_id": pair_id,
            "test_type": spec["test_type"],
            "baseline_decision": base["prediction"],
            "modified_decision": modified["prediction"],
            "decision_changed": changed,
            "outcome": outcome,
            "provisional_reference_match": expected,
            "semantic_validation": "NOT_INDEPENDENTLY_VALIDATED"
        })

    with OUTPUT.open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(analysis[0].keys())
        )
        writer.writeheader()
        writer.writerows(analysis)

    print("\nESDSA — DECISION STABILITY ANALYSIS")
    print("=" * 65)
    print("Model:", next(iter(model_versions)))
    print("Unique model evaluations:", len(results))
    print("Comparison pairs:", len(analysis))

    for row in analysis:
        print(f"\nComparison {row['pair_id']}")
        print("Type:", row["test_type"])
        print("Baseline:", row["baseline_decision"])
        print("Modified:", row["modified_decision"])
        print("Outcome:", row["outcome"])
        print(
            "Provisional reference match:",
            row["provisional_reference_match"]
        )

    print("\nSTABILITY TESTS: 1")
    print("EVIDENCE-CHANGE CONTROLS: 2")
    print("Independent semantic validation: PENDING")
    print("Saved:", OUTPUT)
    print("Original experiment results unchanged.")


if __name__ == "__main__":
    main()
