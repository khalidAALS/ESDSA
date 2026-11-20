

"""Consolidate ESDSA provisional annotations without changing source files."""

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path("data/benchmark")
FOLDER = ROOT / "researcher_annotations_v1"

FIRST = FOLDER / "batch01_criterion_annotations.csv"
FIRST_EQ = FOLDER / "batch01_semantic_equivalence.csv"
REMAINING = ROOT / "esdsa_remaining_groups_annotated_provisional.csv"

OUTPUT = FOLDER / "development_reference_provisional_v1.csv"
QC = FOLDER / "development_reference_qc_v1.json"

FLAGS = {
    "GROUP-004": "Approval authority versus generic referral; unresolved",
    "GROUP-009": "Diagnostic narrowing versus final cause; semantic equivalence",
    "GROUP-011": "Tentative inference versus unsupported assumption; semantic equivalence",
    "GROUP-013": "Code-first triage and missing diagnostic evidence",
    "GROUP-014": "Brief response may omit priority evidence",
    "GROUP-015": "Sensitive payment-data request and status taxonomy",
    "GROUP-016": "Unjustified completion promise and weak follow-up",
    "GROUP-017": "Avoiding cause verification versus missing evidence",
    "GROUP-018": "B may omit demand uncertainty and impact",
    "GROUP-023": "Escalation threshold and verification omitted",
    "GROUP-025": "Use of unreconciled carrier record",
    "GROUP-030": "Passive monitoring and failure to escalate",
    "GROUP-031": "Identifying owners/dependencies and explanation",
    "GROUP-032": "Risk awareness versus dismissal of uncertainty",
    "GROUP-035": "Assess impact versus execute regression tests",
    "GROUP-036": "Proposed mitigation without confirmed causal link",
}

ALLOWED = {
    "POSITIVE_EVIDENCE",
    "NEGATIVE_EVIDENCE",
    "INSUFFICIENT_EVIDENCE",
}


def load(path):
    if not path.is_file():
        raise SystemExit(f"Missing file: {path}")

    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def decision(statuses):
    if "NEGATIVE_EVIDENCE" in statuses:
        return "DO_NOT_ADVANCE"

    if all(s == "POSITIVE_EVIDENCE" for s in statuses):
        return "ADVANCE"

    return "DEFER"


first = load(FIRST)
first_eq = load(FIRST_EQ)
remaining = load(REMAINING)

if len(first) != 12 or len(first_eq) != 4 or len(remaining) != 32:
    raise SystemExit(
        "Unexpected input sizes: "
        f"batch01={len(first)}, "
        f"equivalence={len(first_eq)}, "
        f"remaining={len(remaining)}"
    )

first_equivalence = {
    row["review_group"]: row
    for row in first_eq
}

rows = []


for r in first:
    group = r["review_group"]
    letter = r["response_label"]

    statuses = [
        r[f"criterion_{i}_assessment"]
        for i in range(1, 4)
    ]

    eq = first_equivalence[group]

    rows.append({
        "review_group": group,
        "response_label": letter,
        "role": r["role"],
        "competency": r["competency"],
        "interview_question": r["interview_question"],
        "candidate_answer": r["candidate_answer"],
        "criterion_1": r["criterion_1"],
        "criterion_2": r["criterion_2"],
        "criterion_3": r["criterion_3"],
        "C1": statuses[0],
        "C2": statuses[1],
        "C3": statuses[2],
        "reference_decision": decision(statuses),
        "evidence_explanation": r["supporting_evidence_or_absence"],
        "semantic_equivalence": eq["same_material_evidence"],
        "equivalence_explanation": eq["researcher_explanation"],
        "annotation_status": r["assessment_status"],
        "review_flag": "YES" if group in FLAGS else "NO",
        "review_issue": FLAGS.get(group, ""),
        "researcher_adjudication": (
            "PENDING" if group in FLAGS else "NOT_YET_CONFIRMED"
        ),
    })



