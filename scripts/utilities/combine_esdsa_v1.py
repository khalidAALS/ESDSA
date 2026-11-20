
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path("results")

EVALUATIONS = ROOT / "controlled_pairs_gpt-5.4-mini.jsonl"
AUDITS = ROOT / "controlled_evidence_audit_v1.jsonl"
COMPARISONS = ROOT / "decision_stability_v1.csv"
MAPPING = Path(
    "data/reference/controlled_pairs_v1_reference.csv"
)
OUTPUT = ROOT / "combined_esdsa_v1.json"


def read_jsonl(path):
    with path.open(encoding="utf-8") as f:
        return [
            json.loads(line)
            for line in f if line.strip()
        ]


def read_csv(path):
    with path.open(
        newline="", encoding="utf-8"
    ) as f:
        return list(csv.DictReader(f))


def expand_results(records, decision_field):
    expanded = {}

    for record in records:
        decision = (
            record["parsed_output"]["recommendation"]
            if decision_field == "evaluator"
            else record["evidence_supported_decision"]
        )

        for response_id in record["response_ids"]:
            if response_id in expanded:
                raise ValueError(
                    f"Duplicate response: {response_id}"
                )

            expanded[response_id] = decision

    return expanded


def main():
    evaluations = read_jsonl(EVALUATIONS)
    audits = read_jsonl(AUDITS)
    comparisons = read_csv(COMPARISONS)
    mapping = read_csv(MAPPING)

    assert len(evaluations) == 4
    assert len(audits) == 4
    assert len(comparisons) == 3

    original = expand_results(
        evaluations, "evaluator"
    )
    evidence = expand_results(
        audits, "audit"
    )

    if set(original) != set(evidence):
        raise ValueError("Evaluation/audit ID mismatch")

    if len(original) != 6:
        raise ValueError("Expected six response mappings")

    groups = defaultdict(dict)

    for row in mapping:
        groups[row["pair_id"]][row["variant"]] = (
            row["response_id"]
        )

    comparison_map = {
        row["pair_id"]: row
        for row in comparisons
    }

    if set(comparison_map) != {"A", "B", "C"}:
        raise ValueError("Unexpected comparison pairs")

    report = []

    for pair_id in ("A", "B", "C"):
        group = groups[pair_id]

        baseline_id = group["BASE"]

        modified_key = {
            "A": "STYLE",
            "B": "REMOVED",
            "C": "CONTRADICTED"
        }[pair_id]

        modified_id = group[modified_key]

        original_base = original[baseline_id]
        original_modified = original[modified_id]

        evidence_base = evidence[baseline_id]
        evidence_modified = evidence[modified_id]

        base_supported = (
            original_base == evidence_base
        )
        modified_supported = (
            original_modified == evidence_modified
        )

        if pair_id == "A":
            stability = (
                "STABLE"
                if original_base == original_modified
                else "UNSTABLE"
            )

            if (
                base_supported
                and modified_supported
                and stability == "STABLE"
            ):
                combined_decision = original_base
                verdict = "RETAIN"
            else:
                combined_decision = "DEFER"
                verdict = "DEFER_FOR_REVIEW"

            test_role = "SEMANTIC_STABILITY_PILOT"

        else:
            stability = "NOT_APPLICABLE"
            combined_decision = None
            verdict = "CONTROL_ONLY"
            test_role = "COMPETENCE_SENSITIVITY_CONTROL"

        report.append({
            "pair_id": pair_id,
            "test_role": test_role,
            "original_baseline": original_base,
            "original_modified": original_modified,
            "evidence_baseline": evidence_base,
            "evidence_modified": evidence_modified,
            "evidence_agreement_baseline": base_supported,
            "evidence_agreement_modified": modified_supported,
            "stability": stability,
            "combined_verdict": verdict,
            "combined_decision": combined_decision,
            "reference_validation": "PENDING"
        })

    result = {
        "experiment": "ESDSA combined development prototype",
        "version": "1.0",
        "status": "DEVELOPMENT_ONLY",
        "stability_pairs": 1,
        "evidence_change_controls": 2,
        "independent_semantic_validation": False,
        "cross_model_independence": False,
        "results": report
    }

    if OUTPUT.exists():
        raise SystemExit(
            f"Output exists: {OUTPUT}. No files overwritten."
        )

    OUTPUT.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8"
    )

    print("\nESDSA — COMBINED DEVELOPMENT ANALYSIS")
    print("=" * 65)

    for item in report:
        print(f"\nComparison {item['pair_id']}")
        print("Role:", item["test_role"])
        print(
            "Evidence agreement:",
            item["evidence_agreement_baseline"],
            item["evidence_agreement_modified"]
        )
        print("Stability:", item["stability"])
        print("Verdict:", item["combined_verdict"])
        print("Decision:", item["combined_decision"])

    print("\nSaved:", OUTPUT)
    print("Independent semantic validation: PENDING")
    print("No API calls made.")
    print("Existing experiment files unchanged.")


if __name__ == "__main__":
    main()
