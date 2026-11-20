

"""Evaluate a three-variant decision-consensus gate.

Uses existing predictions only. No API calls.
Does not use reference labels to determine gate decisions.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

SOURCE = Path("results/baseline_comparison_108_v1.json")
OUTPUT = Path("results/esdsa_stability_gate_108_v1.json")

METHODS = ("scoring", "evidence")
ACTIONS = {"ADVANCE", "DO_NOT_ADVANCE"}

if not SOURCE.exists():
    raise SystemExit(f"Missing input: {SOURCE}")

if OUTPUT.exists():
    raise SystemExit(f"Output already exists: {OUTPUT}")

data = json.loads(SOURCE.read_text(encoding="utf-8"))
rows = data["per_response"]

if len(rows) != 108:
    raise SystemExit("Expected 108 response records.")

groups = defaultdict(list)

for row in rows:
    groups[row["group"]].append(row)

if len(groups) != 36:
    raise SystemExit("Expected 36 groups.")

for group, items in groups.items():
    if (
        len(items) != 3
        or {r["letter"] for r in items} != {"A", "B", "C"}
    ):
        raise SystemExit(f"Invalid group structure: {group}")


def gate_decision(items, method):
    decisions = {r[method] for r in items}

    if len(decisions) == 1:
        value = next(iter(decisions))

        if value in ACTIONS:
            return value

    return "DEFER"


def summarise(items, method, gated=False):
    decisions = []

    for row in items:
        if gated:
            decision = gate_decision(groups[row["group"]], method)
        else:
            decision = row[method]

        decisions.append((decision, row["reference"]))

    actionable = [
        (d, ref) for d, ref in decisions if d in ACTIONS
    ]

    disagreements = sum(
        d != ref for d, ref in actionable
    )

    unsupported_advances = sum(
        d == "ADVANCE" and ref != "ADVANCE"
        for d, ref in actionable
    )

    actionable_reference_deferrals = sum(
        d in ACTIONS and ref == "DEFER"
        for d, ref in actionable
    )

    reference_actionable_but_deferred = sum(
        d == "DEFER" and ref in ACTIONS
        for d, ref in decisions
    )

    return {
        "responses": len(items),
        "decision_counts": dict(
            Counter(d for d, _ in decisions)
        ),
        "actionable": len(actionable),
        "coverage": (
            len(actionable) / len(items) if items else None
        ),
        "actionable_disagreements": disagreements,
        "actionable_disagreement_rate": (
            disagreements / len(actionable)
            if actionable else None
        ),
        "advances_without_reference_support":
            unsupported_advances,
        "actions_when_reference_defers":
            actionable_reference_deferrals,
        "deferrals_when_reference_actionable":
            reference_actionable_but_deferred,
    }


eligible_groups = set()

for group, items in groups.items():
    if (
        all(r["semantic_equivalence"] == "YES" for r in items)
        and len({r["reference"] for r in items}) == 1
    ):
        eligible_groups.add(group)

eligible_rows = [
    r for r in rows if r["group"] in eligible_groups
]


analyses = {}

for subset_name, subset in (
    ("equivalent_groups", eligible_rows),
    ("all_groups_sensitivity", rows),
):
    analyses[subset_name] = {}

    for method in METHODS:
        original = summarise(subset, method)
        gated = summarise(subset, method, gated=True)

        analyses[subset_name][method] = {
            "original": original,
            "gated": gated,
            "coverage_change_percentage_points": (
                100 * (
                    gated["coverage"] - original["coverage"]
                )
            ),
            "additional_deferrals": (
                original["actionable"] - gated["actionable"]
            ),
        }


group_diagnostics = []

for group, items in sorted(groups.items()):
    record = {
        "group": group,
        "semantic_equivalence": items[0]["semantic_equivalence"],
        "reference_decisions": {
            r["letter"]: r["reference"] for r in items
        },
        "flagged": items[0]["review_flag"],
    }

    for method in METHODS:
        record[method] = {
            "original_decisions": {
                r["letter"]: r[method] for r in items
            },
            "gated_decision": gate_decision(items, method),
            "changed_to_defer": (
                gate_decision(items, method) == "DEFER"
                and any(r[method] in ACTIONS for r in items)
            ),
        }

    group_diagnostics.append(record)


report = {
    "analysis": "PROTOTYPE_VARIANT_CONSENSUS_GATE",
    "gate_rule": (
        "Retain unanimous actionable decision across "
        "three variants; otherwise defer all three."
    ),
    "eligible_equivalent_groups": len(eligible_groups),
    "eligible_equivalent_responses": len(eligible_rows),
    "analyses": analyses,
    "group_diagnostics": group_diagnostics,
    "limitations": [
        "Reference labels are AI-assisted and provisional.",
        "Semantic equivalence has not been independently validated.",
        "The gate uses three generated variants, not three "
        "independent assessments of the identical response.",
        "The gate does not operationalise full ESDSA.",
        "Gating enforces group-level agreement by construction.",
        "Unstable groups may contain material evidence differences.",
        "Development data only, not held-out evaluation.",
        "Coverage is not matched between methods after gating.",
    ],
}

OUTPUT.write_text(
    json.dumps(
        report, indent=2, ensure_ascii=False
    ) + "\n",
    encoding="utf-8",
)

print("ESDSA — STABILITY-GATE DEVELOPMENT EXPERIMENT")
print("=" * 65)

print("Total groups:", len(groups))
print("Total responses:", len(rows))
print("Provisionally equivalent groups:", len(eligible_groups))
print("Equivalent-group responses:", len(eligible_rows))

for subset_name, methods in analyses.items():
    print("\n" + "-" * 65)
    print(subset_name.upper())

    for method, result in methods.items():
        original = result["original"]
        gated = result["gated"]

        print(f"\nMETHOD: {method.upper()}")

        print(
            "Original coverage:",
            f"{original['actionable']}/{original['responses']}",
            f"({original['coverage']:.1%})"
        )

        print(
            "Gated coverage:",
            f"{gated['actionable']}/{gated['responses']}",
            f"({gated['coverage']:.1%})"
        )

        print(
            "Original actionable disagreements:",
            original["actionable_disagreements"]
        )

        print(
            "Gated actionable disagreements:",
            gated["actionable_disagreements"]
        )

        print(
            "Original unsupported advances:",
            original["advances_without_reference_support"]
        )

        print(
            "Gated unsupported advances:",
            gated["advances_without_reference_support"]
        )

        print(
            "Additional deferrals:",
            result["additional_deferrals"]
        )


print("\nGROUPS TRIGGERING THE GATE")
for item in group_diagnostics:
    triggered = [
        method
        for method in METHODS
        if item[method]["changed_to_defer"]
    ]

    if triggered:
        print(
            item["group"],
            "| equivalence:", item["semantic_equivalence"],
            "| methods:", ", ".join(triggered)
        )

print("\nSaved:", OUTPUT)
print("No API calls made.")
print("No source files modified.")
