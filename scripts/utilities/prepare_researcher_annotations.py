
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path("data/benchmark")
SOURCE = ROOT / "content_review_v1/blinded_review_worksheet.csv"

OUT = ROOT / "researcher_annotations_v1"
ANNOTATIONS = OUT / "batch01_criterion_annotations.csv"
EQUIVALENCE = OUT / "batch01_semantic_equivalence.csv"
MANIFEST = OUT / "batch01_manifest.json"

PREVIOUSLY_INSPECTED = {
    "GROUP-011",
    "GROUP-017",
    "GROUP-023",
    "GROUP-036"
}

if any(p.exists() for p in (
    ANNOTATIONS, EQUIVALENCE, MANIFEST
)):
    raise SystemExit(
        "Batch outputs already exist. Nothing overwritten."
    )

with SOURCE.open(newline="", encoding="utf-8") as f:
    source_rows = list(csv.DictReader(f))

if len(source_rows) != 36:
    raise ValueError("Expected 36 review groups")

available = [
    r for r in source_rows
    if r["review_group"] not in PREVIOUSLY_INSPECTED
]

batch = available[:4]

if len(batch) != 4:
    raise ValueError("Insufficient review groups")

annotations = []
equivalence = []

for group in batch:
    group_id = group["review_group"]

    criteria = group["criteria"].split(" | ")

    if len(criteria) != 3:
        raise ValueError(
            f"Expected three indicators: {group_id}"
        )

    for letter in ("A", "B", "C"):
        annotations.append({
            "review_group": group_id,
            "response_label": letter,
            "role": group["role"],
            "competency": group["competency"],
            "interview_question": group[
                "interview_question"
            ],
            "criterion_1": criteria[0],
            "criterion_2": criteria[1],
            "criterion_3": criteria[2],
            "candidate_answer": group[
                f"answer_{letter}"
            ],
            "criterion_1_assessment": "",
            "criterion_2_assessment": "",
            "criterion_3_assessment": "",
            "supporting_evidence_or_absence": "",
            "researcher_explanation": "",
            "assessment_status": "PENDING"
        })

    equivalence.append({
        "review_group": group_id,
        "competency": group["competency"],
        "same_material_evidence": "",
        "material_differences": "",
        "researcher_explanation": "",
        "assessment_status": "PENDING"
    })

OUT.mkdir(parents=True, exist_ok=True)

def save_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(rows[0])
        )
        writer.writeheader()
        writer.writerows(rows)

save_csv(ANNOTATIONS, annotations)
save_csv(EQUIVALENCE, equivalence)

manifest = {
    "batch": "01",
    "annotator": "PRIMARY_RESEARCHER",
    "annotation_standard": "RESEARCHER_ADJUDICATED",
    "source_sha256": hashlib.sha256(
        SOURCE.read_bytes()
    ).hexdigest(),
    "groups": [
        r["review_group"] for r in batch
    ],
    "response_count": len(annotations),
    "criterion_judgments": len(annotations) * 3,
    "model_predictions_excluded": True,
    "independent_external_validation": False,
    "previous_model_exposure": (
        "Four known decision-disagreement groups excluded; "
        "other prior exposure cannot be ruled out."
    ),
    "status": "PENDING"
}

MANIFEST.write_text(
    json.dumps(manifest, indent=2),
    encoding="utf-8"
)

print("\nESDSA — RESEARCHER ANNOTATION BATCH 01")
print("=" * 60)
print("Annotator: Primary researcher")
print("Groups:", len(batch))
print("Responses:", len(annotations))
print("Criterion judgments:", len(annotations) * 3)
print("Semantic-equivalence judgments:", len(equivalence))
print("Previously inspected groups excluded:", 4)
print("\nCriterion worksheet:", ANNOTATIONS)
print("Equivalence worksheet:", EQUIVALENCE)
print("Manifest:", MANIFEST)
print("\nModel predictions not included.")
print("No API calls made.")
print("Original data unchanged.")
