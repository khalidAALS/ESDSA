

"""Complete two unresolved ESDSA TEST annotations.

Explicit AI-assisted manual adjudication, not model retry.
Uses the original strict evidence validator.
Preserves previously accepted annotations and semantic reviews.
"""

# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import run_validation_annotation_pilot_v1 as pilot

ROOT = Path("results/test_ai_annotations_v2")
TEMPLATE = ROOT / "test_evidence_template_v2.csv"
EVIDENCE = ROOT / "evidence"
SEMANTIC = ROOT / "semantic"
FLAGS = ROOT / "review_required"
ARCHIVE = ROOT / "resolved_review_flags"
PROGRESS = ROOT / "test_annotation_progress_v2.json"
AUDIT = ROOT / "manual_adjudication_audit_v1.json"

ADJUDICATIONS = {
    "TR-C574732B12EAA1D2": {
        "OPS03-C1": (
            "POSITIVE_EVIDENCE",
            "Then I’d reconcile the two reports",
            "The candidate proposes integrating the conflicting "
            "operational reports before determining readiness."
        ),
        "OPS03-C2": (
            "POSITIVE_EVIDENCE",
            "I’d first bring both parties onto the same thread",
            "The candidate explicitly coordinates the relevant "
            "parties and subsequently identifies ownership "
            "and dependencies."
        ),
        "OPS03-C3": (
            "POSITIVE_EVIDENCE",
            "I’d document the basis for the update",
            "The candidate commits to recording the evidence "
            "supporting the readiness determination."
        ),
    },
    "TR-8C1304D89DCF3582": {
        "CSS02-C1": (
            "POSITIVE_EVIDENCE",
            "I’d ask when they noticed the discount disappear",
            "The candidate identifies relevant questions "
            "for investigating the missing promotion."
        ),
        "CSS02-C2": (
            "POSITIVE_EVIDENCE",
            "I’d check the account and order records on our side",
            "The candidate proposes checking internal records "
            "rather than accepting the screenshot as conclusive."
        ),
        "CSS02-C3": (
            "POSITIVE_EVIDENCE",
            "I wouldn’t ask for anything sensitive unless it was actually needed and allowed through our normal process.",
            "The candidate limits information collection "
            "to what is necessary and authorised."
        ),
    },
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    with TEMPLATE.open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))

    require(len(rows) == 216, "Unexpected template size")

    lookup = {
        row["blinded_response_id"]: row
        for row in rows
    }

    require(
        len(lookup) == 216,
        "Duplicate blinded IDs"
    )

    require(
        not AUDIT.exists(),
        "Audit already exists; refusing to repeat"
    )

    prepared = []


    for rid, judgments in ADJUDICATIONS.items():
        require(rid in lookup, f"Unknown response: {rid}")

        row = lookup[rid]
        output = EVIDENCE / f"{rid}.json"
        flag = FLAGS / f"{rid}.json"
        archive = ARCHIVE / flag.name

        require(
            not output.exists(),
            f"Annotation already exists: {rid}"
        )

        require(
            flag.exists(),
            f"Missing original review flag: {rid}"
        )

        require(
            not archive.exists(),
            f"Review flag already archived: {rid}"
        )

        original_flag = read_json(flag)

        require(
            original_flag["status"] == "MANUAL_REVIEW_REQUIRED",
            f"Unexpected flag status: {rid}"
        )

        require(
            len(judgments) == 3,
            f"Expected 3 judgments: {rid}"
        )

        expected = {
            row[f"criterion_{i}_id"]
            for i in (1, 2, 3)
        }

        require(
            set(judgments) == expected,
            f"Criterion IDs mismatch: {rid}"
        )

        result = {
            "criteria": [
                {
                    "criterion_id": cid,
                    "status": status,
                    "passage": passage,
                    "rationale": rationale,
                }
                for cid, (
                    status, passage, rationale
                ) in judgments.items()
            ],
            "annotation_notes": (
                "AI-assisted manual adjudication following "
                "repeated model-generated quotation-validation "
                "failures. Statuses and verbatim excerpts were "
                "assigned by explicit review of the candidate "
                "answer and rubric. Not independent human "
                "ground truth."
            ),
        }


        pilot.validate_evidence(row, result)

        prepared.append(
            (rid, output, flag, archive, result)
        )

    print("ESDSA — MANUAL ANNOTATION ADJUDICATION")
    print("=" * 65)
    print("Target responses:", len(prepared))
    print("Criterion judgments:", 6)
    print("Original evidence validator: PASSED")
    print("API requests: 0")
    print()

    completed_ids = []

    for rid, output, flag, archive, result in prepared:
        record = {
            "experiment": "ESDSA_TEST_AI_ANNOTATION_V2",
            "partition": "TEST",
            "review_type": "EVIDENCE",
            "blinded_id": rid,
            "reviewer_id": "AI_ASSISTED_MANUAL_ADJUDICATION_V1",
            "requested_model": None,
            "returned_model": None,
            "api_response_id": None,
            "annotated_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "annotation": result,
            "reference_decision": None,
            "independent_human_review": False,
            "annotation_method": (
                "EXPLICIT_AI_ASSISTED_MANUAL_ADJUDICATION"
            ),
            "prior_failure": read_json(flag),
        }

        output.parent.mkdir(
            parents=True, exist_ok=True
        )

        with output.open(
            "x", encoding="utf-8"
        ) as handle:
            json.dump(
                record, handle,
                indent=2, ensure_ascii=False
            )
            handle.write("\n")

        ARCHIVE.mkdir(
            parents=True, exist_ok=True
        )

        flag.rename(archive)
        completed_ids.append(rid)

        print("ADJUDICATED:", rid)


    status_counts = {}
    manual_count = 0

    for row in rows:
        rid = row["blinded_response_id"]
        path = EVIDENCE / f"{rid}.json"

        require(
            path.exists(),
            f"Missing evidence annotation: {rid}"
        )

        saved = read_json(path)
        pilot.validate_evidence(
            row, saved["annotation"]
        )

        if saved.get("annotation_method") == (
            "EXPLICIT_AI_ASSISTED_MANUAL_ADJUDICATION"
        ):
            manual_count += 1

        for item in saved["annotation"]["criteria"]:
            status = item["status"]
            status_counts[status] = (
                status_counts.get(status, 0) + 1
            )

    semantic_files = list(
        SEMANTIC.glob("TG-*.json")
    )

    require(
        len(semantic_files) == 72,
        "Expected 72 semantic annotations"
    )

    require(
        len(status_counts) > 0
        and sum(status_counts.values()) == 648,
        "Expected 648 validated criterion judgments"
    )

    require(
        manual_count == 2,
        "Expected precisely two manual adjudications"
    )

    require(
        not list(FLAGS.glob("TR-*.json")),
        "Unresolved evidence flags remain"
    )

    audit = {
        "experiment": "ESDSA_TEST_MANUAL_ADJUDICATION_V1",
        "method": "AI_ASSISTED_MANUAL_ADJUDICATION",
        "adjudicated_responses": completed_ids,
        "adjudicated_criterion_count": 6,
        "reason": (
            "Repeated failure of generated evidence "
            "quotations to satisfy exact substring validation."
        ),
        "original_validator_used": True,
        "model_generated_annotations_accepted": 214,
        "manually_adjudicated_annotations": 2,
        "independent_human_ground_truth": False,
        "api_requests": 0,
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    with AUDIT.open(
        "x", encoding="utf-8"
    ) as handle:
        json.dump(
            audit, handle,
            indent=2, ensure_ascii=False
        )
        handle.write("\n")

    progress = {
        "status": "COMPLETE",
        "evidence_completed": 216,
        "indicator_assessments_completed": 648,
        "semantic_completed": 72,
        "evidence_status_counts": status_counts,
        "model_accepted_evidence_annotations": 214,
        "ai_assisted_manual_adjudications": 2,
        "reference_decisions_assigned": 0,
        "independent_human_review": False,
        "test_prediction_comparison_performed": False,
        "updated_utc": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    temporary = PROGRESS.with_suffix(".json.tmp")

    temporary.write_text(
        json.dumps(
            progress, indent=2,
            ensure_ascii=False
        ) + "\n",
        encoding="utf-8"
    )

    temporary.replace(PROGRESS)

    print()
    print("=" * 65)
    print("TEST ANNOTATION: COMPLETE")
    print("Evidence annotations: 216/216")
    print("Criterion judgments: 648/648")
    print("Semantic groups: 72/72")
    print("Model-accepted evidence annotations: 214")
    print("AI-assisted manual adjudications: 2")
    print("Independent human reference: NOT ESTABLISHED")
    print("Frozen policy: NOT MODIFIED")


if __name__ == "__main__":
    main()
