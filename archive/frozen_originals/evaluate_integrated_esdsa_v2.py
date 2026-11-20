
#!/usr/bin/env python3
"""Integrated ESDSA v2: corrected traceability and restricted stability.

Development-only evaluation. No API calls, reference changes,
or modifications to existing v1/v2 component results.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"

POLICY_V2 = RESULTS / "traceability_policy_v2.json"
INTEGRATED_V1 = RESULTS / "integrated_esdsa_v1.json"

OUT_JSON = RESULTS / "integrated_esdsa_v2.json"
OUT_TXT = RESULTS / "integrated_esdsa_v2.txt"

ACTIONABLE = {"ADVANCE", "DO_NOT_ADVANCE"}
VALID_DECISIONS = ACTIONABLE | {"DEFER"}


def measure(records, field):
    actionable = [
        r for r in records if r[field] in ACTIONABLE
    ]
    wrong = [
        r for r in actionable
        if r[field] != r["reference_decision"]
    ]

    return {
        "total": len(records),
        "actionable": len(actionable),
        "coverage": len(actionable) / len(records),
        "disagreements": len(wrong),
        "disagreement_rate": (
            len(wrong) / len(actionable) if actionable else None
        ),
        "unsupported_advances": sum(
            r[field] == "ADVANCE"
            and r["reference_decision"] != "ADVANCE"
            for r in records
        ),
        "deferrals_against_actionable_reference": sum(
            r[field] == "DEFER"
            and r["reference_decision"] in ACTIONABLE
            for r in records
        ),
        "distribution": dict(Counter(
            r[field] for r in records
        )),
    }


def main():
    policy = json.loads(
        POLICY_V2.read_text(encoding="utf-8")
    )
    v1 = json.loads(
        INTEGRATED_V1.read_text(encoding="utf-8")
    )

    records = policy["all_records"]
    originals = {
        r["response_id"]: r
        for r in v1["records"]
    }

    if len(records) != 108 or len(originals) != 108:
        raise ValueError("Expected 108 unique records")

    groups = defaultdict(list)
    output = []
    seen = set()

    for record in records:
        rid = record["response_id"]

        if rid in seen or rid not in originals:
            raise ValueError(f"Duplicate or unknown response: {rid}")

        seen.add(rid)
        previous = originals[rid]

        if (
            record["group"] != previous["group"]
            or record["reference_decision"]
                != previous["reference_decision"]
            or record["semantic_equivalence"]
                != previous["semantic_equivalence"]
        ):
            raise ValueError(f"Source mismatch for {rid}")

        decision = record["traceability_v2_decision"]

        if decision not in VALID_DECISIONS:
            raise ValueError(f"Invalid decision for {rid}")

        item = {
            **record,
            "integrated_v1_decision":
                previous["esdsa_decision"],
            "integrated_v2_decision": None,
            "stability_gate_reason": None,
        }

        output.append(item)
        groups[record["group"]].append(item)

    if len(groups) != 36:
        raise ValueError(
            f"Expected 36 variant groups; got {len(groups)}"
        )

    group_diagnostics = []

    for group_id, members in sorted(groups.items()):
        if len(members) != 3:
            raise ValueError(
                f"{group_id} contains {len(members)} responses"
            )

        equivalence_values = {
            m["semantic_equivalence"] for m in members
        }

        if len(equivalence_values) != 1:
            raise ValueError(
                f"Inconsistent equivalence: {group_id}"
            )

        equivalence = next(iter(equivalence_values))
        decisions = [
            m["traceability_v2_decision"]
            for m in members
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

        elif equivalence in {"NO", "UNCERTAIN"}:
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
                f"Unexpected equivalence: {equivalence}"
            )

        group_diagnostics.append({
            "group": group_id,
            "semantic_equivalence": equivalence,
            "traceability_v2_decisions": decisions,
            "integrated_v2_decisions": [
                m["integrated_v2_decision"]
                for m in members
            ],
            "gate_reasons": sorted({
                m["stability_gate_reason"]
                for m in members
            }),
            "newly_deferred_by_stability": sum(
                m["traceability_v2_decision"] in ACTIONABLE
                and m["integrated_v2_decision"] == "DEFER"
                for m in members
            ),
        })

    stages = {
        "evidence_aware": measure(
            output, "baseline_evidence_decision"
        ),
        "traceability_v2_only": measure(
            output, "traceability_v2_decision"
        ),
        "integrated_v1": measure(
            output, "integrated_v1_decision"
        ),
        "integrated_v2": measure(
            output, "integrated_v2_decision"
        ),
    }

    # Isolate what the v2 stability gate adds after traceability v2.
    stability_changes = [
        r for r in output
        if r["traceability_v2_decision"]
        != r["integrated_v2_decision"]
    ]

    stability_attribution = {
        "changed_responses": len(stability_changes),
        "prevented_disagreements": sum(
            r["traceability_v2_decision"] in ACTIONABLE
            and r["traceability_v2_decision"]
                != r["reference_decision"]
            and r["integrated_v2_decision"] == "DEFER"
            for r in stability_changes
        ),
        "deferred_supported_decisions": sum(
            r["traceability_v2_decision"] in ACTIONABLE
            and r["traceability_v2_decision"]
                == r["reference_decision"]
            and r["integrated_v2_decision"] == "DEFER"
            for r in stability_changes
        ),
        "deferred_reference_defer": sum(
            r["traceability_v2_decision"] in ACTIONABLE
            and r["reference_decision"] == "DEFER"
            and r["integrated_v2_decision"] == "DEFER"
            for r in stability_changes
        ),
    }

    # Compare directly with original integrated v1.
    v1_changes = [
        r for r in output
        if r["integrated_v1_decision"]
        != r["integrated_v2_decision"]
    ]

    comparison = {
        "changed_responses": len(v1_changes),
        "v1_defer_to_v2_actionable": sum(
            r["integrated_v1_decision"] == "DEFER"
            and r["integrated_v2_decision"] in ACTIONABLE
            for r in v1_changes
        ),
        "restored_correct_against_reference": sum(
            r["integrated_v1_decision"] == "DEFER"
            and r["integrated_v2_decision"] in ACTIONABLE
            and r["integrated_v2_decision"]
                == r["reference_decision"]
            for r in v1_changes
        ),
        "restored_disagreements": sum(
            r["integrated_v1_decision"] == "DEFER"
            and r["integrated_v2_decision"] in ACTIONABLE
            and r["integrated_v2_decision"]
                != r["reference_decision"]
            for r in v1_changes
        ),
        "v1_actionable_to_v2_defer": sum(
            r["integrated_v1_decision"] in ACTIONABLE
            and r["integrated_v2_decision"] == "DEFER"
            for r in v1_changes
        ),
    }

    report = {
        "stage": "development_only",
        "policy_description": {
            "traceability": (
                "Verified negative criterion is sufficient "
                "for DO_NOT_ADVANCE; ADVANCE requires all "
                "three positive criteria to be verified."
            ),
            "stability": (
                "Require unanimous actionable decisions "
                "only when semantic equivalence is YES. "
                "Otherwise, retain individual traceability "
                "decisions without a stability inference."
            ),
        },
        "stage_metrics": stages,
        "stability_attribution": stability_attribution,
        "integrated_v1_to_v2": comparison,
        "group_diagnostics": group_diagnostics,
        "changed_vs_v1": v1_changes,
        "all_records": output,
        "limitations": [
            "Development evaluation only; no held-out data.",
            "Reference decisions are provisional.",
            "Text verification does not establish "
            "substantive evidence sufficiency.",
            "NO and UNCERTAIN groups are not certified "
            "stable; the gate is simply not applied.",
            "The three variants are correlated within "
            "scenario families.",
            "Changes were specified after examining "
            "development diagnostic failures.",
        ],
    }

    OUT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "INTEGRATED ESDSA V2 — DEVELOPMENT COMPARISON",
        "",
    ]

    for name, m in stages.items():
        lines.append(
            f"{name}: coverage={m['coverage']:.1%}; "
            f"actionable={m['actionable']}; "
            f"disagreements={m['disagreements']}; "
            f"rate={m['disagreement_rate']:.1%}; "
            f"unsupported_ADVANCE={m['unsupported_advances']}; "
            f"deferrals_against_actionable_reference="
            f"{m['deferrals_against_actionable_reference']}"
        )

    lines.extend([
        "",
        "V2 STABILITY GATE ATTRIBUTION",
        json.dumps(stability_attribution, indent=2),
        "",
        "INTEGRATED V1 TO V2",
        json.dumps(comparison, indent=2),
        "",
        "GROUPS WITH V2 STABILITY DEFERRALS",
    ])

    for group in group_diagnostics:
        if group["newly_deferred_by_stability"]:
            lines.append(
                f"{group['group']} | "
                f"equivalence={group['semantic_equivalence']} | "
                f"pre={group['traceability_v2_decisions']} | "
                f"post={group['integrated_v2_decisions']} | "
                f"new_deferrals="
                f"{group['newly_deferred_by_stability']}"
            )

    lines.extend([
        "",
        "CHANGED RESPONSES VS V1",
    ])

    for r in v1_changes:
        lines.append(
            f"{r['response_id']} | "
            f"{r['integrated_v1_decision']} -> "
            f"{r['integrated_v2_decision']} | "
            f"reference={r['reference_decision']} | "
            f"equivalence={r['semantic_equivalence']}"
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

    print("\n".join(lines))
    print(f"\nSaved: {OUT_JSON}")
    print(f"Saved: {OUT_TXT}")


if __name__ == "__main__":
    main()
