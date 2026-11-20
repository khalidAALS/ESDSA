
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("data/benchmark")
INPUT = ROOT / "development_responses_v1.csv"
DESIGN = ROOT / "development_response_design_v1.csv"
RUBRICS = ROOT / "rubrics_v1"

OUT_DIR = ROOT / "content_review_v1"
WORKSHEET = OUT_DIR / "blinded_review_worksheet.csv"
MAPPING = OUT_DIR / "private_review_mapping.json"
REPORT = OUT_DIR / "preparation_report.json"

SEED = 20261119

EXPECTED_INPUT_HASH = (
    "566400420436e82274f3bbb05066c275009a0"
    "a5f21bc35add77b68e745877dd2"
)

EXPECTED_DESIGN_HASH = (
    "6ef1b4d600fcaec971e722069e3a345e758"
    "5eef46efc180d0cdb68f637ba8e45"
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    if any(p.exists() for p in (WORKSHEET, MAPPING, REPORT)):
        raise SystemExit(
            "Review outputs already exist. Nothing overwritten."
        )

    if sha256(INPUT) != EXPECTED_INPUT_HASH:
        raise ValueError("Model-facing dataset has changed")

    if sha256(DESIGN) != EXPECTED_DESIGN_HASH:
        raise ValueError("Design metadata has changed")

    responses = read_csv(INPUT)
    design = read_csv(DESIGN)

    if len(responses) != 108 or len(design) != 108:
        raise ValueError("Expected 108 records in each file")

    response_map = {
        r["response_id"]: r for r in responses
    }

    design_map = {
        r["response_id"]: r for r in design
    }

    if (
        len(response_map) != 108
        or len(design_map) != 108
        or set(response_map) != set(design_map)
    ):
        raise ValueError("Missing or duplicate response IDs")

    groups = defaultdict(dict)
    suspicious = []

    for response_id, info in design_map.items():
        response = response_map[response_id]

        if hashlib.sha256(
            response["answer"].encode("utf-8")
        ).hexdigest() != info["response_sha256"]:
            raise ValueError(
                f"Answer fingerprint mismatch: {response_id}"
            )

        if info["partition"] != "DEVELOPMENT":
            raise ValueError("Non-development record detected")

        key = (
            info["family_id"],
            info["intended_condition"]
        )
        variant = info["linguistic_variant"]

        if variant in groups[key]:
            raise ValueError(f"Duplicate variant: {key}")

        groups[key][variant] = response_id

        if len(response["answer"].split()) < 12:
            suspicious.append({
                "response_id": response_id,
                "issue": "VERY_SHORT_RESPONSE"
            })

    variants = {
        "CANONICAL", "CONVERSATIONAL", "CONCISE"
    }

    if len(groups) != 36:
        raise ValueError("Expected 36 evidence-condition groups")

    for key, group in groups.items():
        if set(group) != variants:
            raise ValueError(f"Incomplete group: {key}")

        answer_texts = [
            response_map[rid]["answer"]
            for rid in group.values()
        ]

        if len(set(answer_texts)) != 3:
            suspicious.append({
                "group": key,
                "issue": "DUPLICATE_VARIANT_TEXT"
            })

    rng = random.Random(SEED)
    group_keys = sorted(groups)
    rng.shuffle(group_keys)

    worksheet_rows = []
    private_mapping = {}

    for number, key in enumerate(group_keys, start=1):
        family_id, intended_condition = key
        review_group = f"GROUP-{number:03d}"

        response_ids = list(groups[key].values())
        rng.shuffle(response_ids)

        first = response_map[response_ids[0]]

        if any(
            response_map[rid]["question"] != first["question"]
            or response_map[rid]["rubric_id"] != first["rubric_id"]
            for rid in response_ids
        ):
            raise ValueError(
                f"Inconsistent question or rubric: {key}"
            )

        code = first["competency_code"]
        rubric_file = RUBRICS / f"{code}_rubric_v1.json"
        rubric = json.loads(
            rubric_file.read_text(encoding="utf-8")
        )

        if rubric["rubric_id"] != first["rubric_id"]:
            raise ValueError(f"Rubric mismatch: {key}")

        criteria_text = " | ".join(
            f"{c['id']}: {c['definition']}"
            for c in rubric["criteria"]
        )

        row = {
            "review_group": review_group,
            "role": rubric["role_name"],
            "competency": rubric["competency_name"],
            "interview_question": first["question"],
            "criteria": criteria_text
        }

        private_mapping[review_group] = {
            "family_id": family_id,
            "intended_condition": intended_condition,
            "responses": {}
        }

        for letter, rid in zip(
            ("A", "B", "C"), response_ids
        ):
            row[f"answer_{letter}"] = (
                response_map[rid]["answer"]
            )
            row[f"assessment_{letter}"] = ""
            row[f"evidence_explanation_{letter}"] = ""

            private_mapping[review_group]["responses"][letter] = {
                "response_id": rid,
                "linguistic_variant": (
                    design_map[rid]["linguistic_variant"]
                )
            }

        row["same_material_evidence"] = ""
        row["equivalence_explanation"] = ""
        row["reviewer_id"] = ""
        row["review_status"] = "PENDING"

        worksheet_rows.append(row)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with WORKSHEET.open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=list(worksheet_rows[0])
        )
        writer.writeheader()
        writer.writerows(worksheet_rows)

    mapping_doc = {
        "purpose": "PRIVATE — DO NOT SHARE WITH REVIEWERS",
        "seed": SEED,
        "model_input_sha256": sha256(INPUT),
        "design_sha256": sha256(DESIGN),
        "groups": private_mapping
    }

    MAPPING.write_text(
        json.dumps(mapping_doc, indent=2),
        encoding="utf-8"
    )

    report = {
        "response_count": len(responses),
        "review_groups": len(worksheet_rows),
        "competency_count": len({
            r["competency_code"] for r in responses
        }),
        "condition_counts": dict(Counter(
            d["intended_condition"] for d in design
        )),
        "structural_warnings": suspicious,
        "semantic_validation": "PENDING",
        "evidence_validation": "PENDING",
        "expert_review": "PENDING"
    }

    REPORT.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    print("\nESDSA — CONTENT REVIEW PREPARATION")
    print("=" * 60)
    print("Responses verified:", len(responses))
    print("Blinded review groups:", len(worksheet_rows))
    print("Competencies:", report["competency_count"])
    print("Intended conditions:", report["condition_counts"])
    print("Structural warnings:", len(suspicious))
    print("\nReviewer worksheet:", WORKSHEET)
    print("Private mapping:", MAPPING)
    print("Preparation report:", REPORT)
    print("\nSemantic equivalence: NOT YET VALIDATED")
    print("Evidence classifications: NOT YET VALIDATED")
    print("No API calls made.")
    print("Original dataset unchanged.")


if __name__ == "__main__":
    main()
