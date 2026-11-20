
import csv
import random
from pathlib import Path

SOURCE = Path(
    "data/benchmark/content_review_v1/"
    "blinded_review_worksheet.csv"
)

OUT_DIR = Path(
    "data/benchmark/content_review_v1/"
    "independent_reviews"
)

REVIEWERS = ("R01", "R02")

with SOURCE.open(newline="", encoding="utf-8") as f:
    groups = list(csv.DictReader(f))

assert len(groups) == 36
assert len({g["review_group"] for g in groups}) == 36

OUT_DIR.mkdir(parents=True, exist_ok=True)

outputs = [
    OUT_DIR / f"benchmark_review_{reviewer}.csv"
    for reviewer in REVIEWERS
]

if any(path.exists() for path in outputs):
    raise SystemExit(
        "Reviewer file already exists. Nothing overwritten."
    )

for reviewer, output in zip(REVIEWERS, outputs):
    rows = []

    for group in groups:
        row = {
            "reviewer_id": reviewer,
            "review_group": group["review_group"],
            "role": group["role"],
            "competency": group["competency"],
            "interview_question": group[
                "interview_question"
            ],
            "criteria": group["criteria"]
        }

        for letter in ("A", "B", "C"):
            row[f"answer_{letter}"] = group[
                f"answer_{letter}"
            ]

            for number in (1, 2, 3):
                row[
                    f"{letter}_criterion_{number}"
                ] = ""

            row[f"{letter}_evidence_explanation"] = ""

        row["pairwise_semantic_equivalence"] = ""
        row["equivalence_explanation"] = ""
        row["review_status"] = "PENDING"

        rows.append(row)

    random.Random(
        20261119 if reviewer == "R01" else 20261120
    ).shuffle(rows)

    with output.open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=list(rows[0])
        )
        writer.writeheader()
        writer.writerows(rows)

    print("Created:", output)

print("\nESDSA — INDEPENDENT BENCHMARK REVIEW")
print("Reviewers:", len(REVIEWERS))
print("Groups per reviewer:", len(groups))
print("Responses per reviewer:", len(groups) * 3)
print("Criterion assessments per reviewer:", len(groups) * 9)
print("Reference conditions exposed: NO")
print("Existing benchmark and mapping unchanged.")