for r in remaining:
    group = r["review_group"]

    criteria = [
        item.strip()
        for item in r["criteria"].split(" | ")
    ]

    if len(criteria) != 3:
        raise SystemExit(
            f"Expected three criteria for {group}"
        )

    for letter in ("A", "B", "C"):
        statuses = [
            r[f"{letter}_C{i}"]
            for i in range(1, 4)
        ]

        rows.append({
            "review_group": group,
            "response_label": letter,
            "role": r["role"],
            "competency": r["competency"],
            "interview_question": r["interview_question"],
            "candidate_answer": r[f"answer_{letter}"],
            "criterion_1": criteria[0],
            "criterion_2": criteria[1],
            "criterion_3": criteria[2],
            "C1": statuses[0],
            "C2": statuses[1],
            "C3": statuses[2],
            "reference_decision": decision(statuses),
            "evidence_explanation": r[f"{letter}_explanation"],
            "semantic_equivalence": r["semantic_equivalence"],
            "equivalence_explanation": r["equivalence_explanation"],
            "annotation_status": r["annotation_status"],
            "review_flag": "YES" if group in FLAGS else "NO",
            "review_issue": FLAGS.get(group, ""),
            "researcher_adjudication": (
                "PENDING" if group in FLAGS else "NOT_YET_CONFIRMED"
            ),
        })



expected_groups = {
    f"GROUP-{i:03d}"
    for i in range(1, 37)
}

group_counts = Counter(
    row["review_group"] for row in rows
)

keys = [
    (row["review_group"], row["response_label"])
    for row in rows
]

if (
    len(rows) != 108
    or set(group_counts) != expected_groups
    or any(n != 3 for n in group_counts.values())
    or len(set(keys)) != 108
):
    raise SystemExit(
        "Dataset completeness or uniqueness validation failed."
    )

for row in rows:
    statuses = [row[c] for c in ("C1", "C2", "C3")]

    if any(s not in ALLOWED for s in statuses):
        raise SystemExit(
            f"Invalid status: {row['review_group']} "
            f"{row['response_label']}"
        )

    if not row["candidate_answer"].strip():
        raise SystemExit("Empty candidate answer detected.")



rows.sort(
    key=lambda r: (r["review_group"], r["response_label"])
)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

if OUTPUT.exists() or QC.exists():
    raise SystemExit(
        "Output already exists. Existing files were not overwritten."
    )

with OUTPUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f, fieldnames=list(rows[0].keys())
    )
    writer.writeheader()
    writer.writerows(rows)



stats = {
    "total_groups": len(group_counts),
    "total_responses": len(rows),
    "decisions": dict(Counter(
        r["reference_decision"] for r in rows
    )),
    "criterion_statuses": dict(Counter(
        r[c] for r in rows
        for c in ("C1", "C2", "C3")
    )),
    "review_flagged_groups": sorted(FLAGS),
    "review_flagged_responses": sum(
        r["review_flag"] == "YES" for r in rows
    ),
    "equivalence_groups": {
        group: next(
            r["semantic_equivalence"]
            for r in rows
            if r["review_group"] == group
        )
        for group in sorted(group_counts)
    },
    "source_files": [
        str(FIRST),
        str(FIRST_EQ),
        str(REMAINING),
    ],
    "reference_status": (
        "AI-assisted provisional; "
        "not independently validated"
    ),
    "no_original_model_evaluations_accessed": True,
}

QC.write_text(
    json.dumps(stats, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8"
)



print("ESDSA — CONSOLIDATED PROVISIONAL REFERENCE")
print("=" * 58)
print("Groups:", stats["total_groups"])
print("Responses:", stats["total_responses"])
print("Decisions:", stats["decisions"])
print("Flagged groups:", len(FLAGS))
print("Flagged responses:", stats["review_flagged_responses"])
print("Output:", OUTPUT)
print("QC:", QC)
print("Original annotations unchanged.")
print("No API calls made.")
