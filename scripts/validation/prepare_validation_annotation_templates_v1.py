
# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

from pathlib import Path
from collections import Counter, defaultdict
import csv
import hashlib
import json
import secrets
import sys

ROOT = Path(__file__).resolve().parents[2]

DATASET = (
    ROOT
    / "results/validation_consolidated_v1/validation_responses_v1.csv"
)
MANIFEST = (
    ROOT
    / "results/validation_consolidated_v1/validation_integrity_manifest_v1.json"
)
SCENARIOS = ROOT / "data/benchmark/validation_scenarios_v2.csv"
RUBRIC_DIR = ROOT / "data/benchmark/rubrics_v1"

OUT_DIR = ROOT / "results/validation_annotation_templates_v1"

EVIDENCE_FILE = OUT_DIR / "validation_evidence_annotations_v1.csv"
SEMANTIC_FILE = OUT_DIR / "validation_semantic_annotations_v1.csv"
KEY_FILE = OUT_DIR / "validation_annotation_blinding_key_v1.csv"
AUDIT_FILE = OUT_DIR / "validation_annotation_template_manifest_v1.json"

CONDITIONS = {"SUFFICIENT", "INSUFFICIENT", "NEGATIVE"}
VARIANTS = {"CANONICAL", "CONVERSATIONAL", "CONCISE"}

VALID_STATUSES = [
    "POSITIVE_EVIDENCE",
    "NEGATIVE_EVIDENCE",
    "INSUFFICIENT_EVIDENCE",
]

EXPECTED_FAMILIES = 24
EXPECTED_RESPONSES = 216
EXPECTED_GROUPS = 72


def fail(message):
    raise SystemExit(f"FAIL: {message}")


def read_csv(path):
    if not path.is_file():
        fail(f"Missing file: {path}")

    with path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        return list(csv.DictReader(handle))


