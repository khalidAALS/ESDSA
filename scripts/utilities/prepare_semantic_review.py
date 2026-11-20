
import csv
import hashlib
import json
import random
from pathlib import Path

ROOT = Path("data")
INPUT = ROOT / "model_inputs/challenge_benchmark_v2.csv"
OUTPUT = ROOT / "reference/f02_semantic_review_v1.csv"
MANIFEST = ROOT / "reference/f02_semantic_review_manifest_v1.json"

if OUTPUT.exists() or MANIFEST.exists():
    raise SystemExit("Review files already exist. Nothing overwritten.")

TARGET_IDS = {"ESDSA-V2-0006", "ESDSA-V2-0007"}

with INPUT.open(newline="", encoding="utf-8") as f:
    records = [
        row for row in csv.DictReader(f)
        if row["response_id"] in TARGET_IDS
    ]

assert len(records) == 2
assert len({r["response_id"] for r in records}) == 2
assert len({r["question"] for r in records}) == 1

random.Random(20261119).shuffle(records)

review_rows = []
mapping = {}

for index, row in enumerate(records, start=1):
    review_id = f"F02-REVIEW-{index:02d}"
    mapping[review_id] = row["response_id"]

    review_rows.append({
        "review_id": review_id,
        "interview_question": row["question"],
        "candidate_answer": row["answer"],
        "assessed_criterion": "C3 — Reasoned correction",
        "criterion_definition": (
            "Connects the proposed correction to an identified cause."
        ),
        "evidence_excerpt": "",
        "evidence_assessment": "",
        "reviewer_explanation": "",
        "reviewer_id": "",
        "review_status": "PENDING"
    })

with OUTPUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f, fieldnames=list(review_rows[0].keys())
    )
    writer.writeheader()
    writer.writerows(review_rows)

manifest = {
    "review_type": "C3 evidence and semantic equivalence",
    "purpose": "Development diagnostic review",
    "response_mapping": mapping,
    "source_sha256": hashlib.sha256(
        INPUT.read_bytes()
    ).hexdigest(),
    "original_model_results_modified": False,
    "review_status": "PENDING",
    "instructions": (
        "Assess each answer independently for C3 evidence. "
        "Then compare whether the two answers communicate "
        "materially equivalent evidence. Do not consult "
        "model predictions or expected reference labels."
    )
}

MANIFEST.write_text(
    json.dumps(manifest, indent=2),
    encoding="utf-8"
)

print("Review worksheet:", OUTPUT)
print("Local mapping:", MANIFEST)
print("Responses:", len(review_rows))
print("Model predictions excluded: YES")
print("Reviewer judgments: PENDING")
print("Original experiment unchanged.")
