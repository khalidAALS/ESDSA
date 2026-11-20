

"""Prepare a frozen-input validation generation plan.

No API calls. No candidate responses generated.
Reads the original development generator's instructions and schema.
Does not modify development, validation scenario or test files.
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
import runpy
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data" / "benchmark"

SCENARIOS = BASE / "validation_scenarios_v2.csv"
INTEGRITY = BASE / "validation_scenarios_integrity_v2.json"
RUBRICS = BASE / "rubrics_v1"

GENERATOR = ROOT / "archive/frozen_originals/generate_development_responses_v1.py"
PROTOCOL = (
    BASE / "policy_freeze_v2/"
    "esdsa_evaluation_protocol_freeze_v1.json"
)

OUTPUT = BASE / "validation_generation_plan_v1.json"

EXPECTED_SCENARIO_SHA256 = (
    "23bc13887d81d3e2174e095b4ff4ffe1bf9a279991257c32e0c62703b1d0d9e5"
)

CONDITIONS = {
    "SUFFICIENT", "INSUFFICIENT", "NEGATIVE"
}

VARIANTS = {
    "CANONICAL", "CONVERSATIONAL", "CONCISE"
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha256(value):
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def read_csv(path):
    with path.open(
        encoding="utf-8-sig", newline=""
    ) as f:
        return list(csv.DictReader(f))


def main():
    if OUTPUT.exists():
        raise FileExistsError(
            "Generation plan already exists. "
            "It will not be overwritten."
        )

    for path in (
        SCENARIOS, INTEGRITY, GENERATOR, PROTOCOL
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    actual_scenario_hash = sha256(SCENARIOS)

    if actual_scenario_hash != EXPECTED_SCENARIO_SHA256:
        raise ValueError(
            "Validation scenarios changed since integrity check."
        )

    integrity = json.loads(
        INTEGRITY.read_text(encoding="utf-8")
    )

    if (
        integrity["validation_scenarios_sha256"]
        != actual_scenario_hash
    ):
        raise ValueError(
            "Validation integrity fingerprint mismatch."
        )

    protocol = json.loads(
        PROTOCOL.read_text(encoding="utf-8")
    )

    original = protocol["scripts"][
        "generate_development_responses_v1.py"
    ]

    if sha256(GENERATOR) != original["sha256"]:
        raise ValueError(
            "Original generator differs from frozen protocol."
        )


    generator = runpy.run_path(str(GENERATOR))

    model = generator["MODEL"]
    instructions = generator["INSTRUCTIONS"]
    schema = generator["SCHEMA"]

    if model != "gpt-5.4-mini":
        raise ValueError("Unexpected generation model.")

    if (
        text_sha256(instructions)
        != original["prompt_sha256"]
    ):
        raise ValueError("Original generation prompt changed.")

    schema_options = schema[
        "properties"
    ]["responses"]["items"]["properties"]

    if (
        set(schema_options["condition"]["enum"])
        != CONDITIONS
        or set(schema_options["variant"]["enum"])
        != VARIANTS
    ):
        raise ValueError("Generation schema has changed.")

    rows = read_csv(SCENARIOS)

    if len(rows) != 24:
        raise ValueError("Expected 24 validation scenarios.")

    if len({
        r["family_id"] for r in rows
    }) != 24:
        raise ValueError("Duplicate validation family IDs.")

    counts = Counter(
        r["competency_code"] for r in rows
    )

    if (
        len(counts) != 12
        or any(n != 2 for n in counts.values())
    ):
        raise ValueError(
            "Expected two families per competency."
        )

    batches = []

    for row in rows:
        if row["partition"] != "VALIDATION":
            raise ValueError(
                "A non-validation family was included."
            )

        rubric_path = RUBRICS / row["rubric_file"]

        rubric = json.loads(
            rubric_path.read_text(encoding="utf-8")
        )

        if rubric["rubric_id"] != row["rubric_id"]:
            raise ValueError(
                f"Rubric mismatch: {row['family_id']}"
            )

        if len(rubric["criteria"]) != 3:
            raise ValueError(
                f"Unexpected rubric size: {row['family_id']}"
            )


        payload = {
            "family_id": row["family_id"],
            "role": row["role_name"],
            "competency": row["competency_name"],
            "question": row["interview_question"],
            "rubric": {
                "criteria": rubric["criteria"],
                "evidence_statuses": rubric[
                    "evidence_statuses"
                ],
            },
        }

        request_signature = {
            "model": model,
            "instructions": instructions,
            "payload": payload,
            "schema": schema,
        }

        run_hash = text_sha256(
            json.dumps(
                request_signature,
                sort_keys=True,
                ensure_ascii=False,
            )
        )

        batches.append({
            "family_id": row["family_id"],
            "competency_code": row["competency_code"],
            "scenario_profile": row["scenario_profile"],
            "payload": payload,
            "run_sha256": run_hash,
            "expected_responses": 9,
        })

    plan = {
        "experiment": "ESDSA_VALIDATION_GENERATION_V1",
        "status": "PREPARED_NOT_EXECUTED",
        "partition": "VALIDATION",
        "requested_model": model,
        "generation_script_sha256": sha256(GENERATOR),
        "instructions_sha256": text_sha256(instructions),
        "schema_sha256": text_sha256(
            json.dumps(schema, sort_keys=True)
        ),
        "scenario_file_sha256": actual_scenario_hash,
        "rubric_protocol": "Existing rubrics_v1",
        "explicit_temperature": None,
        "explicit_top_p": None,
        "explicit_seed": None,
        "expected_families": len(batches),
        "expected_responses": len(batches) * 9,
        "batches": batches,
        "safeguards": [
            "Use the original frozen generation instructions.",
            "Use the original strict JSON output schema.",
            "Keep validation outputs separate from development.",
            "Do not use provisional reference decisions "
            "in generation payloads.",
            "Record the actual returned model version.",
            "Inspect a small initial batch before continuing.",
            "Do not generate or evaluate TEST families.",
            "Review semantic equivalence separately.",
        ],
    }

    OUTPUT.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("ESDSA VALIDATION GENERATION PREFLIGHT")
    print("=" * 65)
    print("Scenario integrity: PASS")
    print("Original generator fingerprint: PASS")
    print("Original generation prompt: PASS")
    print("Original output schema: PASS")
    print("Rubric consistency: PASS")
    print("Validation families:", len(batches))
    print("Expected responses:", len(batches) * 9)
    print("Requested model:", model)
    print("Candidate responses generated: NO")
    print("API calls: NONE")
    print()
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
