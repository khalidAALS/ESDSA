

"""Prepare provisional VALIDATION decisions from completed AI annotations.

No API calls. No TEST access. No ESDSA model inference.
Uses the frozen traceability classifier and decision function.
Preserves the frozen ESDSA policy and all source files.
"""

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
from datetime import datetime, timezone
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]

POLICY_FILE = (
    ROOT
    / "data/benchmark/policy_freeze_v2/esdsa_v2_policy_freeze.json"
)
ANNOTATION_DIR = ROOT / "results/validation_ai_annotations_v2"
EVIDENCE_DIR = ANNOTATION_DIR / "evidence"
SEMANTIC_DIR = ANNOTATION_DIR / "semantic"
PROGRESS_FILE = ANNOTATION_DIR / "annotation_progress_v2.json"

OUT_DIR = ROOT / "results/validation_provisional_references_v1"
OUT_JSON = OUT_DIR / "validation_provisional_references_v1.json"
OUT_CSV = OUT_DIR / "validation_provisional_decisions_v1.csv"
OUT_MANIFEST = OUT_DIR / "reference_preparation_manifest_v1.json"

VALID_DECISIONS = {"ADVANCE", "DO_NOT_ADVANCE", "DEFER"}
ACTIONABLE = {"ADVANCE", "DO_NOT_ADVANCE"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    require(path.is_file(), f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def distribution(values):
    counts = Counter(values)
    return {
        value: counts.get(value, 0)
        for value in ("ADVANCE", "DO_NOT_ADVANCE", "DEFER")
    }


def main():
    print("ESDSA — VALIDATION PROVISIONAL REFERENCE PREPARATION")
    print("=" * 68)
    print("API requests: 0")
    print("Blinding key: NOT ACCESSED")
    print("ESDSA model inference: NOT RUN")
    print("TEST partition: NOT ACCESSED")
    print()

    for path in (OUT_JSON, OUT_CSV, OUT_MANIFEST):
        require(
            not path.exists(),
            f"Output already exists; refusing overwrite: {path}"
        )

    frozen = read_json(POLICY_FILE)
    policy = frozen["policy"]

    require(
        frozen["policy_version"] == "ESDSA-v2-development-frozen",
        "Unexpected frozen policy version"
    )

    require(
        policy["stability"]["group_size"] == 3,
        "Unexpected stability group size"
    )


    frozen_hashes = frozen["implementation_file_sha256"]

    scripts = [
        "audit_traceability_v2.py",
        "evaluate_traceability_policy_v2.py",
        "evaluate_integrated_esdsa_v2.py",
    ]

    for name in scripts:
        actual = digest(ROOT / "archive/frozen_originals" / name)
        expected = frozen_hashes[name]

        require(
            actual == expected,
            f"Frozen implementation has changed: {name}"
        )

    from audit_traceability_v2 import classify
    from evaluate_traceability_policy_v2 import new_decision


    import run_validation_annotation_pilot_v1 as pilot
    import run_validation_annotations_v2 as annotation_v2

    evidence_rows, semantic_rows, by_group = (
        pilot.verify_inputs()
    )

    progress = read_json(PROGRESS_FILE)

    require(
        progress.get("status") == "COMPLETE",
        "Annotation stage not marked complete"
    )
    require(
        progress.get("evidence_completed") == 216,
        "Expected 216 evidence annotations"
    )
    require(
        progress.get("semantic_completed") == 72,
        "Expected 72 semantic assessments"
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
        "Duplicate evidence IDs"
    )
    require(
        len(semantic_by_id) == 72,
        "Duplicate semantic group IDs"
    )

    records = []
    group_records = defaultdict(list)
    evidence_files = []
    semantic_files = []

    for rid, source in sorted(evidence_by_id.items()):
        path = EVIDENCE_DIR / f"{rid}.json"

        annotation_v2.validate_saved(
            path, "EVIDENCE", rid, source
        )

        saved = read_json(path)
        evidence_files.append(path)

        criteria = []

        annotated = {
            item["criterion_id"]: item
            for item in saved["annotation"]["criteria"]
        }

        require(
            len(annotated) == 3,
            f"Expected three distinct criteria: {rid}"
        )

        for number in (1, 2, 3):
            cid = source[f"criterion_{number}_id"]
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
                    f"Unverified supporting passage: {rid}, {cid}"
                )

            criteria.append({
                "criterion_id": cid,
                "evidence_status": status,
                "excerpt": passage,
                "rationale": item["rationale"],
                "v2_outcome": outcome,
                "v2_reason": reason,
            })


        decision, decision_reason = new_decision(criteria)

        require(
            decision in VALID_DECISIONS,
            f"Invalid decision: {rid}"
        )

        group_id = source["blinded_group_id"]

        record = {
            "blinded_response_id": rid,
            "blinded_group_id": group_id,
            "family_id": source["family_id"],
            "competency_code": source["competency_code"],
            "provisional_evidence_decision": decision,
            "decision_reason": decision_reason,
            "semantic_equivalence": None,
            "provisional_integrated_decision": None,
            "stability_gate_reason": None,
            "criteria": criteria,
            "annotation_provenance": saved["reviewer_id"],
            "independent_human_reference": False,
        }

        records.append(record)
        group_records[group_id].append(record)

    require(len(records) == 216, "Incorrect record count")
    require(
        len(group_records) == 72,
        "Incorrect group count"
    )

    group_diagnostics = []

    for gid, members in sorted(group_records.items()):
        require(
            gid in semantic_by_id,
            f"Unknown semantic group: {gid}"
        )
        require(
            len(members) == 3,
            f"Group does not contain three responses: {gid}"
        )

        source = semantic_by_id[gid]
        path = SEMANTIC_DIR / f"{gid}.json"

        annotation_v2.validate_saved(
            path,
            "SEMANTIC_EQUIVALENCE",
            gid,
            source,
        )

        saved = read_json(path)
        semantic_files.append(path)

        equivalence = saved["annotation"]["semantic_equivalence"]

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
                f"Invalid equivalence: {gid}: {equivalence}"
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
            "equivalence_rationale": saved["annotation"][
                "equivalence_rationale"
            ],
            "material_differences": saved["annotation"][
                "material_differences"
            ],
            "pre_stability_decisions": pre_decisions,
            "post_stability_decisions": [
                m["provisional_integrated_decision"]
                for m in members
            ],
            "newly_deferred_by_stability": newly_deferred,
        })

    pre = distribution(
        r["provisional_evidence_decision"] for r in records
    )
    post = distribution(
        r["provisional_integrated_decision"] for r in records
    )

    equiv_counts = Counter(
        g["semantic_equivalence"]
        for g in group_diagnostics
    )

    newly_deferred = sum(
        g["newly_deferred_by_stability"]
        for g in group_diagnostics
    )

    summary = {
        "responses": 216,
        "indicator_assessments": 648,
        "semantic_groups": 72,
        "pre_stability_distribution": pre,
        "post_stability_distribution": post,
        "pre_stability_actionable_coverage": (
            (pre["ADVANCE"] + pre["DO_NOT_ADVANCE"]) / 216
        ),
        "post_stability_actionable_coverage": (
            (post["ADVANCE"] + post["DO_NOT_ADVANCE"]) / 216
        ),
        "semantic_equivalence_distribution": {
            value: equiv_counts.get(value, 0)
            for value in ("YES", "NO", "UNCERTAIN")
        },
        "newly_deferred_by_stability": newly_deferred,
        "reference_status": (
            "AI-assisted provisional annotations, "
            "not independently adjudicated ground truth"
        ),
        "esdsa_predictions_evaluated": False,
        "model_disagreements_measured": False,
    }

    require(
        sum(pre.values()) == 216,
        "Pre-stability distribution mismatch"
    )
    require(
        sum(post.values()) == 216,
        "Post-stability distribution mismatch"
    )
    require(
        sum(equiv_counts.values()) == 72,
        "Semantic group distribution mismatch"
    )

    require(
        (pre["ADVANCE"] + pre["DO_NOT_ADVANCE"])
        - (post["ADVANCE"] + post["DO_NOT_ADVANCE"])
        == newly_deferred,
        "Stability attribution mismatch"
    )

    report = {
        "stage": "validation_provisional_reference_preparation",
        "policy_version": frozen["policy_version"],
        "summary": summary,
        "group_diagnostics": group_diagnostics,
        "all_records": records,
        "limitations": [
            "These decisions are derived from AI annotations.",
            "They are not independent reference decisions.",
            "The same model family generated the candidate "
            "responses and provisional annotations.",
            "Annotation instructions were revised after "
            "examining a validation pilot.",
            "Textual verification does not establish "
            "substantive correctness.",
            "No separate ESDSA evaluator predictions "
            "are included in this analysis.",
            "This is not a held-out accuracy estimate.",
            "TEST has not been accessed.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_fields = [
        "blinded_response_id",
        "blinded_group_id",
        "family_id",
        "competency_code",
        "provisional_evidence_decision",
        "provisional_integrated_decision",
        "semantic_equivalence",
        "stability_gate_reason",
        "independent_human_reference",
    ]

    with OUT_CSV.open(
        "x", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=csv_fields
        )
        writer.writeheader()

        for record in records:
            writer.writerow({
                key: record[key] for key in csv_fields
            })

    save_json(OUT_JSON, report)

    manifest = {
        "stage": "VALIDATION_PROVISIONAL_REFERENCE_PREPARATION",
        "status": "COMPLETE",
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "frozen_policy_sha256": digest(POLICY_FILE),
        "frozen_implementation_sha256": {
            name: frozen_hashes[name] for name in scripts
        },
        "source_progress_sha256": digest(PROGRESS_FILE),
        "input_evidence_file_count": len(evidence_files),
        "input_semantic_file_count": len(semantic_files),
        "evidence_annotation_hashes": {
            p.name: digest(p) for p in sorted(evidence_files)
        },
        "semantic_annotation_hashes": {
            p.name: digest(p) for p in sorted(semantic_files)
        },
        "output_sha256": {
            OUT_JSON.name: digest(OUT_JSON),
            OUT_CSV.name: digest(OUT_CSV),
        },
        "api_requests": 0,
        "esdsa_inference": False,
        "independent_reference_validation": False,
        "test_partition_accessed": False,
    }

    save_json(OUT_MANIFEST, manifest)

    print("REFERENCE PREPARATION: PASSED")
    print()
    print("Responses:", summary["responses"])
    print(
        "Indicator assessments:",
        summary["indicator_assessments"]
    )
    print("Semantic groups:", summary["semantic_groups"])
    print()
    print(
        "Pre-stability decisions:",
        summary["pre_stability_distribution"]
    )
    print(
        "Post-stability decisions:",
        summary["post_stability_distribution"]
    )
    print(
        "Semantic equivalence:",
        summary["semantic_equivalence_distribution"]
    )
    print(
        "Newly deferred by stability:",
        summary["newly_deferred_by_stability"]
    )
    print()
    print("Saved:")
    print(OUT_JSON.relative_to(ROOT))
    print(OUT_CSV.relative_to(ROOT))
    print(OUT_MANIFEST.relative_to(ROOT))
    print()
    print("No independent ground truth established.")
    print("No ESDSA model predictions evaluated.")
    print("TEST partition: NOT ACCESSED")


if __name__ == "__main__":
    main()
