
import csv
from pathlib import Path

SOURCE = Path(
    "data/reference/f02_semantic_review_v1.csv"
)
FOLDER = Path("data/reference/independent_reviews")

REVIEWERS = ("R01", "R02")

with SOURCE.open(newline="", encoding="utf-8") as f:
    source_rows = list(csv.DictReader(f))

if len(source_rows) != 2:
    raise ValueError("Expected exactly two responses")

if len({r["review_id"] for r in source_rows}) != 2:
    raise ValueError("Duplicate review IDs")

FOLDER.mkdir(parents=True, exist_ok=True)

for reviewer in REVIEWERS:
    output = FOLDER / f"f02_review_{reviewer}.csv"

    if output.exists():
        raise SystemExit(
            f"Output already exists: {output}"
        )

    rows = []

    for source in source_rows:
        rows.append({
            "reviewer_id": reviewer,
            "review_id": source["review_id"],
            "interview_question": source["interview_question"],
            "candidate_answer": source["candidate_answer"],
            "criterion": source["assessed_criterion"],
            "definition": source["criterion_definition"],
            "evidence_excerpt": "",
            "evidence_assessment": "",
            "reviewer_explanation": "",
            "pair_semantic_equivalence": "",
            "equivalence_explanation": "",
            "review_status": "PENDING"
        })

    if reviewer == "R02":
        rows.reverse()

    with output.open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=list(rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(rows)

    print("Created:", output)

print("\nReview instructions:")
print("1. Assess each response independently for C3.")
print("2. Use POSITIVE_EVIDENCE, NEGATIVE_EVIDENCE,")
print("   or INSUFFICIENT_EVIDENCE.")
print("3. Record a supporting excerpt and explanation.")
print("4. Compare the pair for substantive C3 equivalence.")
print("5. Enter YES, NO, or UNCERTAIN for equivalence.")
print("6. Reviewers must not consult model outputs.")
print("7. Reviewers must not discuss before submission.")
print("\nNo existing files modified.")
