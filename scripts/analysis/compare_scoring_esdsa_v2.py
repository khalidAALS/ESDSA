

"""Compare scoring-only, evidence-aware and integrated ESDSA v2.

Development data only. No API calls. Original files remain unchanged.
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
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"

SCORING_FILE = RESULTS / "scoring_baseline_108_v1.jsonl"
INTEGRATED_FILE = RESULTS / "integrated_esdsa_v2.json"

OUTPUT_JSON = RESULTS / "scoring_esdsa_v2_comparison.json"
OUTPUT_TXT = RESULTS / "scoring_esdsa_v2_comparison.txt"

ACTIONABLE = {"ADVANCE", "DO_NOT_ADVANCE"}
VALID = ACTIONABLE | {"DEFER"}
SEED = 20261120


def get_metrics(rows, field):
    actionable = [
        r for r in rows if r[field] in ACTIONABLE
    ]

    disagreements = sum(
        r[field] != r["reference_decision"]
        for r in actionable
    )

    return {
        "total": len(rows),
        "actionable": len(actionable),
        "coverage": (
            len(actionable) / len(rows) if rows else None
        ),
        "disagreements": disagreements,
        "disagreement_rate": (
            disagreements / len(actionable)
            if actionable else None
        ),
        "unsupported_advances": sum(
            r[field] == "ADVANCE"
            and r["reference_decision"] != "ADVANCE"
            for r in rows
        ),
        "deferrals_against_actionable_reference": sum(
            r[field] == "DEFER"
            and r["reference_decision"] in ACTIONABLE
            for r in rows
        ),
        "distribution": dict(
            Counter(r[field] for r in rows)
        ),
    }


def format_metrics(name, m):
    return (
        f"{name}: "
        f"actionable={m['actionable']}/{m['total']}; "
        f"coverage={m['coverage']:.1%}; "
        f"disagreements={m['disagreements']}; "
        f"rate={m['disagreement_rate']:.1%}; "
        f"unsupported_ADVANCE={m['unsupported_advances']}; "
        f"deferrals_against_actionable_reference="
        f"{m['deferrals_against_actionable_reference']}"
    )


def main():
    with SCORING_FILE.open(encoding="utf-8") as f:
        scoring_rows = [
            json.loads(line)
            for line in f
            if line.strip()
        ]

    integrated_data = json.loads(
        INTEGRATED_FILE.read_text(encoding="utf-8")
    )
    integrated_rows = integrated_data["all_records"]

    if len(scoring_rows) != 108 or len(integrated_rows) != 108:
        raise ValueError("Expected 108 records in each file")

    scoring = {}

    for r in scoring_rows:
        rid = r["response_id"]

        if rid in scoring:
            raise ValueError(f"Duplicate scoring ID: {rid}")

        if r["decision"] not in VALID:
            raise ValueError(f"Invalid scoring decision: {rid}")

        scoring[rid] = r

    integrated_ids = [
        r["response_id"] for r in integrated_rows
    ]

    if len(set(integrated_ids)) != 108:
        raise ValueError("Duplicate integrated response IDs")

    if set(scoring) != set(integrated_ids):
        raise ValueError(
            "Scoring and ESDSA response IDs do not match"
        )

    rows = []

    for r in integrated_rows:
        rid = r["response_id"]
        scoring_record = scoring[rid]

        if r["integrated_v2_decision"] not in VALID:
            raise ValueError(f"Invalid ESDSA decision: {rid}")

        rows.append({
            "response_id": rid,
            "group": r["group"],
            "reference_decision": r["reference_decision"],
            "semantic_equivalence": r["semantic_equivalence"],
            "scoring_decision": scoring_record["decision"],
            "scoring_scores": scoring_record["scores"],
            "scoring_mean": scoring_record["mean_score"],
            "evidence_aware_decision":
                r["baseline_evidence_decision"],
            "esdsa_v2_decision":
                r["integrated_v2_decision"],
        })

    fields = {
        "scoring_only": "scoring_decision",
        "evidence_aware": "evidence_aware_decision",
        "integrated_esdsa_v2": "esdsa_v2_decision",
    }

    full = {
        name: get_metrics(rows, field)
        for name, field in fields.items()
    }


    esdsa_retained = [
        r for r in rows
        if r["esdsa_v2_decision"] in ACTIONABLE
    ]

    on_esdsa_retained = {
        name: get_metrics(esdsa_retained, field)
        for name, field in fields.items()
    }

    both_actionable = [
        r for r in rows
        if r["scoring_decision"] in ACTIONABLE
        and r["esdsa_v2_decision"] in ACTIONABLE
    ]

    common = {
        name: get_metrics(both_actionable, field)
        for name, field in fields.items()
    }


    scoring_retained = [
        r for r in rows
        if r["scoring_decision"] in ACTIONABLE
    ]

    on_scoring_retained = {
        name: get_metrics(scoring_retained, field)
        for name, field in fields.items()
    }

    paired = {
        "both_actionable_count": len(both_actionable),
        "scoring_wrong_esdsa_correct": sum(
            r["scoring_decision"] != r["reference_decision"]
            and r["esdsa_v2_decision"]
                == r["reference_decision"]
            for r in both_actionable
        ),
        "scoring_correct_esdsa_wrong": sum(
            r["scoring_decision"] == r["reference_decision"]
            and r["esdsa_v2_decision"]
                != r["reference_decision"]
            for r in both_actionable
        ),
        "both_wrong": sum(
            r["scoring_decision"] != r["reference_decision"]
            and r["esdsa_v2_decision"]
                != r["reference_decision"]
            for r in both_actionable
        ),
        "scoring_defers_esdsa_acts": sum(
            r["scoring_decision"] == "DEFER"
            and r["esdsa_v2_decision"] in ACTIONABLE
            for r in rows
        ),
        "esdsa_defers_scoring_acts": sum(
            r["esdsa_v2_decision"] == "DEFER"
            and r["scoring_decision"] in ACTIONABLE
            for r in rows
        ),
    }


    n = len(scoring_retained)

    if len(esdsa_retained) < n:
        raise ValueError(
            "ESDSA has fewer actionable cases than scoring"
        )

    rng = random.Random(SEED)
    draws = []

    for _ in range(10000):
        sample = rng.sample(esdsa_retained, n)

        disagreements = sum(
            r["esdsa_v2_decision"]
                != r["reference_decision"]
            for r in sample
        )

        draws.append(disagreements)

    draws.sort()
    scoring_errors = full["scoring_only"]["disagreements"]

    sensitivity = {
        "scoring_actionable_count": n,
        "esdsa_actionable_pool": len(esdsa_retained),
        "draws": len(draws),
        "mean_esdsa_disagreements": sum(draws) / len(draws),
        "percentile_2_5": draws[249],
        "percentile_97_5": draws[9749],
        "fraction_esdsa_fewer_disagreements_than_scoring": (
            sum(x < scoring_errors for x in draws)
            / len(draws)
        ),
        "fraction_esdsa_equal_disagreements_to_scoring": (
            sum(x == scoring_errors for x in draws)
            / len(draws)
        ),
        "warning": (
            "Matched-count random sampling is descriptive. "
            "It does not compare the same retained cases or "
            "represent a deployable policy. Its percentiles "
            "are not confidence intervals."
        ),
    }

    report = {
        "dataset": "108 synthetic development responses",
        "reference_status": "AI-assisted provisional",
        "full_sample": full,
        "on_esdsa_retained_cases": on_esdsa_retained,
        "both_actionable_cases": common,
        "on_scoring_retained_cases": on_scoring_retained,
        "paired_comparison": paired,
        "random_matched_count_sensitivity": sensitivity,
        "all_records": rows,
        "limitations": [
            "Reference labels are provisional, not independent ground truth.",
            "Only 12 scenario families are represented.",
            "The 108 responses and their variants are correlated.",
            "ESDSA v2 was refined after development diagnostics.",
            "Comparison of actionable error rates involves selective coverage.",
            "Random matched-count sampling is not a usable deferral rule.",
            "No claim of statistically established superiority is warranted.",
        ],
    }

    OUTPUT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "SCORING-ONLY VS ESDSA V2 — DEVELOPMENT COMPARISON",
        "",
        "FULL 108 RESPONSES",
    ]

    for name, m in full.items():
        lines.append(format_metrics(name, m))

    lines.extend(["", "EXACT 100 ESDSA-RETAINED CASES"])

    for name, m in on_esdsa_retained.items():
        lines.append(format_metrics(name, m))

    lines.extend(["", "BOTH POLICIES ACTIONABLE — SAME CASES"])

    for name, m in common.items():
        lines.append(format_metrics(name, m))

    lines.extend(["", "EXACT SCORING-ACTIONABLE CASES"])

    for name, m in on_scoring_retained.items():
        lines.append(format_metrics(name, m))

    lines.extend([
        "",
        "PAIRED COMPARISON",
        json.dumps(paired, indent=2),
        "",
        "RANDOM MATCHED-COUNT SENSITIVITY",
        json.dumps(sensitivity, indent=2),
        "",
        "LIMITATIONS",
        *[f"- {x}" for x in report["limitations"]],
    ])

    OUTPUT_TXT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print("\n".join(lines))
    print(f"\nSaved: {OUTPUT_JSON}")
    print(f"Saved: {OUTPUT_TXT}")


if __name__ == "__main__":
    main()
