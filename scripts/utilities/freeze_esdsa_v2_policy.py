

"""Record the ESDSA v2 development-policy freeze.

No API calls. Does not change model decisions or reference labels.
Refuses to overwrite an existing freeze manifest.
"""

# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
FREEZE_DIR = ROOT / "data" / "benchmark" / "policy_freeze_v2"
MANIFEST = FREEZE_DIR / "esdsa_v2_policy_freeze.json"

REQUIRED_FILES = [
    "audit_traceability_v2.py",
    "evaluate_traceability_policy_v2.py",
    "evaluate_integrated_esdsa_v2.py",
    "results/integrated_esdsa_v1.json",
    "results/traceability_audit_v2.json",
    "results/traceability_policy_v2.json",
    "results/integrated_esdsa_v2.json",
    "results/scoring_baseline_108_v1.jsonl",
    "data/benchmark/development_responses_v1.csv",
    "data/benchmark/researcher_annotations_v1/"
    "development_reference_provisional_v1.csv",
    "data/benchmark/scenario_registry_v2.csv",
]

OPTIONAL_FILES = [
    "results/scoring_esdsa_v2_comparison.json",
    "data/benchmark/scenario_registry_reconciliation_v2.json",
    "data/benchmark/benchmark_specification_v1.json",
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if MANIFEST.exists():
        raise FileExistsError(
            "The ESDSA v2 freeze manifest already exists. "
            "It will not be overwritten."
        )

    missing = [
        filename
        for filename in REQUIRED_FILES
        if not (((ROOT / "archive/frozen_originals") if filename.endswith(".py") else ROOT) / filename).is_file()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing required files:\n" + "\n".join(missing)
        )

    integrated = json.loads(
        (RESULTS / "integrated_esdsa_v2.json").read_text(
            encoding="utf-8"
        )
    )

    records = integrated["all_records"]

    if len(records) != 108:
        raise ValueError(
            f"Expected 108 records; found {len(records)}"
        )

    if len({
        r["response_id"] for r in records
    }) != 108:
        raise ValueError("Duplicate response IDs")

    groups = {r["group"] for r in records}

    if len(groups) != 36:
        raise ValueError("Expected 36 variant groups")

    metrics = integrated["stage_metrics"]["integrated_v2"]

    if (
        metrics["actionable"] != 100
        or metrics["disagreements"] != 13
    ):
        raise ValueError(
            "Integrated v2 results differ from the "
            "reviewed development results"
        )

    file_hashes = {}

    for filename in REQUIRED_FILES + OPTIONAL_FILES:
        path = ((ROOT / "archive/frozen_originals") if filename.endswith(".py") else ROOT) / filename

        if path.is_file():
            file_hashes[filename] = digest(path)

    rubric_dir = ROOT / "data/benchmark/rubrics_v1"

    for path in sorted(rubric_dir.glob("*.json")):
        filename = str(path.relative_to(ROOT))
        file_hashes[filename] = digest(path)

    manifest = {
        "policy_name": (
            "Evidence Sufficiency and Decision "
            "Stability Audit"
        ),
        "policy_version": "ESDSA-v2-development-frozen",
        "freeze_timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "freeze_scope": (
            "Deterministic traceability and "
            "stability decision policy"
        ),
        "policy": {
            "evidence_statuses": [
                "POSITIVE_EVIDENCE",
                "NEGATIVE_EVIDENCE",
                "INSUFFICIENT_EVIDENCE",
            ],
            "traceability": {
                "method": (
                    "Unicode and punctuation normalization; "
                    "ordered matching of citation segments "
                    "separated by ellipses"
                ),
                "outcomes": [
                    "VERIFIED",
                    "CONTEXT_ONLY",
                    "UNVERIFIABLE",
                ],
                "negative_rule": (
                    "Any criterion classified as "
                    "NEGATIVE_EVIDENCE with VERIFIED "
                    "support yields DO_NOT_ADVANCE"
                ),
                "positive_rule": (
                    "All three criteria must be "
                    "POSITIVE_EVIDENCE and VERIFIED "
                    "to yield ADVANCE"
                ),
                "otherwise": "DEFER",
            },
            "stability": {
                "group_size": 3,
                "applies_when_equivalence": "YES",
                "required_condition": (
                    "All three pre-stability decisions "
                    "must be identical and actionable"
                ),
                "failed_condition": (
                    "DEFER all three responses "
                    "in that equivalence group"
                ),
                "equivalence_no_or_uncertain": (
                    "Do not apply the stability gate; "
                    "retain each traceability decision"
                ),
            },
            "limitations": [
                "Textual verification does not establish "
                "substantive evidence sufficiency.",
                "A verified negative classification is "
                "decisive even if another criterion "
                "has an invalid citation.",
                "NO/UNCERTAIN equivalence is not "
                "evidence of decision stability.",
                "The three-response stability gate "
                "assumes a controlled paraphrase batch, "
                "not an ordinary single-applicant interview.",
            ],
        },
        "development_dataset": {
            "scenario_families": 12,
            "variant_groups": 36,
            "responses": 108,
            "reference_status": (
                "AI-assisted provisional; "
                "not independent ground truth"
            ),
            "policy_refined_using_development": True,
            "actionable": metrics["actionable"],
            "disagreements": metrics["disagreements"],
            "coverage": metrics["coverage"],
            "disagreement_rate": metrics[
                "disagreement_rate"
            ],
        },
        "planned_held_out_design": {
            "validation_families": 24,
            "test_families": 24,
            "validation_and_test_examined": False,
            "test_policy": (
                "Do not revise policy from test "
                "outcomes or inspect test labels "
                "before the final evaluation"
            ),
        },
        "implementation_file_sha256": file_hashes,
        "important_note": (
            "This freeze covers the deterministic "
            "ESDSA v2 audit. It does not establish "
            "that model prompts, model versions, "
            "generation protocols or future reference "
            "adjudication procedures are frozen. "
            "Those must be documented before held-out "
            "model evaluation."
        ),
    }

    FREEZE_DIR.mkdir(parents=True, exist_ok=True)

    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("ESDSA V2 POLICY FREEZE")
    print("=" * 60)
    print("Version:", manifest["policy_version"])
    print("Development families: 12")
    print("Development responses: 108")
    print("Actionable decisions:", metrics["actionable"])
    print("Development disagreements:", metrics["disagreements"])
    print("Files fingerprinted:", len(file_hashes))
    print("Original experimental files modified: NO")
    print("API calls: NONE")
    print()
    print("Saved:", MANIFEST)
    print()
    print(
        "Note: Model-evaluation prompts and held-out "
        "reference procedures still require a separate "
        "protocol freeze."
    )


if __name__ == "__main__":
    main()
