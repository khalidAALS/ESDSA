
"""Development-only ESDSA diagnosis. No API calls or label modifications."""

import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
BENCH = ROOT / "data" / "benchmark" / "researcher_annotations_v1"

INPUT = RESULTS / "integrated_esdsa_v1.json"
REFERENCE = BENCH / "development_reference_provisional_v1.csv"

OUTPUT = RESULTS / "integrated_esdsa_diagnostic_v1.json"
TEXT = RESULTS / "integrated_esdsa_diagnostic_v1.txt"

ACTIONABLE = {"ADVANCE", "DO_NOT_ADVANCE"}
SEED = 20261120


def metrics(rows, field):
    n = len(rows)
    active = [r for r in rows if r[field] in ACTIONABLE]
    wrong = [
        r for r in active
        if r[field] != r["reference_decision"]
    ]

    return {
        "total": n,
        "actionable": len(active),
        "coverage": len(active) / n if n else None,
        "actionable_disagreements": len(wrong),
        "actionable_disagreement_rate": (
            len(wrong) / len(active) if active else None
        ),
        "unsupported_advances": sum(
            r[field] == "ADVANCE"
            and r["reference_decision"] != "ADVANCE"
            for r in rows
        ),
        "unnecessary_deferrals": sum(
            r[field] == "DEFER"
            and r["reference_decision"] in ACTIONABLE
            for r in rows
        ),
        "decision_distribution": dict(
            Counter(r[field] for r in rows)
        ),
    }


