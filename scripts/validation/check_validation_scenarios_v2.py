

"""Final pre-generation integrity check for ESDSA validation scenarios.

Read-only checks of source files. Writes only a new audit report.
Makes no API calls and does not generate candidate responses.
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
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data" / "benchmark"

SCENARIOS = BASE / "validation_scenarios_v2.csv"
REGISTRY = BASE / "scenario_registry_v2.csv"
DEVELOPMENT = BASE / "development_scenarios_v1.csv"
RUBRICS = BASE / "rubrics_v1"

POLICY_FREEZE = (
    BASE / "policy_freeze_v2/esdsa_v2_policy_freeze.json"
)
EVALUATION_FREEZE = (
    BASE / "policy_freeze_v2/"
    "esdsa_evaluation_protocol_freeze_v1.json"
)

REPORT = BASE / "validation_scenarios_integrity_v2.json"


def load_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(value):
    return " ".join(value.casefold().split())


def main():
    if REPORT.exists():
        raise FileExistsError(
            "The integrity report already exists. "
            "It will not be overwritten."
        )

    for path in (
        SCENARIOS,
        REGISTRY,
        DEVELOPMENT,
        POLICY_FREEZE,
        EVALUATION_FREEZE,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    scenarios = load_csv(SCENARIOS)
    registry = load_csv(REGISTRY)
    development = load_csv(DEVELOPMENT)

    validation_registry = {
        row["family_id"]: row
        for row in registry
        if row["partition"] == "VALIDATION"
    }

    if len(scenarios) != 24:
        raise ValueError(
            f"Expected 24 validation scenarios; found {len(scenarios)}"
        )

    if len(validation_registry) != 24:
        raise ValueError(
            "Registry does not contain 24 validation families"
        )

    scenario_ids = [r["family_id"] for r in scenarios]

    if len(set(scenario_ids)) != 24:
        raise ValueError("Duplicate validation family IDs")

    if set(scenario_ids) != set(validation_registry):
        raise ValueError(
            "Validation scenario IDs do not match the registry"
        )

    development_ids = {
        row["family_id"] for row in development
    }

    if set(scenario_ids) & development_ids:
        raise ValueError(
            "Development/validation family overlap detected"
        )

    competency_counts = Counter(
        row["competency_code"] for row in scenarios
    )

    if (
        len(competency_counts) != 12
        or any(n != 2 for n in competency_counts.values())
    ):
        raise ValueError(
            "Expected two scenarios for each of 12 competencies"
        )

    development_questions = {
        normalize(row["interview_question"])
        for row in development
    }

    seen_questions = set()
    rubric_hashes = {}

    for row in scenarios:
        family_id = row["family_id"]
        registered = validation_registry[family_id]

        if row["partition"] != "VALIDATION":
            raise ValueError(
                f"Wrong partition: {family_id}"
            )

        for field in (
            "role_code",
            "role_name",
            "competency_code",
            "competency_name",
            "scenario_profile",
        ):
            if row[field] != registered[field]:
                raise ValueError(
                    f"Registry mismatch: {family_id}, {field}"
                )

        question = normalize(row["interview_question"])

        if not question:
            raise ValueError(
                f"Empty interview question: {family_id}"
            )

        if question in seen_questions:
            raise ValueError(
                f"Duplicate validation question: {family_id}"
            )

        if question in development_questions:
            raise ValueError(
                f"Development question reused: {family_id}"
            )

        seen_questions.add(question)

        rubric_file = RUBRICS / row["rubric_file"]

        if not rubric_file.is_file():
            raise FileNotFoundError(rubric_file)

        rubric = json.loads(
            rubric_file.read_text(encoding="utf-8")
        )

        if rubric["rubric_id"] != row["rubric_id"]:
            raise ValueError(
                f"Rubric ID mismatch: {family_id}"
            )

        if len(rubric["criteria"]) != 3:
            raise ValueError(
                f"Expected three rubric criteria: {family_id}"
            )

        rubric_hashes[row["rubric_file"]] = digest(
            rubric_file
        )

        if row["candidate_responses_generated"] != "NO":
            raise ValueError(
                f"Unexpected generation status: {family_id}"
            )

    report = {
        "audit": "ESDSA validation scenario integrity",
        "version": "v2",
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "validation_families": len(scenarios),
        "competencies": len(competency_counts),
        "families_per_competency": dict(
            sorted(competency_counts.items())
        ),
        "planned_candidate_responses": 24 * 9,
        "validation_scenarios_sha256": digest(SCENARIOS),
        "registry_sha256": digest(REGISTRY),
        "development_scenarios_sha256": digest(DEVELOPMENT),
        "policy_freeze_sha256": digest(POLICY_FREEZE),
        "evaluation_freeze_sha256": digest(
            EVALUATION_FREEZE
        ),
        "rubric_sha256": rubric_hashes,
        "checks": {
            "partition_integrity": "PASS",
            "family_id_uniqueness": "PASS",
            "competency_coverage": "PASS",
            "exact_question_uniqueness": "PASS",
            "rubric_consistency": "PASS",
            "development_family_separation": "PASS",
            "policy_freeze_present": "PASS",
            "evaluation_freeze_present": "PASS",
        },
        "limitations": [
            "Exact-text checks cannot guarantee conceptual novelty.",
            "Scenario content has not been independently expert-reviewed.",
            "Reference decisions have not been adjudicated.",
            "No candidate responses have been generated.",
            "This audit does not modify or evaluate TEST families.",
        ],
    }

    REPORT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("ESDSA VALIDATION SCENARIO INTEGRITY")
    print("=" * 65)
    print("Validation families:", len(scenarios))
    print("Competencies:", len(competency_counts))
    print("Families per competency: 2")
    print("Planned candidate responses:", 24 * 9)
    print("Partition integrity: PASS")
    print("Question uniqueness: PASS")
    print("Rubric consistency: PASS")
    print("Development family separation: PASS")
    print("Policy freeze: FOUND")
    print("Evaluation freeze: FOUND")
    print("API calls: NONE")
    print()
    print("Validation SHA256:", digest(SCENARIOS))
    print("Saved:", REPORT)


if __name__ == "__main__":
    main()
