

"""Paired exploratory comparison of ESDSA development baselines.

Uses existing predictions and provisional annotations only.
Does not make API calls or change source files.
"""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("data/benchmark")
RESULTS = Path("results")

REF = (
    ROOT / "researcher_annotations_v1"
    / "development_reference_provisional_v1.csv"
)
MAPPING = ROOT / "content_review_v1/private_review_mapping.json"

SCORING = RESULTS / "scoring_baseline_108_v1.jsonl"
EVIDENCE = RESULTS / "benchmark_evidence_aware_v1.jsonl"

OUTPUT = RESULTS / "baseline_comparison_108_v1.json"

DECISIONS = {"ADVANCE", "DEFER", "DO_NOT_ADVANCE"}


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


def index_by_id(records):
    indexed = {}

    for record in records:
        rid = record["response_id"]

        if rid in indexed:
            raise ValueError(f"Duplicate response ID: {rid}")

        indexed[rid] = record

    return indexed


def metrics(items, field):
    total = len(items)

    counts = Counter(r[field] for r in items)

    actionable = [
        r for r in items
        if r[field] != "DEFER"
    ]

    unsupported_advances = sum(
        r[field] == "ADVANCE"
        and r["reference"] != "ADVANCE"
        for r in items
    )

    actionable_disagreements = sum(
        r[field] != "DEFER"
        and r[field] != r["reference"]
        for r in items
    )

    unnecessary_deferrals = sum(
        r[field] == "DEFER"
        and r["reference"] != "DEFER"
        for r in items
    )

    matches = sum(
        r[field] == r["reference"]
        for r in items
    )

    return {
        "total": total,
        "decisions": dict(counts),
        "decision_agreement": matches / total if total else None,
        "actionable_count": len(actionable),
        "actionable_coverage": (
            len(actionable) / total if total else None
        ),
        "actionable_disagreement_count": actionable_disagreements,
        "actionable_disagreement_rate": (
            actionable_disagreements / len(actionable)
            if actionable else None
        ),
        "advances_without_reference_support": unsupported_advances,
        "deferrals_when_reference_actionable": unnecessary_deferrals,
    }


for path in (REF, MAPPING, SCORING, EVIDENCE):
    if not path.is_file():
        raise SystemExit(f"Missing file: {path}")

if OUTPUT.exists():
    raise SystemExit(
        f"Output exists: {OUTPUT}. Nothing overwritten."
    )

references = load_csv(REF)

mapping = json.loads(
    MAPPING.read_text(encoding="utf-8")
)["groups"]

scoring = index_by_id(load_jsonl(SCORING))
evidence = index_by_id(load_jsonl(EVIDENCE))

if (
    len(references) != 108
    or len(scoring) != 108
    or len(evidence) != 108
):
    raise SystemExit("Expected 108 records per dataset.")


combined = []

for row in references:
    group = row["review_group"]
    letter = row["response_label"]

    rid = mapping[group]["responses"][letter]["response_id"]

    if rid not in scoring or rid not in evidence:
        raise SystemExit(f"Missing prediction: {rid}")

    a = scoring[rid]
    b = evidence[rid]

    if (
        a.get("rubric_id") != b.get("rubric_id")
        or a.get("answer_sha256") != b.get("answer_sha256")
    ):
        raise SystemExit(f"Input/rubric mismatch: {rid}")

    sd = a["decision"]
    ed = b["decision"]
    rd = row["reference_decision"]

    if not {sd, ed, rd}.issubset(DECISIONS):
        raise SystemExit(f"Unexpected decision: {rid}")

    combined.append({
        "response_id": rid,
        "group": group,
        "letter": letter,
        "competency": row["competency"],
        "reference": rd,
        "scoring": sd,
        "evidence": ed,
        "scoring_mean": a["mean_score"],
        "scoring_scores": a["scores"],
        "criterion_reference": [
            row[f"C{i}"] for i in (1, 2, 3)
        ],
        "criterion_evidence": [
            c["evidence_status"]
            for c in b["parsed_output"]["criteria"]
        ],
        "review_flag": row["review_flag"],
        "semantic_equivalence": row["semantic_equivalence"],
    })


all_metrics = {
    "scoring_only": metrics(combined, "scoring"),
    "evidence_aware": metrics(combined, "evidence"),
}

unflagged = [
    r for r in combined
    if r["review_flag"] == "NO"
]

flagged = [
    r for r in combined
    if r["review_flag"] == "YES"
]

