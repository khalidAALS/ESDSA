

"""Evaluate corrected traceability policy on development data.

No API calls. Does not modify original results or reference labels.
This is a component-level experiment, not the final integrated ESDSA v2.
"""

# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"

INTEGRATED = RESULTS / "integrated_esdsa_v1.json"
AUDIT = RESULTS / "traceability_audit_v2.json"

OUT_JSON = RESULTS / "traceability_policy_v2.json"
OUT_TXT = RESULTS / "traceability_policy_v2.txt"

ACTIONABLE = {"ADVANCE", "DO_NOT_ADVANCE"}


def metrics(records, decision_field):
    actionable = [
        r for r in records
        if r[decision_field] in ACTIONABLE
    ]

    disagreements = [
        r for r in actionable
        if r[decision_field] != r["reference_decision"]
    ]

    return {
        "total": len(records),
        "actionable": len(actionable),
        "coverage": len(actionable) / len(records),
        "disagreements": len(disagreements),
        "disagreement_rate": (
            len(disagreements) / len(actionable)
            if actionable else None
        ),
        "unsupported_advances": sum(
            r[decision_field] == "ADVANCE"
            and r["reference_decision"] != "ADVANCE"
            for r in records
        ),
        "deferrals_against_actionable_reference": sum(
            r[decision_field] == "DEFER"
            and r["reference_decision"] in ACTIONABLE
            for r in records
        ),
        "distribution": dict(Counter(
            r[decision_field] for r in records
        )),
    }


def new_decision(criteria):
    if any(
        c["evidence_status"] == "NEGATIVE_EVIDENCE"
        and c["v2_outcome"] == "VERIFIED"
        for c in criteria
    ):
        return "DO_NOT_ADVANCE", "VERIFIED_NEGATIVE_EVIDENCE"

    if all(
        c["evidence_status"] == "POSITIVE_EVIDENCE"
        and c["v2_outcome"] == "VERIFIED"
        for c in criteria
    ):
        return "ADVANCE", "ALL_POSITIVE_VERIFIED"

    return "DEFER", "INSUFFICIENT_VERIFIED_DECISIVE_EVIDENCE"


def main():
    original = json.loads(
        INTEGRATED.read_text(encoding="utf-8")
    )["records"]

    citation_report = json.loads(
        AUDIT.read_text(encoding="utf-8")
    )

    citation_lookup = {}

    for item in citation_report["all_citation_audits"]:
        key = (item["response_id"], item["criterion_id"])

        if key in citation_lookup:
            raise ValueError(f"Duplicate citation audit: {key}")

        citation_lookup[key] = item

    if len(original) != 108:
        raise ValueError("Expected 108 original records")

    output = []
    seen_ids = set()

    for r in original:
        rid = r["response_id"]

        if rid in seen_ids:
            raise ValueError(f"Duplicate response ID: {rid}")

        seen_ids.add(rid)
        criteria = []

        for criterion in r["criterion_audit"]:
            status = criterion["status"]
            criterion_id = criterion["criterion_id"]
            key = (rid, criterion_id)

            if status == "INSUFFICIENT_EVIDENCE":
                outcome = "NOT_APPLICABLE"
            else:
                if key not in citation_lookup:
                    raise ValueError(f"Missing citation audit: {key}")

                audit = citation_lookup[key]

                if audit["evidence_status"] != status:
                    raise ValueError(f"Status mismatch: {key}")

                outcome = audit["v2_outcome"]

            criteria.append({
                "criterion_id": criterion_id,
                "evidence_status": status,
                "v2_outcome": outcome,
            })

        if len(criteria) != 3:
            raise ValueError(
                f"Expected 3 criteria for {rid}; "
                f"found {len(criteria)}"
            )

        decision, reason = new_decision(criteria)

        output.append({
            "response_id": rid,
            "group": r["group"],
            "semantic_equivalence": r["semantic_equivalence"],
            "reference_decision": r["reference_decision"],
            "baseline_evidence_decision":
                r["baseline_evidence_decision"],
            "traceability_v1_decision":
                r["pre_stability_decision"],
            "traceability_v2_decision": decision,
            "traceability_v2_reason": reason,
            "criteria": criteria,
        })

    stages = {
        "evidence_aware": metrics(
            output, "baseline_evidence_decision"
        ),
        "traceability_v1": metrics(
            output, "traceability_v1_decision"
        ),
        "traceability_v2": metrics(
            output, "traceability_v2_decision"
        ),
    }

    changed = [
        r for r in output
        if r["traceability_v1_decision"]
        != r["traceability_v2_decision"]
    ]

    restored_correct = sum(
        r["traceability_v1_decision"] == "DEFER"
        and r["traceability_v2_decision"] in ACTIONABLE
        and r["traceability_v2_decision"]
            == r["reference_decision"]
        for r in changed
    )

    restored_disagreement = sum(
        r["traceability_v1_decision"] == "DEFER"
        and r["traceability_v2_decision"] in ACTIONABLE
        and r["traceability_v2_decision"]
            != r["reference_decision"]
        for r in changed
    )

    newly_deferred = sum(
        r["traceability_v1_decision"] in ACTIONABLE
        and r["traceability_v2_decision"] == "DEFER"
        for r in changed
    )

    summary = {
        "stages": stages,
        "changed_responses": len(changed),
        "restored_correct_recommendations": restored_correct,
        "restored_disagreements": restored_disagreement,
        "newly_deferred_recommendations": newly_deferred,
        "limitations": [
            "Development data only.",
            "Provisional reference labels are not ground truth.",
            "Only citation verification and decision gating "
            "are evaluated; substantive evidence classifications "
            "remain unchanged.",
            "The stability gate is not applied in this experiment.",
            "Verified excerpts may still be irrelevant or "
            "insufficient for their associated competencies.",
        ],
    }

    report = {
        "summary": summary,
        "changed_records": changed,
        "all_records": output,
    }

    OUT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "ESDSA V2 — TRACEABILITY POLICY COMPONENT TEST",
        "",
    ]

    for name, m in stages.items():
        lines.append(
            f"{name}: "
            f"coverage={m['coverage']:.1%}; "
            f"actionable={m['actionable']}; "
            f"disagreements={m['disagreements']}; "
            f"disagreement_rate="
            f"{m['disagreement_rate']:.1%}; "
            f"unsupported_ADVANCE={m['unsupported_advances']}; "
            f"deferrals_against_actionable_reference="
            f"{m['deferrals_against_actionable_reference']}"
        )

    lines.extend([
        "",
        f"CHANGED RESPONSES: {len(changed)}",
        f"Restored correct: {restored_correct}",
        f"Restored disagreements: {restored_disagreement}",
        f"Newly deferred: {newly_deferred}",
        "",
        "CHANGED RESPONSE DETAILS",
    ])

    for r in changed:
        lines.append(
            f"{r['response_id']} | "
            f"{r['traceability_v1_decision']} -> "
            f"{r['traceability_v2_decision']} | "
            f"reference={r['reference_decision']} | "
            f"reason={r['traceability_v2_reason']}"
        )

    lines.extend([
        "",
        "LIMITATIONS",
        *[f"- {x}" for x in summary["limitations"]],
    ])

    OUT_TXT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print("\n".join(lines))
    print(f"\nSaved: {OUT_JSON}")
    print(f"Saved: {OUT_TXT}")


if __name__ == "__main__":
    main()
