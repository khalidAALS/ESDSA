
"""Exploratory matched-coverage sensitivity analysis for ESDSA."""

import json
import random
from pathlib import Path
from statistics import mean

SOURCE = Path("results/baseline_comparison_108_v1.json")
OUTPUT = Path("results/matched_coverage_sensitivity_v1.json")

SEED = 20261119
REPETITIONS = 10000

if not SOURCE.is_file():
    raise SystemExit(f"Missing input: {SOURCE}")

if OUTPUT.exists():
    raise SystemExit(f"Output exists: {OUTPUT}; nothing overwritten.")

report = json.loads(SOURCE.read_text(encoding="utf-8"))
rows = report["per_response"]

if len(rows) != 108:
    raise SystemExit("Expected 108 paired responses.")

scoring = [r for r in rows if r["scoring"] != "DEFER"]
evidence = [r for r in rows if r["evidence"] != "DEFER"]

target = len(scoring)

if target != 79 or len(evidence) != 105:
    raise SystemExit(
        f"Unexpected coverage: scoring={target}, "
        f"evidence={len(evidence)}"
    )

def count_disagreements(items, method):
    return sum(r[method] != r["reference"] for r in items)

def count_unsupported_advances(items, method):
    return sum(
        r[method] == "ADVANCE"
        and r["reference"] != "ADVANCE"
        for r in items
    )

def percentile(values, fraction):
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]

scoring_errors = count_disagreements(scoring, "scoring")
scoring_unsupported = count_unsupported_advances(scoring, "scoring")

rng = random.Random(SEED)
sample_errors = []
sample_unsupported = []

for _ in range(REPETITIONS):
    sample = rng.sample(evidence, target)
    sample_errors.append(
        count_disagreements(sample, "evidence")
    )
    sample_unsupported.append(
        count_unsupported_advances(sample, "evidence")
    )

# Same-response comparison: both methods make a decision.
common = [
    r for r in rows
    if r["scoring"] != "DEFER"
    and r["evidence"] != "DEFER"
]

common_results = {
    "count": len(common),
    "scoring_disagreements": count_disagreements(
        common, "scoring"
    ),
    "evidence_disagreements": count_disagreements(
        common, "evidence"
    ),
    "scoring_unsupported_advances": count_unsupported_advances(
        common, "scoring"
    ),
    "evidence_unsupported_advances": count_unsupported_advances(
        common, "evidence"
    ),
}

result = {
    "analysis": "EXPLORATORY_MATCHED_COVERAGE_SENSITIVITY",
    "seed": SEED,
    "repetitions": REPETITIONS,
    "total_responses": len(rows),
    "matched_actionable_count": target,
    "scoring": {
        "disagreements": scoring_errors,
        "disagreement_rate": scoring_errors / target,
        "unsupported_advances": scoring_unsupported,
    },
    "evidence_random_deferral": {
        "mean_disagreements": mean(sample_errors),
        "mean_disagreement_rate": mean(sample_errors) / target,
        "disagreements_2_5_percentile": percentile(
            sample_errors, 0.025
        ),
        "disagreements_97_5_percentile": percentile(
            sample_errors, 0.975
        ),
        "mean_unsupported_advances": mean(sample_unsupported),
        "unsupported_advances_2_5_percentile": percentile(
            sample_unsupported, 0.025
        ),
        "unsupported_advances_97_5_percentile": percentile(
            sample_unsupported, 0.975
        ),
        "fraction_samples_better_than_scoring": sum(
            n < scoring_errors for n in sample_errors
        ) / REPETITIONS,
        "fraction_samples_equal_to_scoring": sum(
            n == scoring_errors for n in sample_errors
        ) / REPETITIONS,
    },
    "common_actionable_subset": common_results,
    "limitations": [
        "Reference classifications are AI-assisted and provisional.",
        "Random deferral is not an operational selective prediction policy.",
        "Random-sampling percentiles are not independent statistical confidence intervals.",
        "Experiments use development data, not held-out evaluation.",
        "Observed reference disagreement is not validated real-world error.",
        "This analysis does not establish ESDSA superiority."
    ],
}

OUTPUT.write_text(
    json.dumps(result, indent=2) + "\n",
    encoding="utf-8"
)

print("ESDSA — MATCHED-COVERAGE SENSITIVITY")
print("=" * 60)
print("Total responses:", len(rows))
print("Matched actionable decisions:", target)
print("Random samples:", REPETITIONS)

print("\nSCORING-ONLY")
print("Disagreements:", scoring_errors)
print(f"Disagreement rate: {scoring_errors / target:.1%}")
print("Unsupported advances:", scoring_unsupported)

print("\nEVIDENCE-AWARE WITH RANDOM DEFERRAL")
print(f"Mean disagreements: {mean(sample_errors):.2f}")
print(f"Mean disagreement rate: {mean(sample_errors) / target:.1%}")
print(
    "95% simulation range (disagreement counts):",
    percentile(sample_errors, 0.025),
    "to",
    percentile(sample_errors, 0.975)
)
print(
    "Mean unsupported advances:",
    f"{mean(sample_unsupported):.2f}"
)
print(
    "Samples with fewer disagreements than scoring:",
    f"{result['evidence_random_deferral']['fraction_samples_better_than_scoring']:.1%}"
)

print("\nBOTH METHODS ACTIONABLE ON SAME RESPONSES")
print("Responses:", common_results["count"])
print("Scoring disagreements:", common_results["scoring_disagreements"])
print("Evidence disagreements:", common_results["evidence_disagreements"])

print("\nSaved:", OUTPUT)
print("No API calls or original-file modifications.")
