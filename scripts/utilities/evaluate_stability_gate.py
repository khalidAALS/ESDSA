
import json
from collections import Counter, defaultdict
from pathlib import Path

INPUT = Path("results/audit_repeatability_f02_v1.jsonl")
OUTPUT = Path("results/stability_gate_development_v1.json")

if OUTPUT.exists():
    raise SystemExit("Output exists; nothing overwritten.")

with INPUT.open(encoding="utf-8") as f:
    records = [
        json.loads(line)
        for line in f if line.strip()
    ]

groups = defaultdict(dict)

for record in records:
    response_id = record["response_id"]
    repetition = record["repetition"]

    if repetition in groups[response_id]:
        raise ValueError("Duplicate repetition")

    groups[response_id][repetition] = (
        record["evidence_supported_decision"]
    )

expected_ids = {
    "ESDSA-V2-0006",
    "ESDSA-V2-0007"
}

assert set(groups) == expected_ids
assert len(records) == 20

for group in groups.values():
    assert set(group) == set(range(1, 11))

sample_sizes = [1, 3, 5, 10]
report = []

print("ESDSA — STABILITY GATE DEVELOPMENT TEST")
print("=" * 65)

for k in sample_sizes:
    retained = 0
    deferred_by_gate = 0

    print(f"\nAssessments per response: {k}")

    for response_id in sorted(groups):
        decisions = [
            groups[response_id][i]
            for i in range(1, k + 1)
        ]

        counts = Counter(decisions)

        if len(counts) == 1:
            verdict = "RETAIN"
            decision = decisions[0]
            retained += 1
        else:
            verdict = "STABILITY_FAILURE"
            decision = "DEFER"
            deferred_by_gate += 1

        report.append({
            "response_id": response_id,
            "assessments": k,
            "observed_decisions": dict(counts),
            "gate_verdict": verdict,
            "final_decision": decision,
            "reference_correctness": "NOT_ESTABLISHED"
        })

        print(
            f"{response_id}: {dict(counts)} "
            f"→ {verdict} → {decision}"
        )

    print(
        f"Retained decisions: {retained}/2"
    )
    print(
        f"Stability-triggered deferrals: "
        f"{deferred_by_gate}/2"
    )

result = {
    "experiment": "Stability gate development v1",
    "status": "EXPLORATORY",
    "policy": (
        "Retain a decision only when all k "
        "assessments agree; otherwise DEFER."
    ),
    "sample_sizes": sample_sizes,
    "sampling_method": (
        "First k saved repetition indices. "
        "Not a prospective independent trial."
    ),
    "correctness_established": False,
    "independent_semantic_validation": False,
    "results": report,
    "limitations": [
        "Two responses from one scenario family",
        "No independently verified reference judgments",
        "Repeated calls may be dependent",
        "Policy evaluated retrospectively",
        "Additional assessments incur extra cost",
        "Deferral does not establish improved accuracy",
        "This is not a matched-coverage comparison"
    ]
}

OUTPUT.write_text(
    json.dumps(result, indent=2),
    encoding="utf-8"
)

print("\nSaved:", OUTPUT)
print("No API calls made.")
print("Original experiment outputs unchanged.")


if __name__ == "__main__":
    pass
