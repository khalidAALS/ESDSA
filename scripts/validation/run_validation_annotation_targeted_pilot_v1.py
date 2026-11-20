
# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

from pathlib import Path
import os
import sys

from openai import OpenAI

import run_validation_annotation_pilot_v1 as pilot


ROOT = Path(__file__).resolve().parents[2]

TARGET_FAMILY = "ESDSA-CSS02-06"
COMPLETED_PILOT_GROUP = "VG-25DA3C60956AC4B4"

OUT_DIR = ROOT / "results/validation_ai_annotations_v1"
EVIDENCE_DIR = OUT_DIR / "evidence"
SEMANTIC_DIR = OUT_DIR / "semantic"

EXPERIMENT = "ESDSA_VALIDATION_AI_ANNOTATION_TARGETED_PILOT_V1"


def fail(message):
    raise SystemExit(f"FAIL: {message}")


def make_record(response, kind, identifier, result):
    saved = pilot.record(response, kind, identifier, result)
    saved["experiment"] = EXPERIMENT
    return saved


def main():
    print("ESDSA VALIDATION — TARGETED ANNOTATION PILOT")
    print("=" * 65)
    print("Target family:", TARGET_FAMILY)
    print("New evidence annotations: 6")
    print("New semantic assessments: 2")
    print("Maximum new API requests: 8")
    print("Blinding key: NOT ACCESSED")
    print("ESDSA evaluator: NOT RUN")
    print("TEST partition: NOT ACCESSED")
    print()

    evidence, semantic, by_group = pilot.verify_inputs()


    family_groups = [
        row for row in semantic
        if row["family_id"] == TARGET_FAMILY
    ]

    if len(family_groups) != 3:
        fail(
            "Expected exactly three blinded groups "
            f"for {TARGET_FAMILY}; found {len(family_groups)}"
        )

    prior_groups = [
        row for row in family_groups
        if row["blinded_group_id"] == COMPLETED_PILOT_GROUP
    ]

    if len(prior_groups) != 1:
        fail("Original pilot group not found in target family")

    prior_members = by_group[COMPLETED_PILOT_GROUP]

    for row in prior_members:
        rid = row["blinded_response_id"]
        path = EVIDENCE_DIR / f"{rid}.json"

        if not path.exists():
            fail(f"Original pilot evidence missing: {rid}")

        saved = pilot.load_json(path)

        if (
            saved.get("blinded_id") != rid
            or saved.get("review_type") != "EVIDENCE"
        ):
            fail(f"Original pilot record mismatch: {rid}")

        pilot.validate_evidence(row, saved["annotation"])

    prior_semantic = (
        SEMANTIC_DIR / f"{COMPLETED_PILOT_GROUP}.json"
    )

    if not prior_semantic.exists():
        fail("Original pilot semantic annotation missing")

    prior_record = pilot.load_json(prior_semantic)

    if (
        prior_record.get("blinded_id") != COMPLETED_PILOT_GROUP
        or prior_record.get("review_type") != "SEMANTIC_EQUIVALENCE"
    ):
        fail("Original pilot semantic record mismatch")

    pilot.validate_semantic(prior_record["annotation"])

    target_groups = sorted(
        (
            row for row in family_groups
            if row["blinded_group_id"] != COMPLETED_PILOT_GROUP
        ),
        key=lambda row: row["blinded_group_id"],
    )

    if len(target_groups) != 2:
        fail("Expected exactly two remaining target groups")

    print("Original pilot verified: 3 evidence + 1 semantic")
    print("Remaining blinded groups:")
    for row in target_groups:
        print(" ", row["blinded_group_id"])
    print()

    if not os.environ.get("OPENAI_API_KEY"):
        fail("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(timeout=120, max_retries=0)

    new_evidence = 0
    new_semantic = 0

    for group in target_groups:
        gid = group["blinded_group_id"]

        members = sorted(
            by_group[gid],
            key=lambda row: row["blinded_response_id"],
        )

        print("-" * 65)
        print("Group:", gid)

        if len(members) != 3:
            fail(f"Incorrect group size: {gid}")

        for row in members:
            rid = row["blinded_response_id"]
            output_file = EVIDENCE_DIR / f"{rid}.json"

            if output_file.exists():
                saved = pilot.load_json(output_file)

                if (
                    saved.get("blinded_id") != rid
                    or saved.get("review_type") != "EVIDENCE"
                ):
                    fail(f"Existing evidence record mismatch: {rid}")

                pilot.validate_evidence(
                    row,
                    saved["annotation"],
                )

                print(f"ALREADY SAVED: evidence {rid}")
                continue

            print(f"Annotating evidence: {rid}")

            response, result = pilot.call_model(
                client,
                pilot.EVIDENCE_INSTRUCTIONS,
                pilot.evidence_payload(row),
                pilot.EVIDENCE_SCHEMA,
                "esdsa_evidence_annotation_v1",
            )

            pilot.validate_evidence(row, result)

            pilot.save_json_new(
                output_file,
                make_record(
                    response,
                    "EVIDENCE",
                    rid,
                    result,
                ),
            )

            new_evidence += 1
            print(f"PASS: evidence {rid}")

        semantic_file = SEMANTIC_DIR / f"{gid}.json"

        if semantic_file.exists():
            saved = pilot.load_json(semantic_file)

            if (
                saved.get("blinded_id") != gid
                or saved.get("review_type") != "SEMANTIC_EQUIVALENCE"
            ):
                fail(f"Existing semantic record mismatch: {gid}")

            pilot.validate_semantic(saved["annotation"])

            print(f"ALREADY SAVED: semantic {gid}")
            continue

        print(f"Annotating semantic equivalence: {gid}")

        response, result = pilot.call_model(
            client,
            pilot.SEMANTIC_INSTRUCTIONS,
            pilot.semantic_payload(group, members),
            pilot.SEMANTIC_SCHEMA,
            "esdsa_semantic_equivalence_v1",
        )

        pilot.validate_semantic(result)

        pilot.save_json_new(
            semantic_file,
            make_record(
                response,
                "SEMANTIC_EQUIVALENCE",
                gid,
                result,
            ),
        )

        new_semantic += 1
        print(f"PASS: semantic {gid}")

    for group in family_groups:
        gid = group["blinded_group_id"]

        for row in by_group[gid]:
            rid = row["blinded_response_id"]
            path = EVIDENCE_DIR / f"{rid}.json"

            if not path.exists():
                fail(f"Missing final evidence record: {rid}")

            saved = pilot.load_json(path)
            pilot.validate_evidence(
                row,
                saved["annotation"],
            )

        path = SEMANTIC_DIR / f"{gid}.json"

        if not path.exists():
            fail(f"Missing final semantic record: {gid}")

        saved = pilot.load_json(path)
        pilot.validate_semantic(saved["annotation"])

    print()
    print("=" * 65)
    print("TARGETED ANNOTATION PILOT: PASSED")
    print("Target family:", TARGET_FAMILY)
    print("Evidence annotations complete: 9 / 9")
    print("Semantic groups complete: 3 / 3")
    print("New evidence API requests:", new_evidence)
    print("New semantic API requests:", new_semantic)
    print("Original templates: NOT MODIFIED")
    print("Blinding key: NOT ACCESSED")
    print("No final reference decisions assigned.")
    print("TEST partition: NOT ACCESSED")


if __name__ == "__main__":
    main()
