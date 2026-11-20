
"""Consolidated ESDSA v2 VALIDATION analysis.

No API requests, no evaluator inference, no policy changes,
and no TEST access.

Compares completed predictions with AI-assisted provisional
reference decisions. Does not claim independent ground truth.
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

from audit_traceability_v2 import classify
from evaluate_traceability_policy_v2 import new_decision


ROOT = Path(__file__).resolve().parents[2]

PRED = ROOT / "results/validation_evaluator_predictions_v1"
REF = ROOT / "results/validation_provisional_references_v1"
TEMPLATES = ROOT / "results/validation_annotation_templates_v1"

POLICY = (
    ROOT / "data/benchmark/policy_freeze_v2/"
    "esdsa_v2_policy_freeze.json"
)

EVIDENCE = PRED / "evidence_aware_validation_v1.jsonl"
SCORING = PRED / "scoring_only_validation_v1.jsonl"

REFERENCES = REF / "validation_provisional_references_v1.json"
KEY = TEMPLATES / "validation_annotation_blinding_key_v1.csv"
DATASET = (
    ROOT / "results/validation_consolidated_v1/"
    "validation_responses_v1.csv"
)
SCENARIOS = ROOT / "data/benchmark/validation_scenarios_v2.csv"

OUT_DIR = ROOT / "results/validation_esdsa_v2_analysis"
OUT_JSON = OUT_DIR / "validation_esdsa_v2_results.json"
OUT_CSV = OUT_DIR / "validation_esdsa_v2_records.csv"
OUT_TXT = OUT_DIR / "validation_esdsa_v2_summary.txt"
OUT_MANIFEST = OUT_DIR / "validation_esdsa_v2_manifest.json"

ACTIONABLE = {"ADVANCE", "DO_NOT_ADVANCE"}
DECISIONS = ACTIONABLE | {"DEFER"}


def check(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    check(path.is_file(), f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path):
    check(path.is_file(), f"Missing file: {path}")

    with path.open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path):
    check(path.is_file(), f"Missing file: {path}")
    records = {}

    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue

            item = json.loads(line)
            rid = item["response_id"]

            check(
                rid not in records,
                f"Duplicate prediction: {rid}"
            )
            check(
                item["partition"] == "VALIDATION",
                f"Non-validation prediction: {rid}"
            )

            records[rid] = item

    check(
        len(records) == 216,
        f"Expected 216 predictions in {path.name}; "
        f"found {len(records)}"
    )

    return records


def metrics(records, field, reference_field):
    actionable = [
        row for row in records
        if row[field] in ACTIONABLE
    ]

    disagreements = [
        row for row in actionable
        if row[field] != row[reference_field]
    ]

    counts = Counter(row[field] for row in records)

    return {
        "total": len(records),
        "actionable": len(actionable),
        "coverage": len(actionable) / len(records),
        "deferrals": counts["DEFER"],
        "deferral_rate": counts["DEFER"] / len(records),
        "disagreements": len(disagreements),
        "disagreement_rate": (
            len(disagreements) / len(actionable)
            if actionable else None
        ),
        "unsupported_advances_provisional": sum(
            row[field] == "ADVANCE"
            and row[reference_field] != "ADVANCE"
            for row in records
        ),
        "deferrals_against_actionable_reference": sum(
            row[field] == "DEFER"
            and row[reference_field] in ACTIONABLE
            for row in records
        ),
        "distribution": {
            name: counts[name]
            for name in (
                "ADVANCE", "DO_NOT_ADVANCE", "DEFER"
            )
        },
    }


def main():
    print("ESDSA V2 — CONSOLIDATED VALIDATION ANALYSIS")
    print("=" * 68)
    print("API requests: 0")
    print("Frozen policy: NOT MODIFIED")
    print("TEST partition: NOT ACCESSED")
    print()

    outputs = [
        OUT_JSON, OUT_CSV, OUT_TXT, OUT_MANIFEST
    ]

    for path in outputs:
        check(
            not path.exists(),
            f"Refusing to overwrite existing result: {path}"
        )

    frozen = read_json(POLICY)

    check(
        frozen["policy_version"]
        == "ESDSA-v2-development-frozen",
        "Unexpected policy version"
    )

    for name in (
        "audit_traceability_v2.py",
        "evaluate_traceability_policy_v2.py",
        "evaluate_integrated_esdsa_v2.py",
    ):
        expected = frozen["implementation_file_sha256"][name]

        check(
            sha256(ROOT / "archive/frozen_originals" / name) == expected,
            f"Frozen implementation modified: {name}"
        )

    evidence = read_jsonl(EVIDENCE)
    scoring = read_jsonl(SCORING)

    source_rows = read_csv(DATASET)
    scenarios = read_csv(SCENARIOS)

    check(len(source_rows) == 216, "Dataset size mismatch")
    check(len(scenarios) == 24, "Scenario count mismatch")

    source = {
        row["response_id"]: row
        for row in source_rows
    }

    scenario_by_family = {
        row["family_id"]: row
        for row in scenarios
    }

    check(len(source) == 216, "Duplicate source responses")
    check(
        len(scenario_by_family) == 24,
        "Duplicate scenario families"
    )

    check(
        set(evidence) == set(source)
        and set(scoring) == set(source),
        "Prediction IDs do not match dataset IDs"
    )

    reference_report = read_json(REFERENCES)
    provisional = reference_report["all_records"]

    check(
        len(provisional) == 216,
        "Provisional reference count mismatch"
    )

    reference_by_blinded_id = {
        row["blinded_response_id"]: row
        for row in provisional
    }

    check(
        len(reference_by_blinded_id) == 216,
        "Duplicate blinded references"
    )

    key_rows = read_csv(KEY)

    check(len(key_rows) == 216, "Blinding key mismatch")

    original_to_blinded = {}
    original_to_group = {}

    for row in key_rows:
        rid = row["original_response_id"]

        check(
            rid not in original_to_blinded,
            f"Duplicate blinding mapping: {rid}"
        )

        original_to_blinded[rid] = (
            row["blinded_response_id"]
        )
        original_to_group[rid] = (
            row["blinded_group_id"]
        )

    check(
        set(original_to_blinded) == set(source),
        "Blinding key does not match dataset"
    )

    records = []
    groups = defaultdict(list)
    citation_counts = Counter()

    for rid in sorted(source):
        input_row = source[rid]
        family = input_row["family_id"]

        question = scenario_by_family[
            family
        ]["interview_question"]

        prediction = evidence[rid]
        baseline = scoring[rid]

        check(
            prediction["answer_sha256"]
            == input_row["answer_sha256"],
            f"Evidence answer hash mismatch: {rid}"
        )

        check(
            baseline["answer_sha256"]
            == input_row["answer_sha256"],
            f"Scoring answer hash mismatch: {rid}"
        )

        check(
            prediction["rubric_id"]
            == scenario_by_family[family]["rubric_id"],
            f"Evidence rubric mismatch: {rid}"
        )

        check(
            baseline["rubric_id"]
            == scenario_by_family[family]["rubric_id"],
            f"Scoring rubric mismatch: {rid}"
        )

        for result in (prediction, baseline):
            check(
                result["requested_model"] == "gpt-5.4-mini",
                f"Unexpected requested model: {rid}"
            )

        blinded_id = original_to_blinded[rid]
        group_id = original_to_group[rid]

        ref = reference_by_blinded_id[blinded_id]

        check(
            ref["blinded_group_id"] == group_id,
            f"Reference group mismatch: {rid}"
        )

        check(
            ref["family_id"] == family,
            f"Reference family mismatch: {rid}"
        )

        check(
            len(ref["criteria"]) == 3,
            f"Reference criteria mismatch: {rid}"
        )

        audited_criteria = []

        model_criteria = prediction[
            "parsed_output"
        ]["criteria"]

        check(
            len(model_criteria) == 3,
            f"Model criteria mismatch: {rid}"
        )

        expected_criterion_ids = {
            item["criterion_id"]
            for item in ref["criteria"]
        }

        observed_ids = set()

        for criterion in model_criteria:
            cid = criterion["criterion_id"]
            status = criterion["evidence_status"]
            excerpt = criterion["supporting_excerpt"]

            check(
                cid in expected_criterion_ids
                and cid not in observed_ids,
                f"Invalid model criterion: {rid}, {cid}"
            )

            observed_ids.add(cid)

            check(
                status in (
                    "POSITIVE_EVIDENCE",
                    "NEGATIVE_EVIDENCE",
                    "INSUFFICIENT_EVIDENCE",
                ),
                f"Invalid evidence status: {rid}, {cid}"
            )

            if status == "INSUFFICIENT_EVIDENCE":
                outcome = "NOT_APPLICABLE"
                reason = "insufficient_evidence"
            else:
                outcome, reason = classify(
                    excerpt,
                    input_row["answer"],
                    question,
                )

                citation_counts[outcome] += 1

            audited_criteria.append({
                "criterion_id": cid,
                "evidence_status": status,
                "v2_outcome": outcome,
                "v2_reason": reason,
                "excerpt": excerpt,
                "explanation": criterion["explanation"],
            })

        check(
            observed_ids == expected_criterion_ids,
            f"Incomplete model criteria: {rid}"
        )

        # Frozen traceability decision function.
        traceability_decision, traceability_reason = (
            new_decision(audited_criteria)
        )

        evidence_decision = prediction["decision"]
        scoring_decision = baseline["decision"]

        for name in (
            traceability_decision,
            evidence_decision,
            scoring_decision,
        ):
            check(
                name in DECISIONS,
                f"Unexpected decision: {rid}, {name}"
            )

        pre_reference = ref[
            "provisional_evidence_decision"
        ]
        post_reference = ref[
            "provisional_integrated_decision"
        ]

        check(
            pre_reference in DECISIONS
            and post_reference in DECISIONS,
            f"Invalid provisional reference: {rid}"
        )

        record = {
            "response_id": rid,
            "family_id": family,
            "competency_code": (
                scenario_by_family[family]["competency_code"]
            ),
            "group": group_id,
            "scoring_only_decision": scoring_decision,
            "evidence_aware_decision": evidence_decision,
            "traceability_v2_decision": (
                traceability_decision
            ),
            "traceability_v2_reason": (
                traceability_reason
            ),
            "integrated_v2_decision": None,
            "stability_gate_reason": None,
            "semantic_equivalence": (
                ref["semantic_equivalence"]
            ),
            "provisional_reference_pre": pre_reference,
            "provisional_reference_post": post_reference,
            "model_criteria": audited_criteria,
        }

        records.append(record)
        groups[group_id].append(record)

    check(len(groups) == 72, "Expected 72 variant groups")

    group_diagnostics = []

    for gid, members in sorted(groups.items()):
        check(
            len(members) == 3,
            f"Invalid group size: {gid}"
        )

        equivalences = {
            member["semantic_equivalence"]
            for member in members
        }

        check(
            len(equivalences) == 1,
            f"Inconsistent equivalence: {gid}"
        )

        equivalence = next(iter(equivalences))

        decisions = [
            member["traceability_v2_decision"]
            for member in members
        ]

        if equivalence == "YES":
            unanimous_actionable = (
                len(set(decisions)) == 1
                and decisions[0] in ACTIONABLE
            )

            if unanimous_actionable:
                for member in members:
                    member["integrated_v2_decision"] = (
                        member["traceability_v2_decision"]
                    )
                    member["stability_gate_reason"] = (
                        "EQUIVALENT_UNANIMOUS_ACTIONABLE"
                    )
            else:
                for member in members:
                    member["integrated_v2_decision"] = "DEFER"
                    member["stability_gate_reason"] = (
                        "EQUIVALENT_GROUP_NOT_UNANIMOUS"
                    )

        elif equivalence in ("NO", "UNCERTAIN"):
            for member in members:
                member["integrated_v2_decision"] = (
                    member["traceability_v2_decision"]
                )
                member["stability_gate_reason"] = (
                    "STABILITY_NOT_ASSESSED_NON_EQUIVALENT"
                    if equivalence == "NO"
                    else "STABILITY_NOT_ASSESSED_UNCERTAIN"
                )

        else:
            raise ValueError(
                f"Unknown equivalence: {gid}, {equivalence}"
            )

        group_diagnostics.append({
            "group": gid,
            "semantic_equivalence": equivalence,
            "traceability_decisions": decisions,
            "integrated_decisions": [
                item["integrated_v2_decision"]
                for item in members
            ],
            "newly_deferred": sum(
                member["traceability_v2_decision"]
                in ACTIONABLE
                and member["integrated_v2_decision"] == "DEFER"
                for member in members
            ),
        })

    stages = (
        "scoring_only_decision",
        "evidence_aware_decision",
        "traceability_v2_decision",
        "integrated_v2_decision",
    )


    metrics_pre = {
        stage: metrics(
            records,
            stage,
            "provisional_reference_pre",
        )
        for stage in stages
    }


    metrics_post = {
        stage: metrics(
            records,
            stage,
            "provisional_reference_post",
        )
        for stage in stages
    }

    stability_changes = [
        record for record in records
        if record["traceability_v2_decision"]
        != record["integrated_v2_decision"]
    ]

    stability_attribution = {
        "changed_responses": len(stability_changes),
        "newly_deferred": sum(
            record["traceability_v2_decision"]
            in ACTIONABLE
            and record["integrated_v2_decision"] == "DEFER"
            for record in stability_changes
        ),
        "prevented_provisional_disagreements": sum(
            record["traceability_v2_decision"]
            in ACTIONABLE
            and record["traceability_v2_decision"]
            != record["provisional_reference_pre"]
            and record["integrated_v2_decision"] == "DEFER"
            for record in stability_changes
        ),
        "deferred_provisionally_supported_decisions": sum(
            record["traceability_v2_decision"]
            in ACTIONABLE
            and record["traceability_v2_decision"]
            == record["provisional_reference_pre"]
            and record["integrated_v2_decision"] == "DEFER"
            for record in stability_changes
        ),
    }

    report = {
        "stage": "VALIDATION",
        "policy_version": frozen["policy_version"],
        "reference_status": (
            "AI-assisted provisional, not independent ground truth"
        ),
        "main_metrics_against_pre_stability_reference": (
            metrics_pre
        ),
        "sensitivity_metrics_against_post_stability_reference": (
            metrics_post
        ),
        "citation_outcomes": dict(citation_counts),
        "stability_attribution": stability_attribution,
        "group_diagnostics": group_diagnostics,
        "records": records,
        "limitations": [
            "All references are AI-assisted and provisional.",
            "The candidate responses and annotations used the "
            "same model family.",
            "Reference annotation instructions were revised "
            "after inspecting a subset of validation data.",
            "Semantic equivalence assessments are shared "
            "between the integrated evaluator and reference "
            "construction, creating methodological dependence.",
            "Verified quotation matching is not proof that "
            "an evidence classification is substantively correct.",
            "Disagreement rates are not independently validated "
            "error rates.",
            "The 216 responses are clustered within 24 "
            "scenario families and are not independent samples.",
            "No TEST records are accessed.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    fields = [
        "response_id",
        "family_id",
        "competency_code",
        "group",
        "scoring_only_decision",
        "evidence_aware_decision",
        "traceability_v2_decision",
        "integrated_v2_decision",
        "semantic_equivalence",
        "stability_gate_reason",
        "provisional_reference_pre",
        "provisional_reference_post",
    ]

    with OUT_CSV.open(
        "x", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
        )
        writer.writeheader()

        for record in records:
            writer.writerow({
                key: record[key]
                for key in fields
            })

    with OUT_JSON.open("x", encoding="utf-8") as handle:
        json.dump(
            report,
            handle,
            indent=2,
            ensure_ascii=False,
        )

    lines = [
        "ESDSA V2 — VALIDATION RESULTS",
        "",
        "MAIN COMPARISON: PRE-STABILITY PROVISIONAL REFERENCE",
        "",
    ]

    for stage, result in metrics_pre.items():
        lines.append(
            f"{stage}: "
            f"coverage={result['coverage']:.1%}; "
            f"actionable={result['actionable']}; "
            f"disagreements={result['disagreements']}; "
            f"disagreement_rate="
            f"{result['disagreement_rate']:.1%}; "
            f"unsupported_ADVANCE="
            f"{result['unsupported_advances_provisional']}; "
            f"deferrals={result['deferrals']}"
        )

    lines.extend([
        "",
        "STABILITY ATTRIBUTION",
        json.dumps(
            stability_attribution,
            indent=2,
        ),
        "",
        "CITATION VERIFICATION OUTCOMES",
        json.dumps(
            dict(citation_counts),
            indent=2,
        ),
        "",
        "POST-STABILITY REFERENCE SENSITIVITY",
    ])

    for stage, result in metrics_post.items():
        lines.append(
            f"{stage}: "
            f"coverage={result['coverage']:.1%}; "
            f"disagreements={result['disagreements']}; "
            f"disagreement_rate="
            f"{result['disagreement_rate']:.1%}"
        )

    lines.extend([
        "",
        "LIMITATIONS",
        *[f"- {x}" for x in report["limitations"]],
    ])

    OUT_TXT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "stage": "VALIDATION",
        "status": "COMPLETE",
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "policy_sha256": sha256(POLICY),
        "input_sha256": {
            path.name: sha256(path)
            for path in (
                EVIDENCE,
                SCORING,
                REFERENCES,
                KEY,
                DATASET,
                SCENARIOS,
            )
        },
        "output_sha256": {
            path.name: sha256(path)
            for path in (
                OUT_JSON,
                OUT_CSV,
                OUT_TXT,
            )
        },
        "api_requests": 0,
        "test_accessed": False,
        "reference_independently_validated": False,
    }

    with OUT_MANIFEST.open(
        "x", encoding="utf-8"
    ) as handle:
        json.dump(
            manifest,
            handle,
            indent=2,
            ensure_ascii=False,
        )

    print("\n".join(lines))
    print()
    print("ANALYSIS COMPLETE")
    print("Responses:", len(records))
    print("Groups:", len(groups))
    print("API requests: 0")
    print("TEST partition: NOT ACCESSED")
    print()
    print("Saved:")
    for path in outputs:
        print(" ", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