def read_json(path):
    if not path.is_file():
        fail(f"Missing file: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path, columns, records):
    with path.open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(records)


def unique_tokens(prefix, count):
    values = set()

    while len(values) < count:
        values.add(prefix + secrets.token_hex(8).upper())

    return list(values)


def main():
    print("ESDSA VALIDATION — ANNOTATION TEMPLATE PREPARATION")
    print("=" * 65)
    print("API requests: 0")
    print("Model evaluation: NOT RUN")
    print("TEST partition: NOT ACCESSED")
    print()

    outputs = [
        EVIDENCE_FILE,
        SEMANTIC_FILE,
        KEY_FILE,
        AUDIT_FILE,
    ]

    existing = [p for p in outputs if p.exists()]

    if existing:
        fail(
            "Annotation output already exists; refusing to overwrite: "
            + ", ".join(str(p) for p in existing)
        )

    manifest = read_json(MANIFEST)

    if manifest.get("status") != "PASSED":
        fail("Consolidation manifest has not passed")

    if manifest.get("response_count") != EXPECTED_RESPONSES:
        fail("Consolidation response count mismatch")

    if sha256(DATASET) != manifest.get("output_csv_sha256"):
        fail("Consolidated dataset SHA256 mismatch")

    dataset = read_csv(DATASET)
    scenario_rows = read_csv(SCENARIOS)

    if len(dataset) != EXPECTED_RESPONSES:
        fail(f"Expected 216 responses, found {len(dataset)}")

    if len(scenario_rows) != EXPECTED_FAMILIES:
        fail(f"Expected 24 scenarios, found {len(scenario_rows)}")

    scenarios = {}

    for item in scenario_rows:
        fid = item["family_id"].strip()

        if fid in scenarios:
            fail(f"Duplicate scenario: {fid}")

        if item["partition"].strip() != "VALIDATION":
            fail(f"Unexpected scenario partition: {fid}")

        if not item["interview_question"].strip():
            fail(f"Missing scenario question: {fid}")

        scenarios[fid] = item


    rubrics = {}

    for item in scenario_rows:
        code = item["competency_code"].strip()
        filename = item["rubric_file"].strip()

        if code in rubrics:
            continue

        expected_filename = f"{code}_rubric_v1.json"

        if filename != expected_filename:
            fail(
                f"Unexpected rubric filename for {code}: "
                f"{filename}"
            )

        rubric_path = RUBRIC_DIR / filename
        rubric = read_json(rubric_path)

        if rubric.get("competency_code") != code:
            fail(f"Rubric competency mismatch: {code}")

        if rubric.get("rubric_id") != item["rubric_id"]:
            fail(f"Rubric identifier mismatch: {code}")

        criteria = rubric.get("criteria")

        if not isinstance(criteria, list) or len(criteria) != 3:
            fail(f"Expected three rubric criteria: {code}")

        criterion_ids = [x["id"] for x in criteria]

        if len(set(criterion_ids)) != 3:
            fail(f"Duplicate rubric criterion IDs: {code}")

        for criterion in criteria:
            if not criterion.get("definition"):
                fail(f"Missing rubric definition: {code}")

        rubrics[code] = rubric

    if len(rubrics) != 12:
        fail(f"Expected 12 rubrics, found {len(rubrics)}")

    print(f"Rubrics verified: {len(rubrics)}")
    print(f"Scenario questions verified: {len(scenarios)}")

    groups = defaultdict(list)
    response_ids = set()

    for row in dataset:
        fid = row["family_id"]
        rid = row["response_id"]
        condition = row["generation_condition"]
        variant = row["variant"]

        if fid not in scenarios:
            fail(f"Unregistered family: {fid}")

        if row["partition"] != "VALIDATION":
            fail(f"Non-validation response: {rid}")

        if condition not in CONDITIONS:
            fail(f"Unknown generation condition: {rid}")

        if variant not in VARIANTS:
            fail(f"Unknown linguistic variant: {rid}")

        if rid in response_ids:
            fail(f"Duplicate response ID: {rid}")

        response_ids.add(rid)

        answer = row["answer"]

        if not answer.strip():
            fail(f"Empty response: {rid}")

        actual_hash = hashlib.sha256(
            answer.encode("utf-8")
        ).hexdigest()

        if actual_hash != row["answer_sha256"]:
            fail(f"Answer hash mismatch: {rid}")

        groups[(fid, condition)].append(row)

    if len(groups) != EXPECTED_GROUPS:
        fail(f"Expected 72 groups; found {len(groups)}")

    for fid in scenarios:
        for condition in CONDITIONS:
            items = groups.get((fid, condition), [])

            if len(items) != 3:
                fail(
                    f"Expected three variants: {fid}, {condition}"
                )

            if {x["variant"] for x in items} != VARIANTS:
                fail(
                    f"Incorrect variants: {fid}, {condition}"
                )

    blinded_ids = unique_tokens("VR-", EXPECTED_RESPONSES)
    group_ids = unique_tokens("VG-", EXPECTED_GROUPS)

    secrets.SystemRandom().shuffle(blinded_ids)
    secrets.SystemRandom().shuffle(group_ids)

    response_id_map = dict(zip(sorted(response_ids), blinded_ids))
    group_keys = sorted(groups)
    group_id_map = dict(zip(group_keys, group_ids))

    evidence_records = []
    semantic_records = []
    key_records = []

    for group_key in group_keys:
        fid, condition = group_key
        scenario = scenarios[fid]
        rubric = rubrics[scenario["competency_code"]]
        group_id = group_id_map[group_key]

        responses = list(groups[group_key])
        secrets.SystemRandom().shuffle(responses)

        semantic_row = {
            "blinded_group_id": group_id,
            "family_id": fid,
            "role_name": scenario["role_name"],
            "competency_code": scenario["competency_code"],
            "competency_name": scenario["competency_name"],
            "scenario_profile": scenario["scenario_profile"],
            "interview_question": scenario["interview_question"],
            "semantic_equivalence": "",
            "material_differences": "",
            "equivalence_rationale": "",
            "reviewer_id": "",
            "review_date": "",
            "review_status": "PENDING",
        }

        for index, response in enumerate(responses):
            slot = ("A", "B", "C")[index]
            rid = response["response_id"]
            blinded_id = response_id_map[rid]

            semantic_row[f"response_{slot}_id"] = blinded_id
            semantic_row[f"response_{slot}_text"] = response["answer"]

            key_records.append({
                "blinded_response_id": blinded_id,
                "blinded_group_id": group_id,
                "semantic_slot": slot,
                "original_response_id": rid,
                "family_id": fid,
                "generation_condition": condition,
                "original_variant": response["variant"],
                "answer_sha256": response["answer_sha256"],
            })

            evidence_row = {
                "blinded_response_id": blinded_id,
                "blinded_group_id": group_id,
                "family_id": fid,
                "role_name": scenario["role_name"],
                "competency_code": scenario["competency_code"],
                "competency_name": scenario["competency_name"],
                "scenario_profile": scenario["scenario_profile"],
                "interview_question": scenario["interview_question"],
                "rubric_id": rubric["rubric_id"],
                "answer": response["answer"],
                "annotation_notes": "",
                "reviewer_id": "",
                "review_date": "",
                "review_status": "PENDING",
            }

            for criterion_number, criterion in enumerate(
                rubric["criteria"], start=1
            ):
                prefix = f"criterion_{criterion_number}"

                evidence_row[f"{prefix}_id"] = criterion["id"]
                evidence_row[f"{prefix}_name"] = criterion["name"]
                evidence_row[f"{prefix}_definition"] = (
                    criterion["definition"]
                )
                evidence_row[f"{prefix}_status"] = ""
                evidence_row[f"{prefix}_passage"] = ""
                evidence_row[f"{prefix}_rationale"] = ""

            evidence_records.append(evidence_row)

        semantic_records.append(semantic_row)

    if len(evidence_records) != EXPECTED_RESPONSES:
        fail("Incorrect evidence template count")

    if len(semantic_records) != EXPECTED_GROUPS:
        fail("Incorrect semantic template count")

    if len(key_records) != EXPECTED_RESPONSES:
        fail("Incorrect blinding key count")

    if len({
        x["blinded_response_id"] for x in key_records
    }) != EXPECTED_RESPONSES:
        fail("Blinded response IDs are not unique")


    secrets.SystemRandom().shuffle(evidence_records)
    secrets.SystemRandom().shuffle(semantic_records)

    evidence_columns = [
        "blinded_response_id",
        "blinded_group_id",
        "family_id",
        "role_name",
        "competency_code",
        "competency_name",
        "scenario_profile",
        "interview_question",
        "rubric_id",
        "answer",
    ]

    for number in (1, 2, 3):
        evidence_columns.extend([
            f"criterion_{number}_id",
            f"criterion_{number}_name",
            f"criterion_{number}_definition",
            f"criterion_{number}_status",
            f"criterion_{number}_passage",
            f"criterion_{number}_rationale",
        ])

    evidence_columns.extend([
        "annotation_notes",
        "reviewer_id",
        "review_date",
        "review_status",
    ])

    semantic_columns = [
        "blinded_group_id",
        "family_id",
        "role_name",
        "competency_code",
        "competency_name",
        "scenario_profile",
        "interview_question",
        "response_A_id",
        "response_A_text",
        "response_B_id",
        "response_B_text",
        "response_C_id",
        "response_C_text",
        "semantic_equivalence",
        "material_differences",
        "equivalence_rationale",
        "reviewer_id",
        "review_date",
        "review_status",
    ]

    key_columns = [
        "blinded_response_id",
        "blinded_group_id",
        "semantic_slot",
        "original_response_id",
        "family_id",
        "generation_condition",
        "original_variant",
        "answer_sha256",
    ]


    OUT_DIR.mkdir(parents=True, exist_ok=True)

    write_csv(
        EVIDENCE_FILE, evidence_columns, evidence_records
    )
    write_csv(
        SEMANTIC_FILE, semantic_columns, semantic_records
    )
    write_csv(
        KEY_FILE, key_columns, key_records
    )

    audit = {
        "name": "ESDSA_VALIDATION_ANNOTATION_TEMPLATES_V1",
        "partition": "VALIDATION",
        "status": "TEMPLATES_CREATED",
        "families": EXPECTED_FAMILIES,
        "responses": EXPECTED_RESPONSES,
        "semantic_groups": EXPECTED_GROUPS,
        "rubrics": len(rubrics),
        "indicators_per_response": 3,
        "total_indicator_assessments": 648,
        "source_dataset_sha256": sha256(DATASET),
        "source_scenarios_sha256": sha256(SCENARIOS),
        "rubric_sha256": {
            code: sha256(
                RUBRIC_DIR / f"{code}_rubric_v1.json"
            )
            for code in sorted(rubrics)
        },
        "output_sha256": {
            path.name: sha256(path)
            for path in (
                EVIDENCE_FILE,
                SEMANTIC_FILE,
                KEY_FILE,
            )
        },
        "allowed_evidence_statuses": VALID_STATUSES,
        "allowed_semantic_statuses": [
            "YES",
            "NO",
            "UNCERTAIN",
        ],
        "rules": [
            "Assess demonstrated evidence, not generation intent.",
            "Omission alone is not NEGATIVE_EVIDENCE.",
            "Use INSUFFICIENT_EVIDENCE when evidence is absent.",
            "For positive or negative evidence, record the "
            "supporting passage and rationale.",
            "Semantic equivalence concerns decision-relevant "
            "meaning, not wording alone.",
            "Do not use generation condition as a reference label.",
            "Do not infer ADVANCE, DO_NOT_ADVANCE, or DEFER yet.",
            "Blinding is partial: scenario and answer content "
            "remain visible to reviewers.",
            "Expert review has not been completed.",
        ],
    }

    AUDIT_FILE.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 65)
    print("ANNOTATION TEMPLATE PREPARATION: PASSED")
    print(f"Validation families: {EXPECTED_FAMILIES}")
    print(f"Evidence annotation rows: {len(evidence_records)}")
    print(f"Rubric indicator assessments: 648")
    print(f"Semantic-equivalence groups: {len(semantic_records)}")
    print(f"Blinding key rows: {len(key_records)}")
    print()
    print("Outputs:")
    for path in outputs:
        print(f"  {path.relative_to(ROOT)}")

    print()
    print("No reference decisions inferred.")
    print("No evaluator run.")
    print("TEST partition: NOT ACCESSED")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, TypeError) as exc:
        fail(f"Invalid input structure: {exc}")

