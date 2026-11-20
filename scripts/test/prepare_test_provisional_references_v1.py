

"""Prepare provisional TEST references from completed AI annotations.

Reuses the frozen ESDSA v2 traceability classifier,
decision function, and validation reference stability rules.

No API calls.
No evaluator predictions loaded or compared.
No generation-condition labels used as reference decisions.
No modification of frozen policy or source annotations.

Explicitly records two AI-assisted manual adjudications.
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
import hashlib
import json

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import run_validation_annotation_pilot_v1 as pilot

ROOT = Path(__file__).resolve().parents[2]

POLICY_FILE = (
    ROOT
    / "data/benchmark/policy_freeze_v2/"
    "esdsa_v2_policy_freeze.json"
)

DATASET = (
    ROOT
    / "results/test_generation_v1/"
    "test_responses_v1.csv"
)

PREDICTION_LOCK = (
    ROOT
    / "results/test_evaluator_predictions_v1/"
    "test_predictions_lock_v1.json"
)

ANNOTATION_DIR = (
    ROOT / "results/test_ai_annotations_v2"
)

EVIDENCE_TEMPLATE = (
    ANNOTATION_DIR / "test_evidence_template_v2.csv"
)

SEMANTIC_TEMPLATE = (
    ANNOTATION_DIR / "test_semantic_template_v2.csv"
)

TEMPLATE_MANIFEST = (
    ANNOTATION_DIR
    / "test_annotation_template_manifest_v2.json"
)

PROGRESS_FILE = (
    ANNOTATION_DIR / "test_annotation_progress_v2.json"
)

ADJUDICATION_AUDIT = (
    ANNOTATION_DIR / "manual_adjudication_audit_v1.json"
)

EVIDENCE_DIR = ANNOTATION_DIR / "evidence"
SEMANTIC_DIR = ANNOTATION_DIR / "semantic"

OUT_DIR = (
    ROOT / "results/test_provisional_references_v1"
)

OUT_JSON = (
    OUT_DIR / "test_provisional_references_v1.json"
)

OUT_CSV = (
    OUT_DIR / "test_provisional_decisions_v1.csv"
)

OUT_MANIFEST = (
    OUT_DIR / "reference_preparation_manifest_v1.json"
)

ACTIONABLE = {"ADVANCE", "DO_NOT_ADVANCE"}

VALID_DECISIONS = ACTIONABLE | {"DEFER"}

FROZEN_SCRIPTS = (
    "audit_traceability_v2.py",
    "evaluate_traceability_policy_v2.py",
    "evaluate_integrated_esdsa_v2.py",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    require(path.is_file(), f"Missing file: {path}")

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def read_csv(path):
    require(path.is_file(), f"Missing file: {path}")

    with path.open(
        encoding="utf-8-sig",
        newline=""
    ) as handle:
        return list(csv.DictReader(handle))


def save_json_new(path, data):
    with path.open(
        "x",
        encoding="utf-8"
    ) as handle:
        json.dump(
            data,
            handle,
            indent=2,
            ensure_ascii=False,
        )
        handle.write("\n")


def distribution(values):
    counts = Counter(values)

    return {
        decision: counts.get(decision, 0)
        for decision in (
            "ADVANCE",
            "DO_NOT_ADVANCE",
            "DEFER",
        )
    }


def verify_frozen_policy():
    frozen = read_json(POLICY_FILE)
    policy = frozen["policy"]

    require(
        frozen["policy_version"]
        == "ESDSA-v2-development-frozen",
        "Unexpected frozen policy version",
    )

    require(
        policy["stability"]["group_size"] == 3,
        "Unexpected stability group size",
    )

    expected_hashes = frozen[
        "implementation_file_sha256"
    ]

    for name in FROZEN_SCRIPTS:
        require(
            digest(ROOT / "archive/frozen_originals" / name)
            == expected_hashes[name],
            f"Frozen implementation changed: {name}",
        )

    return frozen


def verify_prediction_lock():
    lock = read_json(PREDICTION_LOCK)

    require(
        lock["status"] == "LOCKED",
        "TEST predictions are not locked",
    )

    require(
        lock["dataset_sha256"] == digest(DATASET),
        "TEST dataset differs from prediction lock",
    )

    require(
        len(lock["prediction_files"]) == 2,
        "Expected two locked evaluator files",
    )

    for name, item in lock["prediction_files"].items():
        path = ROOT / item["file"]

        require(
            path.is_file(),
            f"Missing locked prediction file: {name}",
        )

        require(
            digest(path) == item["sha256"],
            f"Locked predictions changed: {name}",
        )

        require(
            item["records"] == 216,
            f"Incorrect locked prediction count: {name}",
        )

    return lock


def load_verified_templates():
    manifest = read_json(TEMPLATE_MANIFEST)

    require(
        manifest["status"] == "PREPARED",
        "Annotation templates not prepared",
    )

    require(
        manifest["dataset_sha256"] == digest(DATASET),
        "Annotation source dataset mismatch",
    )

    require(
        manifest["prediction_lock_sha256"]
        == digest(PREDICTION_LOCK),
        "Prediction lock differs from annotation preparation",
    )

    require(
        manifest["evidence_template_sha256"]
        == digest(EVIDENCE_TEMPLATE),
        "Evidence template has changed",
    )

    require(
        manifest["semantic_template_sha256"]
        == digest(SEMANTIC_TEMPLATE),
        "Semantic template has changed",
    )

    evidence_rows = read_csv(EVIDENCE_TEMPLATE)
    semantic_rows = read_csv(SEMANTIC_TEMPLATE)

    require(
        len(evidence_rows) == 216,
        "Expected 216 evidence templates",
    )

    require(
        len(semantic_rows) == 72,
        "Expected 72 semantic templates",
    )

    evidence_by_id = {
        row["blinded_response_id"]: row
        for row in evidence_rows
    }

    semantic_by_id = {
        row["blinded_group_id"]: row
        for row in semantic_rows
    }

    require(
        len(evidence_by_id) == 216,
        "Duplicate blinded response IDs",
    )

    require(
        len(semantic_by_id) == 72,
        "Duplicate blinded group IDs",
    )

    return evidence_by_id, semantic_by_id


def verify_annotation_completion(evidence_ids):
    progress = read_json(PROGRESS_FILE)
    audit = read_json(ADJUDICATION_AUDIT)

    require(
        progress["status"] == "COMPLETE",
        "TEST annotation stage is incomplete",
    )

    require(
        progress["evidence_completed"] == 216,
        "Expected 216 evidence annotations",
    )

    require(
        progress["indicator_assessments_completed"] == 648,
        "Expected 648 criterion judgments",
    )

    require(
        progress["semantic_completed"] == 72,
        "Expected 72 semantic annotations",
    )

    require(
        progress["model_accepted_evidence_annotations"]
        == 214,
        "Unexpected model annotation count",
    )

    require(
        progress["ai_assisted_manual_adjudications"]
        == 2,
        "Unexpected manual adjudication count",
    )

    require(
        audit["original_validator_used"] is True,
        "Manual adjudication validator not documented",
    )

    require(
        audit["adjudicated_criterion_count"] == 6,
        "Unexpected adjudicated criterion count",
    )

    adjudicated_ids = set(
        audit["adjudicated_responses"]
    )

    require(
        len(adjudicated_ids) == 2,
        "Expected exactly two manually adjudicated responses",
    )

    require(
        adjudicated_ids.issubset(evidence_ids),
        "Unknown manually adjudicated response",
    )

    require(
        not list(
            (ANNOTATION_DIR / "review_required").glob("TR-*.json")
        ),
        "Unresolved evidence review flags remain",
    )

    return progress, audit, adjudicated_ids


def validate_saved_evidence(path, rid, source, manual_ids):
    saved = read_json(path)

    require(
        saved["experiment"]
        == "ESDSA_TEST_AI_ANNOTATION_V2",
        f"Unexpected annotation experiment: {rid}",
    )

    require(
        saved["partition"] == "TEST",
        f"Non-TEST evidence annotation: {rid}",
    )

    require(
        saved["review_type"] == "EVIDENCE",
        f"Unexpected review type: {rid}",
    )

    require(
        saved["blinded_id"] == rid,
        f"Evidence annotation ID mismatch: {rid}",
    )

    require(
        saved["independent_human_review"] is False,
        f"Unexpected human-review status: {rid}",
    )

    pilot.validate_evidence(
        source,
        saved["annotation"],
    )

    is_manual = rid in manual_ids

    if is_manual:
        require(
            saved["reviewer_id"]
            == "AI_ASSISTED_MANUAL_ADJUDICATION_V1",
            f"Manual provenance mismatch: {rid}",
        )

        require(
            saved.get("annotation_method")
            == "EXPLICIT_AI_ASSISTED_MANUAL_ADJUDICATION",
            f"Missing adjudication method: {rid}",
        )

        require(
            saved["api_response_id"] is None,
            f"Manual annotation must not claim an API response: {rid}",
        )

    else:
        require(
            saved["reviewer_id"]
            == "AI_ASSISTED_GPT54_MINI_V2",
            f"Model annotation provenance mismatch: {rid}",
        )

        require(
            bool(saved["api_response_id"]),
            f"Missing original annotation API ID: {rid}",
        )

    return saved


def validate_saved_semantic(path, gid, source):
    saved = read_json(path)

    require(
        saved["experiment"]
        == "ESDSA_TEST_AI_ANNOTATION_V2",
        f"Unexpected semantic experiment: {gid}",
    )

    require(
        saved["partition"] == "TEST",
        f"Non-TEST semantic annotation: {gid}",
    )

    require(
        saved["review_type"]
        == "SEMANTIC_EQUIVALENCE",
        f"Unexpected semantic review type: {gid}",
    )

    require(
        saved["blinded_id"] == gid,
        f"Semantic annotation ID mismatch: {gid}",
    )

    require(
        saved["reviewer_id"]
        == "AI_ASSISTED_GPT54_MINI_V2",
        f"Semantic annotation provenance mismatch: {gid}",
    )

    require(
        saved["independent_human_review"] is False,
        f"Unexpected semantic human-review status: {gid}",
    )

    pilot.validate_semantic(saved["annotation"])

    return saved


def main():
    print("ESDSA — TEST PROVISIONAL REFERENCE PREPARATION")
    print("=" * 68)
    print("API requests: 0")
    print("Generation conditions: NOT USED")
    print("Blinding key: NOT ACCESSED")
    print("Locked evaluator predictions: NOT LOADED")
    print()

    for path in (
        OUT_JSON,
        OUT_CSV,
        OUT_MANIFEST,
    ):
        require(
            not path.exists(),
            f"Output already exists: {path}",
        )

    frozen = verify_frozen_policy()
    lock = verify_prediction_lock()

    evidence_by_id, semantic_by_id = (
        load_verified_templates()
    )

    progress, audit, manual_ids = (
        verify_annotation_completion(
            set(evidence_by_id)
        )
    )

    from audit_traceability_v2 import classify
    from evaluate_traceability_policy_v2 import new_decision

    records = []
    grouped = defaultdict(list)

    evidence_files = []
    semantic_files = []

    manual_count = 0

    for rid, source in sorted(
        evidence_by_id.items()
    ):
        path = EVIDENCE_DIR / f"{rid}.json"

        saved = validate_saved_evidence(
            path,
            rid,
            source,
            manual_ids,
        )

        evidence_files.append(path)

        annotated = {
            item["criterion_id"]: item
            for item in saved["annotation"]["criteria"]
        }

        require(
            len(annotated) == 3,
            f"Expected three criteria: {rid}",
        )

        criteria = []

        for number in (1, 2, 3):
            cid = source[
                f"criterion_{number}_id"
            ]

            require(
                cid in annotated,
                f"Missing criterion {cid}: {rid}",
            )

            item = annotated[cid]
            status = item["status"]
            passage = item["passage"]

            if status == "INSUFFICIENT_EVIDENCE":
                outcome = "NOT_APPLICABLE"
                reason = "insufficient_evidence"

            else:
                outcome, reason = classify(
                    passage,
                    source["answer"],
                    source["interview_question"],
                )

                require(
                    outcome == "VERIFIED",
                    "Supporting passage failed frozen "
                    f"traceability: {rid}, {cid} "
                    f"({outcome}: {reason})",
                )

            criteria.append({
                "criterion_id": cid,
                "evidence_status": status,
                "excerpt": passage,
                "rationale": item["rationale"],
                "v2_outcome": outcome,
                "v2_reason": reason,
            })

        decision, decision_reason = (
            new_decision(criteria)
        )

        require(
            decision in VALID_DECISIONS,
            f"Invalid reference decision: {rid}",
        )

        manual = rid in manual_ids

        if manual:
            manual_count += 1

        record = {
            "blinded_response_id": rid,
            "blinded_group_id": source[
                "blinded_group_id"
            ],
            "family_id": source["family_id"],
            "competency_code": source[
                "competency_code"
            ],
            "provisional_evidence_decision": decision,
            "decision_reason": decision_reason,
            "semantic_equivalence": None,
            "provisional_integrated_decision": None,
            "stability_gate_reason": None,
            "criteria": criteria,
            "annotation_provenance": saved["reviewer_id"],
            "manual_adjudication": manual,
            "independent_human_reference": False,
        }

        records.append(record)

        grouped[
            record["blinded_group_id"]
        ].append(record)

    require(
        len(records) == 216,
        "Incorrect evidence reference count",
    )

    require(
        len(grouped) == 72,
        "Incorrect reference group count",
    )

    require(
        manual_count == 2,
        "Manual annotation attribution mismatch",
    )

    group_diagnostics = []

    for gid, members in sorted(grouped.items()):
        require(
            gid in semantic_by_id,
            f"Missing semantic template: {gid}",
        )

        require(
            len(members) == 3,
            f"Expected three group members: {gid}",
        )

        source = semantic_by_id[gid]
        path = SEMANTIC_DIR / f"{gid}.json"

        saved = validate_saved_semantic(
            path,
            gid,
            source,
        )

        semantic_files.append(path)

        equivalence = saved[
            "annotation"
        ]["semantic_equivalence"]

        pre_decisions = [
            member["provisional_evidence_decision"]
            for member in members
        ]


        if equivalence == "YES":

            unanimous_actionable = (
                len(set(pre_decisions)) == 1
                and pre_decisions[0] in ACTIONABLE
            )

            if unanimous_actionable:
                for member in members:
                    member["provisional_integrated_decision"] = (
                        member["provisional_evidence_decision"]
                    )

                    member["stability_gate_reason"] = (
                        "EQUIVALENT_UNANIMOUS_ACTIONABLE"
                    )

            else:
                for member in members:
                    member["provisional_integrated_decision"] = (
                        "DEFER"
                    )

                    member["stability_gate_reason"] = (
                        "EQUIVALENT_GROUP_NOT_UNANIMOUS"
                    )

        elif equivalence in {"NO", "UNCERTAIN"}:

            for member in members:
                member["provisional_integrated_decision"] = (
                    member["provisional_evidence_decision"]
                )

                member["stability_gate_reason"] = (
                    "STABILITY_NOT_ASSESSED_NON_EQUIVALENT"
                    if equivalence == "NO"
                    else "STABILITY_NOT_ASSESSED_UNCERTAIN"
                )

        else:
            raise ValueError(
                f"Unexpected semantic status: {gid}: "
                f"{equivalence}"
            )

        for member in members:
            member["semantic_equivalence"] = equivalence

        newly_deferred = sum(
            member["provisional_evidence_decision"]
            in ACTIONABLE
            and member["provisional_integrated_decision"]
            == "DEFER"
            for member in members
        )

        group_diagnostics.append({
            "blinded_group_id": gid,
            "family_id": source["family_id"],
            "semantic_equivalence": equivalence,
            "equivalence_rationale": saved[
                "annotation"
            ]["equivalence_rationale"],
            "material_differences": saved[
                "annotation"
            ]["material_differences"],
            "pre_stability_decisions": pre_decisions,
            "post_stability_decisions": [
                member["provisional_integrated_decision"]
                for member in members
            ],
            "newly_deferred_by_stability": newly_deferred,
            "contains_manual_adjudication": any(
                member["manual_adjudication"]
                for member in members
            ),
        })

    pre = distribution(
        record["provisional_evidence_decision"]
        for record in records
    )

    post = distribution(
        record["provisional_integrated_decision"]
        for record in records
    )

    equivalence_counts = Counter(
        group["semantic_equivalence"]
        for group in group_diagnostics
    )

    newly_deferred = sum(
        group["newly_deferred_by_stability"]
        for group in group_diagnostics
    )

    summary = {
        "responses": 216,
        "indicator_assessments": 648,
        "semantic_groups": 72,
        "model_accepted_evidence_annotations": 214,
        "ai_assisted_manual_adjudications": 2,
        "manual_adjudicated_indicator_judgments": 6,
        "pre_stability_distribution": pre,
        "post_stability_distribution": post,
        "pre_stability_actionable_coverage": (
            (
                pre["ADVANCE"]
                + pre["DO_NOT_ADVANCE"]
            ) / 216
        ),
        "post_stability_actionable_coverage": (
            (
                post["ADVANCE"]
                + post["DO_NOT_ADVANCE"]
            ) / 216
        ),
        "semantic_equivalence_distribution": {
            value: equivalence_counts.get(value, 0)
            for value in (
                "YES",
                "NO",
                "UNCERTAIN",
            )
        },
        "newly_deferred_by_stability": newly_deferred,
        "reference_status": (
            "AI-assisted provisional annotations, "
            "including two explicitly recorded manual "
            "adjudications; not independently "
            "adjudicated human ground truth."
        ),
        "esdsa_predictions_evaluated": False,
        "model_disagreements_measured": False,
    }

    require(
        sum(pre.values()) == 216,
        "Incorrect pre-stability distribution",
    )

    require(
        sum(post.values()) == 216,
        "Incorrect post-stability distribution",
    )

    require(
        sum(equivalence_counts.values()) == 72,
        "Incorrect semantic distribution",
    )

    require(
        (
            pre["ADVANCE"]
            + pre["DO_NOT_ADVANCE"]
            - post["ADVANCE"]
            - post["DO_NOT_ADVANCE"]
        ) == newly_deferred,
        "Stability attribution mismatch",
    )

    report = {
        "stage": "test_provisional_reference_preparation",
        "policy_version": frozen["policy_version"],
        "summary": summary,
        "group_diagnostics": group_diagnostics,
        "all_records": records,
        "limitations": [
            "Reference decisions are derived from AI-assisted annotations.",
            "These are not independent human ground-truth labels.",
            "The same model family generated candidate responses "
            "and most provisional evidence annotations.",
            "Two evidence annotations were completed through "
            "explicit AI-assisted manual adjudication after "
            "repeated quotation-validation failures.",
            "The original annotation instructions were developed "
            "and revised during the validation phase.",
            "TEST scenario questions were authored after "
            "validation results had been examined.",
            "Verbatim quotation verification does not establish "
            "the substantive correctness of evidence judgments.",
            "Semantic-equivalence annotations are also AI-assisted.",
            "The provisional post-stability references reuse "
            "the frozen stability rule and are not independent "
            "of that decision mechanism.",
            "No locked evaluator predictions have been compared "
            "in this reference preparation stage.",
            "The reference decisions must not be described "
            "as independently measured hiring accuracy.",
        ],
    }

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    csv_fields = [
        "blinded_response_id",
        "blinded_group_id",
        "family_id",
        "competency_code",
        "provisional_evidence_decision",
        "provisional_integrated_decision",
        "semantic_equivalence",
        "stability_gate_reason",
        "annotation_provenance",
        "manual_adjudication",
        "independent_human_reference",
    ]

    with OUT_CSV.open(
        "x",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=csv_fields,
        )

        writer.writeheader()

        for record in records:
            writer.writerow({
                field: record[field]
                for field in csv_fields
            })

    save_json_new(OUT_JSON, report)

    manifest = {
        "stage": "TEST_PROVISIONAL_REFERENCE_PREPARATION",
        "status": "COMPLETE",
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "frozen_policy_sha256": digest(POLICY_FILE),
        "frozen_implementation_sha256": {
            name: frozen[
                "implementation_file_sha256"
            ][name]
            for name in FROZEN_SCRIPTS
        },
        "source_dataset_sha256": digest(DATASET),
        "prediction_lock_sha256": digest(
            PREDICTION_LOCK
        ),
        "source_progress_sha256": digest(
            PROGRESS_FILE
        ),
        "manual_adjudication_audit_sha256": digest(
            ADJUDICATION_AUDIT
        ),
        "input_evidence_file_count": len(
            evidence_files
        ),
        "input_semantic_file_count": len(
            semantic_files
        ),
        "evidence_annotation_hashes": {
            path.name: digest(path)
            for path in sorted(evidence_files)
        },
        "semantic_annotation_hashes": {
            path.name: digest(path)
            for path in sorted(semantic_files)
        },
        "output_sha256": {
            OUT_JSON.name: digest(OUT_JSON),
            OUT_CSV.name: digest(OUT_CSV),
        },
        "api_requests": 0,
        "evaluator_predictions_loaded": False,
        "evaluator_predictions_compared": False,
        "blinding_key_accessed": False,
        "independent_reference_validation": False,
    }

    save_json_new(OUT_MANIFEST, manifest)

    print("TEST REFERENCE PREPARATION: PASSED")
    print()
    print("Responses:", summary["responses"])
    print(
        "Indicator assessments:",
        summary["indicator_assessments"],
    )
    print(
        "Semantic groups:",
        summary["semantic_groups"],
    )

    print()
    print(
        "Pre-stability decisions:",
        summary["pre_stability_distribution"],
    )
    print(
        "Post-stability decisions:",
        summary["post_stability_distribution"],
    )
    print(
        "Semantic equivalence:",
        summary["semantic_equivalence_distribution"],
    )
    print(
        "Newly deferred by stability:",
        newly_deferred,
    )

    print()
    print(
        "Model-accepted annotations:",
        summary["model_accepted_evidence_annotations"],
    )
    print(
        "Manual adjudications:",
        summary["ai_assisted_manual_adjudications"],
    )

    print()
    print("Saved:")
    print(OUT_JSON.relative_to(ROOT))
    print(OUT_CSV.relative_to(ROOT))
    print(OUT_MANIFEST.relative_to(ROOT))

    print()
    print("API requests: 0")
    print("Locked evaluator predictions: NOT COMPARED")
    print("Independent human ground truth: NOT ESTABLISHED")
    print("Frozen policy: NOT MODIFIED")


if __name__ == "__main__":
    main()