subset_metrics = {
    "unflagged": {
        "scoring_only": metrics(unflagged, "scoring"),
        "evidence_aware": metrics(unflagged, "evidence"),
    },
    "flagged": {
        "scoring_only": metrics(flagged, "scoring"),
        "evidence_aware": metrics(flagged, "evidence"),
    },
}

method_disagreement = [
    r for r in combined
    if r["scoring"] != r["evidence"]
]

paired_comparison = Counter()

for r in combined:
    scoring_matches = r["scoring"] == r["reference"]
    evidence_matches = r["evidence"] == r["reference"]

    if scoring_matches and evidence_matches:
        paired_comparison["both_match"] += 1
    elif scoring_matches:
        paired_comparison["scoring_only_matches"] += 1
    elif evidence_matches:
        paired_comparison["evidence_only_matches"] += 1
    else:
        paired_comparison["neither_matches"] += 1


groups = defaultdict(list)

for r in combined:
    groups[r["group"]].append(r)

stability = {}

for method in ("scoring", "evidence"):
    eligible = []
    stable = []
    unstable = []

    for group, items in sorted(groups.items()):
        if len(items) != 3:
            raise SystemExit(f"Invalid group size: {group}")
        if (
            items[0]["semantic_equivalence"] != "YES"
            or len({x["reference"] for x in items}) != 1
        ):
            continue

        eligible.append(group)

        if len({x[method] for x in items}) == 1:
            stable.append(group)
        else:
            unstable.append({
                "group": group,
                "decisions": {
                    x["letter"]: x[method]
                    for x in items
                },
            })

    stability[method] = {
        "eligible_groups": len(eligible),
        "stable_groups": len(stable),
        "unstable_groups": unstable,
        "stable_fraction": (
            len(stable) / len(eligible)
            if eligible else None
        ),
    }


report = {
    "design": "Paired 108-response development comparison",
    "reference_status": (
        "AI-assisted provisional annotations; "
        "not independently validated"
    ),
    "important_limitations": [
        "Raw actionable coverage differs between methods.",
        "Reference agreement does not establish true accuracy.",
        "Sixteen groups are flagged for adjudication.",
        "Semantic equivalence is provisional.",
        "This is a development-set analysis, not held-out testing.",
        "Matched-coverage comparison has not yet been performed.",
    ],
    "overall": all_metrics,
    "subsets": subset_metrics,
    "paired_reference_agreement": dict(paired_comparison),
    "method_decision_disagreements": len(method_disagreement),
    "linguistic_stability": stability,
    "per_response": combined,
}

OUTPUT.write_text(
    json.dumps(
        report, indent=2, ensure_ascii=False
    ) + "\n",
    encoding="utf-8",
)


print("ESDSA — PAIRED BASELINE COMPARISON")
print("=" * 65)

for name, result in all_metrics.items():
    print("\nMETHOD:", name.upper())

    print("Decision counts:", result["decisions"])

    print(
        "Actionable coverage:",
        f"{result['actionable_count']}/108",
        f"({result['actionable_coverage']:.1%})"
    )

    print(
        "Provisional reference agreement:",
        f"{result['decision_agreement']:.1%}"
    )

    print(
        "Actionable disagreement rate:",
        f"{result['actionable_disagreement_rate']:.1%}"
    )

    print(
        "Advances without reference support:",
        result["advances_without_reference_support"]
    )

    print(
        "Deferrals when reference is actionable:",
        result["deferrals_when_reference_actionable"]
    )


print("\nPAIRED REFERENCE AGREEMENT")
print(dict(paired_comparison))

print(
    "\nMethods disagree on:",
    len(method_disagreement),
    "of 108 responses"
)

print("\nUNFLAGGED SUBSET (PROVISIONAL)")
for name, result in subset_metrics["unflagged"].items():
    print(
        name,
        "| n =", result["total"],
        "| agreement =",
        f"{result['decision_agreement']:.1%}",
        "| coverage =",
        f"{result['actionable_coverage']:.1%}"
    )


print("\nLINGUISTIC STABILITY")
for name, result in stability.items():
    print(
        name,
        "| eligible groups:", result["eligible_groups"],
        "| stable:", result["stable_groups"],
        "| unstable:", len(result["unstable_groups"])
    )

    for item in result["unstable_groups"]:
        print(" ", item["group"], item["decisions"])


print("\nReport:", OUTPUT)
print("No API calls made.")
print("Original predictions and annotations unchanged.")
print("This is exploratory, not a matched-coverage comparison.")