def main():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    rows = data["records"]

    assert len(rows) == 108, (
        f"Expected 108 records, got {len(rows)}"
    )

    ids = [r["response_id"] for r in rows]
    assert len(set(ids)) == len(ids), "Duplicate response IDs"

    with REFERENCE.open(
        newline="", encoding="utf-8-sig"
    ) as f:
        refrows = list(csv.DictReader(f))

    ref = {
        (r["review_group"], r["response_label"]): r
        for r in refrows
    }

    assert len(ref) == len(refrows) == 108, (
        "Reference keys missing or duplicated"
    )

    for r in rows:
        key = (r["group"], r["letter"])

        assert key in ref, f"No reference for {key}"

        assert (
            r["reference_decision"]
            == ref[key]["reference_decision"]
        ), f"Reference mismatch: {key}"

        assert (
            r["semantic_equivalence"]
            == ref[key]["semantic_equivalence"]
        ), f"Equivalence mismatch: {key}"

        r["reference_review_flag"] = ref[key]["review_flag"]

    groups = defaultdict(list)

    for r in rows:
        groups[r["group"]].append(r)

    assert len(groups) == 36
    assert all(len(v) == 3 for v in groups.values())

    stages = {
        "evidence_aware": metrics(
            rows, "baseline_evidence_decision"
        ),
        "traceability_only": metrics(
            rows, "pre_stability_decision"
        ),
        "integrated_esdsa": metrics(
            rows, "esdsa_decision"
        ),
    }


    retained = [
        r for r in rows
        if r["esdsa_decision"] in ACTIONABLE
    ]

    common = {
        name: metrics(retained, field)
        for name, field in [
            ("evidence_aware", "baseline_evidence_decision"),
            ("traceability_only", "pre_stability_decision"),
            ("integrated_esdsa", "esdsa_decision"),
        ]
    }


    eligible = [
        r for r in rows
        if r["baseline_evidence_decision"] in ACTIONABLE
    ]

    rng = random.Random(SEED)
    draws = []

    for _ in range(10000):
        sample = rng.sample(eligible, len(retained))

        disagreements = sum(
            r["baseline_evidence_decision"]
            != r["reference_decision"]
            for r in sample
        )

        draws.append(disagreements)

    draws.sort()

    esdsa_disagreements = stages[
        "integrated_esdsa"
    ]["actionable_disagreements"]

    random_comparison = {
        "matched_count": len(retained),
        "draws": len(draws),
        "mean_disagreements": sum(draws) / len(draws),
        "percentile_2_5": draws[249],
        "percentile_97_5": draws[9749],
        "fraction_fewer_disagreements_than_esdsa": (
            sum(x < esdsa_disagreements for x in draws)
            / len(draws)
        ),
        "warning": (
            "Random retention is descriptive only; "
            "percentiles are not confidence intervals."
        ),
    }


    transitions = {}

    for label, before, after in [
        (
            "evidence_to_traceability",
            "baseline_evidence_decision",
            "pre_stability_decision",
        ),
        (
            "traceability_to_integrated",
            "pre_stability_decision",
            "esdsa_decision",
        ),
    ]:
        changed = [
            r for r in rows
            if r[before] != r[after]
        ]

        transitions[label] = {
            "changed_count": len(changed),
            "prevented_disagreements": sum(
                r[before] in ACTIONABLE
                and r[before] != r["reference_decision"]
                and r[after] == "DEFER"
                for r in changed
            ),
            "deferred_supported": sum(
                r[before] in ACTIONABLE
                and r[before] == r["reference_decision"]
                and r[after] == "DEFER"
                for r in changed
            ),
            "newly_deferred_reference_defer": sum(
                r[before] in ACTIONABLE
                and r["reference_decision"] == "DEFER"
                and r[after] == "DEFER"
                for r in changed
            ),
            "response_ids": [
                r["response_id"] for r in changed
            ],
        }

    deferred = [
        r for r in rows
        if r["esdsa_decision"] == "DEFER"
    ]

    deferral_breakdown = {
        "reference_actionable": sum(
            r["reference_decision"] in ACTIONABLE
            for r in deferred
        ),
        "reference_defer": sum(
            r["reference_decision"] == "DEFER"
            for r in deferred
        ),
        "flagged_for_review": sum(
            r["reference_review_flag"] == "YES"
            for r in deferred
        ),
        "by_equivalence": dict(
            Counter(
                r["semantic_equivalence"]
                for r in deferred
            )
        ),
        "by_reference": dict(
            Counter(
                r["reference_decision"]
                for r in deferred
            )
        ),
    }

    group_report = []

    for name, g in sorted(groups.items()):
        group_report.append({
            "group": name,
            "equivalence": sorted(set(
                r["semantic_equivalence"] for r in g
            )),
            "reference_flagged": any(
                r["reference_review_flag"] == "YES"
                for r in g
            ),
            "reference_decisions": [
                r["reference_decision"] for r in g
            ],
            "evidence_decisions": [
                r["baseline_evidence_decision"] for r in g
            ],
            "traceability_decisions": [
                r["pre_stability_decision"] for r in g
            ],
            "integrated_decisions": [
                r["esdsa_decision"] for r in g
            ],
            "new_deferrals": sum(
                r["baseline_evidence_decision"] in ACTIONABLE
                and r["esdsa_decision"] == "DEFER"
                for r in g
            ),
            "unnecessary_deferrals": sum(
                r["esdsa_decision"] == "DEFER"
                and r["reference_decision"] in ACTIONABLE
                for r in g
            ),
            "prevented_disagreements": sum(
                r["baseline_evidence_decision"] in ACTIONABLE
                and r["baseline_evidence_decision"]
                != r["reference_decision"]
                and r["esdsa_decision"] == "DEFER"
                for r in g
            ),
        })


    cluster_list = list(groups.values())
    rng = random.Random(SEED + 1)
    diffs = []

    for _ in range(5000):
        sampled = [
            r
            for _ in cluster_list
            for r in rng.choice(cluster_list)
        ]

        m1 = metrics(
            sampled, "baseline_evidence_decision"
        )
        m2 = metrics(
            sampled, "esdsa_decision"
        )

        if (
            m1["actionable_disagreement_rate"] is not None
            and m2["actionable_disagreement_rate"] is not None
        ):
            diffs.append(
                m2["actionable_disagreement_rate"]
                - m1["actionable_disagreement_rate"]
            )

    diffs.sort()

    uncertainty = {
        "quantity": (
            "Integrated minus evidence-aware actionable "
            "disagreement rate (different retained populations)"
        ),
        "observed": (
            stages["integrated_esdsa"][
                "actionable_disagreement_rate"
            ]
            - stages["evidence_aware"][
                "actionable_disagreement_rate"
            ]
        ),
        "cluster_bootstrap_95_percentile_interval": [
            diffs[int(0.025 * len(diffs))],
            diffs[int(0.975 * len(diffs)) - 1],
        ],
        "bootstrap_resamples": len(diffs),
        "warning": (
            "Exploratory development uncertainty with "
            "36 correlated variant groups in 12 scenario families; "
            "not held-out inference."
        ),
    }

    report = {
        "stage": "development_only",
        "n_responses": len(rows),
        "n_variant_groups": len(groups),
        "stages": stages,
        "exact_common_retained_cases": common,
        "random_matched_count_sensitivity": random_comparison,
        "component_transitions": transitions,
        "deferrals": deferral_breakdown,
        "group_diagnostics": group_report,
        "exploratory_uncertainty": uncertainty,
        "limitations": [
            "Provisional AI-assisted references are not "
            "independent ground truth.",
            "Scoring-only per-response outputs were not "
            "among the four inputs.",
            "The current gate operates on groups including "
            "NO/UNCERTAIN equivalence.",
            "Literal quotation mismatch is not semantic "
            "evidence failure.",
            "Do not tune policy on held-out data or claim "
            "development results are independent validation.",
        ],
    }

    RESULTS.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    lines = [
        "INTEGRATED ESDSA — DEVELOPMENT DIAGNOSIS",
        "",
    ]

    for name, m in stages.items():
        lines.append(
            f"{name}: coverage={m['coverage']:.1%}; "
            f"actionable={m['actionable']}; "
            f"disagreements={m['actionable_disagreements']}; "
            f"rate={m['actionable_disagreement_rate']:.1%}; "
            f"unsupported ADVANCE={m['unsupported_advances']}; "
            f"unnecessary deferrals={m['unnecessary_deferrals']}"
        )

    lines += [
        "",
        "EXACT SAME 72 ESDSA-RETAINED CASES",
    ]

    for name, m in common.items():
        lines.append(
            f"{name}: actionable={m['actionable']}; "
            f"disagreements={m['actionable_disagreements']}; "
            f"unsupported ADVANCE={m['unsupported_advances']}"
        )

    lines += ["", "COMPONENT ATTRIBUTION"]

    for name, m in transitions.items():
        lines.append(
            f"{name}: changed={m['changed_count']}; "
            f"prevented disagreements="
            f"{m['prevented_disagreements']}; "
            f"deferred supported={m['deferred_supported']}; "
            f"deferred reference-DEFER="
            f"{m['newly_deferred_reference_defer']}"
        )

    lines += [
        "",
        "DEFERRALS",
        json.dumps(deferral_breakdown, indent=2),
        "",
        "MATCHED-COUNT RANDOM SENSITIVITY",
        json.dumps(random_comparison, indent=2),
        "",
        "UNCERTAINTY",
        json.dumps(uncertainty, indent=2),
        "",
        "GROUPS WITH UNNECESSARY DEFERRALS",
    ]

    for g in group_report:
        if g["unnecessary_deferrals"]:
            lines.append(
                f"{g['group']}: "
                f"unnecessary={g['unnecessary_deferrals']}, "
                f"prevented_disagreements="
                f"{g['prevented_disagreements']}, "
                f"equivalence={g['equivalence']}, "
                f"flagged={g['reference_flagged']}"
            )

    lines += ["", "LIMITATIONS"]
    lines += [
        "- " + s for s in report["limitations"]
    ]

    TEXT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print("\n".join(lines))
    print(f"\nSaved {OUTPUT} and {TEXT}")


if __name__ == "__main__":
    main()
