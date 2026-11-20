

"""Compare provisional ESDSA references with existing evaluator outputs."""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("data/benchmark")
REF = ROOT / "researcher_annotations_v1/development_reference_provisional_v1.csv"
MAPPING = ROOT / "content_review_v1/private_review_mapping.json"
EVALUATIONS = Path("results/benchmark_evidence_aware_v1.jsonl")
OUTPUT = Path("results/development_reference_comparison_v1.json")

def load_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def load_jsonl(path):
    with path.open(encoding="utf-8") as f:
        return [
            json.loads(line)
            for line in f
            if line.strip()
        ]

for path in (REF, MAPPING, EVALUATIONS):
    if not path.is_file():
        raise SystemExit(f"Missing input: {path}")

if OUTPUT.exists():
    raise SystemExit(
        f"Output already exists: {OUTPUT}\n"
        "Nothing overwritten."
    )

references = load_csv(REF)
mapping = json.loads(MAPPING.read_text(encoding="utf-8"))["groups"]
evaluations = load_jsonl(EVALUATIONS)

model_by_id = {
    r["response_id"]: r
    for r in evaluations
}

if len(references) != 108 or len(model_by_id) != 108:
    raise SystemExit("Expected 108 reference and model records.")

results = []
confusion = Counter()
criterion_confusion = Counter()

for row in references:
    group = row["review_group"]
    letter = row["response_label"]

    response_id = mapping[group]["responses"][letter]["response_id"]
    model = model_by_id[response_id]

    ref_criteria = [row[f"C{i}"] for i in range(1, 4)]
    model_criteria = [
        c["evidence_status"]
        for c in model["parsed_output"]["criteria"]
    ]

    if len(model_criteria) != 3:
        raise SystemExit(f"Unexpected criteria: {response_id}")

    reference_decision = row["reference_decision"]
    model_decision = model["decision"]

    confusion[(reference_decision, model_decision)] += 1

    differences = []

    for i, (reference_status, model_status) in enumerate(
        zip(ref_criteria, model_criteria), start=1
    ):
        criterion_confusion[(reference_status, model_status)] += 1

        if reference_status != model_status:
            differences.append({
                "criterion": i,
                "reference": reference_status,
                "model": model_status,
            })

    results.append({
        "group": group,
        "letter": letter,
        "response_id": response_id,
        "competency": row["competency"],
        "reference_decision": reference_decision,
        "model_decision": model_decision,
        "decision_agrees": reference_decision == model_decision,
        "criterion_differences": differences,
        "review_flag": row["review_flag"],
        "semantic_equivalence": row["semantic_equivalence"],
    })

decision_matches = sum(r["decision_agrees"] for r in results)
criterion_mismatches = sum(
    len(r["criterion_differences"]) for r in results
)

group_results = defaultdict(list)
for row in results:
    group_results[row["group"]].append(row)

unstable = []
for group, items in sorted(group_results.items()):
    model_decisions = {r["model_decision"] for r in items}

    if len(model_decisions) > 1:
        unstable.append({
            "group": group,
            "semantic_equivalence": items[0]["semantic_equivalence"],
            "model_decisions": {
                r["letter"]: r["model_decision"] for r in items
            },
            "reference_decisions": {
                r["letter"]: r["reference_decision"] for r in items
            },
        })

disagreements = [
    r for r in results if not r["decision_agrees"]
]

report = {
    "status": "EXPLORATORY_PROVISIONAL_COMPARISON",
    "warning": (
        "Reference labels are AI-assisted and not independently "
        "adjudicated. Agreement is not validated accuracy."
    ),
    "responses": len(results),
    "criterion_comparisons": len(results) * 3,
    "decision_matches": decision_matches,
    "decision_agreement": decision_matches / len(results),
    "criterion_matches": len(results) * 3 - criterion_mismatches,
    "criterion_agreement": (
        (len(results) * 3 - criterion_mismatches)
        / (len(results) * 3)
    ),
    "decision_confusion": [
        {"reference": a, "model": b, "count": n}
        for (a, b), n in sorted(confusion.items())
    ],
    "criterion_confusion": [
        {"reference": a, "model": b, "count": n}
        for (a, b), n in sorted(criterion_confusion.items())
    ],
    "decision_disagreements": disagreements,
    "unstable_groups": unstable,
}

OUTPUT.write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8"
)

print("ESDSA — DEVELOPMENT REFERENCE COMPARISON")
print("=" * 62)

print(
    f"Decision agreement: {decision_matches}/108 "
    f"({100 * report['decision_agreement']:.1f}%)"
)

print(
    f"Criterion agreement: "
    f"{report['criterion_matches']}/324 "
    f"({100 * report['criterion_agreement']:.1f}%)"
)

print("\nDECISION CONFUSION")
for (reference, model), count in sorted(confusion.items()):
    print(f"  {reference:16} -> {model:16}: {count}")

print("\nDECISION DISAGREEMENTS")
for r in disagreements:
    print(
        f"  {r['group']} {r['letter']}: "
        f"{r['reference_decision']} -> {r['model_decision']}"
        f" | Flagged: {r['review_flag']}"
    )

print("\nMODEL-UNSTABLE GROUPS")
for r in unstable:
    print(
        f"  {r['group']}: "
        f"equivalence={r['semantic_equivalence']}, "
        f"decisions={r['model_decisions']}"
    )

print("\nReport:", OUTPUT)
print("No API calls made.")
print("No annotations or model predictions modified.")
print("These are provisional agreement statistics, not accuracy.")
