
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path("results")
output = root / "v2_disagreement_review.json"

if output.exists():
    raise SystemExit(f"Already exists: {output}")

finding = {
    "finding_id": "ESDSA-DEV-F01",
    "experiment": "Challenge Benchmark v2",
    "scenario_family": "F02",
    "response_ids": [
        "ESDSA-V2-0006",
        "ESDSA-V2-0007"
    ],
    "criterion": "C3",
    "criterion_name": "Reasoned correction",
    "scoring_evaluator": {
        "original_scores": [3, 3, 2, 3],
        "style_scores": [3, 3, 2, 3],
        "original_recommendation": "ADVANCE",
        "style_recommendation": "ADVANCE"
    },
    "evidence_audit": {
        "original_c3": "POSITIVE_EVIDENCE",
        "style_c3": "INSUFFICIENT_EVIDENCE",
        "original_recommendation": "ADVANCE",
        "style_recommendation": "DEFER"
    },
    "observed_issue": (
        "Evidence audit assigns different C3 classifications "
        "to responses designed to preserve substantive competency "
        "evidence under linguistic variation."
    ),
    "preliminary_interpretation": (
        "Potential evidence-audit instability under a "
        "meaning-preserving rewrite. Semantic equivalence "
        "has not been independently established."
    ),
    "excerpt_warnings": {
        "count": 3,
        "suspected_cause": "Surrounding quotation marks",
        "verification_status": "PENDING"
    },
    "reference_status": "PROVISIONAL",
    "independent_semantic_validation": False,
    "requires_follow_up": True,
    "created_utc": datetime.now(
        timezone.utc
    ).isoformat()
}

output.write_text(
    json.dumps(finding, indent=2),
    encoding="utf-8"
)

print("Created:", output)
print("Finding:", finding["finding_id"])
print("Criterion:", finding["criterion"])
print("Independent semantic validation: PENDING")
print("Original model results unchanged.")
