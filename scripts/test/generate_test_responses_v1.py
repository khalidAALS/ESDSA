

"""ESDSA TEST response generation.

Uses the original development generator's unchanged:
- model
- instructions
- response schema
- validation rules
- API configuration

24 TEST families x 9 answers = 216 responses.

No evaluator inference, reference annotation, or policy changes.
Resumable, with one raw JSON file per completed family.
"""

# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

import argparse
import csv
import hashlib
import json
import os

from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

import generate_development_responses_v1 as original


ROOT = Path(__file__).resolve().parents[2]

SCENARIOS = ROOT / "data/benchmark/test_scenarios_v1.csv"

SCENARIO_MANIFEST = (
    ROOT / "data/benchmark/test_scenarios_manifest_v1.json"
)

VALIDATION_PLAN = (
    ROOT / "data/benchmark/validation_generation_plan_v1.json"
)

RUBRIC_DIR = ROOT / "data/benchmark/rubrics_v1"

ORIGINAL_GENERATOR = (
    ROOT / "archive/frozen_originals/generate_development_responses_v1.py"
)

OUT_DIR = ROOT / "results/test_generation_v1"
BATCH_DIR = OUT_DIR / "batches"

CONSOLIDATED = OUT_DIR / "test_responses_v1.csv"
MANIFEST = OUT_DIR / "test_generation_manifest_v1.json"

MODEL = original.MODEL

EXPECTED_MODEL_VERSION = "gpt-5.4-mini-2026-03-17"

EXPECTED_FAMILIES = 24
EXPECTED_RESPONSES = 216


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def load_json(path):
    require(path.is_file(), f"Missing file: {path}")

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def read_csv(path):
    require(path.is_file(), f"Missing file: {path}")

    with path.open(
        encoding="utf-8-sig",
        newline=""
    ) as handle:
        return list(csv.DictReader(handle))


def save_json_new(path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "x",
        encoding="utf-8",
    ) as handle:
        json.dump(
            data,
            handle,
            indent=2,
            ensure_ascii=False,
        )
        handle.write("\n")


def write_csv_new(path, rows, columns):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "x",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
            extrasaction="raise",
        )

        writer.writeheader()
        writer.writerows(rows)


def verify_original_protocol():
    plan = load_json(VALIDATION_PLAN)

    require(
        sha256_file(ORIGINAL_GENERATOR)
        == plan["generation_script_sha256"],
        "Original generator changed since validation plan",
    )

    require(
        sha256_text(original.INSTRUCTIONS)
        == plan["instructions_sha256"],
        "Original generation instructions changed",
    )

    schema_hash = sha256_text(
        json.dumps(
            original.SCHEMA,
            sort_keys=True,
            ensure_ascii=False,
        )
    )

    require(
        schema_hash == plan["schema_sha256"],
        "Original generation schema mismatch",
    )

    require(
        MODEL == plan["requested_model"],
        "Original generation model mismatch",
    )

    require(
        MODEL == "gpt-5.4-mini",
        "Unexpected generation model",
    )

    require(
        len(original.EXPECTED) == 9,
        "Unexpected original generation combinations",
    )

    require(
        plan["expected_families"] == 24
        and plan["expected_responses"] == 216,
        "Validation generation design mismatch",
    )

    require(
        plan["explicit_temperature"] is None
        and plan["explicit_top_p"] is None
        and plan["explicit_seed"] is None,
        "Unexpected original sampling configuration",
    )

    return plan


def make_question(scenario):
    context = scenario["scenario_context"].strip()
    question = scenario["interview_question"].strip()

    require(
        bool(context) and bool(question),
        "Empty scenario context or question",
    )

    return (
        f"Scenario: {context}\n\n"
        f"Interview question: {question}"
    )


def prepare_family(scenario):
    fid = scenario["family_id"]

    require(
        scenario["partition"] == "TEST",
        f"Non-TEST family: {fid}",
    )

    require(
        scenario["candidate_responses_generated"] == "NO",
        f"Unexpected source generation status: {fid}",
    )

    rubric_path = (
        RUBRIC_DIR / scenario["rubric_file"]
    )

    require(
        rubric_path.is_file(),
        f"Missing rubric: {fid}",
    )

    rubric = load_json(rubric_path)

    require(
        rubric["rubric_id"] == scenario["rubric_id"],
        f"Rubric identifier mismatch: {fid}",
    )

    require(
        rubric["competency_code"]
        == scenario["competency_code"],
        f"Rubric competency mismatch: {fid}",
    )

    require(
        len(rubric["criteria"]) == 3,
        f"Expected three criteria: {fid}",
    )

    require(
        rubric["evidence_statuses"]
        == list(original.STATUSES)
        if hasattr(original, "STATUSES")
        else set(rubric["evidence_statuses"])
        == {
            "POSITIVE_EVIDENCE",
            "NEGATIVE_EVIDENCE",
            "INSUFFICIENT_EVIDENCE",
        },
        f"Unexpected evidence statuses: {fid}",
    )

    payload = {
        "family_id": fid,
        "role": scenario["role_name"],
        "competency": scenario["competency_name"],
        "question": make_question(scenario),
        "rubric": {
            "criteria": rubric["criteria"],
            "evidence_statuses": rubric["evidence_statuses"],
        },
    }

    configuration = {
        "model": MODEL,
        "instructions": original.INSTRUCTIONS,
        "payload": payload,
        "schema": original.SCHEMA,
    }

    run_hash = sha256_text(
        json.dumps(
            configuration,
            sort_keys=True,
            ensure_ascii=False,
        )
    )

    return {
        "scenario": scenario,
        "rubric": rubric,
        "rubric_path": rubric_path,
        "payload": payload,
        "run_sha256": run_hash,
        "path": BATCH_DIR / f"{fid}.json",
    }


def validate_batch(batch, prepared):
    fid = prepared["scenario"]["family_id"]

    require(
        batch["family_id"] == fid,
        f"Saved family mismatch: {fid}",
    )

    require(
        batch["partition"] == "TEST",
        f"Saved partition mismatch: {fid}",
    )

    require(
        batch["requested_model"] == MODEL,
        f"Saved requested model mismatch: {fid}",
    )

    require(
        batch["returned_model"] == EXPECTED_MODEL_VERSION,
        f"Saved returned model mismatch: {fid}",
    )

    require(
        batch["run_sha256"] == prepared["run_sha256"],
        f"Saved generation configuration mismatch: {fid}",
    )

    require(
        batch["rubric_sha256"]
        == sha256_file(prepared["rubric_path"]),
        f"Saved rubric hash mismatch: {fid}",
    )

    require(
        batch["scenario_sha256"] == sha256_file(SCENARIOS),
        f"Saved scenario file hash mismatch: {fid}",
    )

    items = batch["responses"]

    original.validate_generated(items)

    parsed_raw = json.loads(batch["raw_output"])

    require(
        parsed_raw["responses"] == items,
        f"Saved raw/parsed response mismatch: {fid}",
    )

    return items


def generate_family(client, prepared):
    fid = prepared["scenario"]["family_id"]

    response = client.responses.create(
        model=MODEL,
        instructions=original.INSTRUCTIONS,
        input=json.dumps(
            prepared["payload"],
            ensure_ascii=False,
        ),
        text={
            "format": {
                "type": "json_schema",
                "name": "esdsa_development_responses",
                "strict": True,
                "schema": original.SCHEMA,
            }
        },
        store=False,
    )

    require(
        response.status == "completed",
        f"Incomplete API response: {fid}",
    )

    require(
        response.model == EXPECTED_MODEL_VERSION,
        f"Unexpected model version: {fid}",
    )

    require(
        bool(response.output_text),
        f"Empty API output: {fid}",
    )

    parsed = json.loads(response.output_text)
    items = parsed["responses"]

    original.validate_generated(items)

    batch = {
        "experiment": "ESDSA_TEST_GENERATION_V1",
        "partition": "TEST",
        "family_id": fid,
        "requested_model": MODEL,
        "returned_model": response.model,
        "api_response_id": response.id,
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "run_sha256": prepared["run_sha256"],
        "scenario_sha256": sha256_file(SCENARIOS),
        "rubric_sha256": sha256_file(
            prepared["rubric_path"]
        ),
        "responses": items,
        "raw_output": response.output_text,
        "input_tokens": (
            response.usage.input_tokens
            if response.usage else None
        ),
        "output_tokens": (
            response.usage.output_tokens
            if response.usage else None
        ),
        "generation_conditions_are_reference_labels": False,
    }

    validate_batch(batch, prepared)

    save_json_new(prepared["path"], batch)

    return batch


def consolidate(prepared_families):
    if CONSOLIDATED.exists() or MANIFEST.exists():
        require(
            CONSOLIDATED.exists() and MANIFEST.exists(),
            "Partial final outputs exist; manual inspection required",
        )

        manifest = load_json(MANIFEST)

        require(
            manifest["status"] == "COMPLETE",
            "Existing generation manifest is not complete",
        )

        require(
            sha256_file(CONSOLIDATED)
            == manifest["consolidated_sha256"],
            "Existing consolidated file hash mismatch",
        )

        require(
            len(read_csv(CONSOLIDATED)) == 216,
            "Existing consolidated response count mismatch",
        )

        print("Final consolidated outputs already verified.")
        return

    rows = []
    batch_hashes = {}
    models = set()

    for prepared in prepared_families:
        path = prepared["path"]

        require(
            path.is_file(),
            f"Missing completed family: {path.name}",
        )

        batch = load_json(path)
        validate_batch(batch, prepared)

        scenario = prepared["scenario"]
        fid = scenario["family_id"]
        models.add(batch["returned_model"])

        batch_hashes[path.name] = sha256_file(path)

        pairs = {
            (item["condition"], item["variant"]): item
            for item in batch["responses"]
        }

        for condition in original.CONDITIONS:
            for variant in original.VARIANTS:
                item = pairs[(condition, variant)]
                answer = item["answer"].strip()

                rows.append({
                    "response_id": (
                        f"{fid}__{condition}__{variant}"
                    ),
                    "family_id": fid,
                    "partition": "TEST",
                    "generation_condition": condition,
                    "variant": variant,
                    "answer": answer,
                    "answer_sha256": sha256_text(answer),
                    "returned_model": batch["returned_model"],
                    "run_sha256": batch["run_sha256"],
                })

    require(
        len(rows) == EXPECTED_RESPONSES,
        "Incorrect consolidated response count",
    )

    require(
        len({row["response_id"] for row in rows}) == 216,
        "Duplicate response identifiers",
    )

    require(
        models == {EXPECTED_MODEL_VERSION},
        "Inconsistent generation models",
    )

    columns = [
        "response_id",
        "family_id",
        "partition",
        "generation_condition",
        "variant",
        "answer",
        "answer_sha256",
        "returned_model",
        "run_sha256",
    ]

    write_csv_new(CONSOLIDATED, rows, columns)

    manifest = {
        "experiment": "ESDSA_TEST_GENERATION_V1",
        "status": "COMPLETE",
        "partition": "TEST",
        "completed_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "families": EXPECTED_FAMILIES,
        "responses": EXPECTED_RESPONSES,
        "responses_per_family": 9,
        "requested_model": MODEL,
        "returned_model": EXPECTED_MODEL_VERSION,
        "original_generator_sha256": sha256_file(
            ORIGINAL_GENERATOR
        ),
        "original_instructions_sha256": sha256_text(
            original.INSTRUCTIONS
        ),
        "original_schema_sha256": sha256_text(
            json.dumps(
                original.SCHEMA,
                sort_keys=True,
                ensure_ascii=False,
            )
        ),
        "test_scenarios_sha256": sha256_file(SCENARIOS),
        "test_scenario_manifest_sha256": sha256_file(
            SCENARIO_MANIFEST
        ),
        "batch_sha256": batch_hashes,
        "consolidated_sha256": sha256_file(CONSOLIDATED),
        "independent_reference_labels": False,
        "reference_annotation_completed": False,
        "esdsa_evaluation_completed": False,
        "frozen_policy_modified": False,
        "limitations": [
            "Synthetic model-generated answers.",
            "Generation conditions are experimental design "
            "metadata, not validated reference decisions.",
            "TEST questions were authored after validation "
            "analysis and this must be disclosed.",
            "The scenario context and question are combined "
            "inside the original generation question field.",
        ],
    }

    save_json_new(MANIFEST, manifest)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--run",
        action="store_true",
        help="Generate TEST answers; default is dry run",
    )

    args = parser.parse_args()

    print("ESDSA — TEST RESPONSE GENERATION")
    print("=" * 65)
    print("Mode:", "API RUN" if args.run else "DRY RUN")
    print("Model:", MODEL)
    print("Original generation instructions: UNCHANGED")
    print("TEST only: 24 families x 9 responses")
    print()

    plan = verify_original_protocol()
    scenario_manifest = load_json(SCENARIO_MANIFEST)

    require(
        scenario_manifest["status"]
        == "PREPARED_NOT_GENERATED",
        "Unexpected TEST scenario manifest status",
    )

    require(
        scenario_manifest["test_scenarios_sha256"]
        == sha256_file(SCENARIOS),
        "TEST scenarios changed after preparation",
    )

    scenarios = read_csv(SCENARIOS)

    require(
        len(scenarios) == EXPECTED_FAMILIES,
        "Incorrect TEST scenario count",
    )

    require(
        len({
            row["family_id"] for row in scenarios
        }) == EXPECTED_FAMILIES,
        "Duplicate TEST family IDs",
    )

    prepared = [
        prepare_family(row)
        for row in scenarios
    ]

    completed = {}

    for family in prepared:
        path = family["path"]

        if path.exists():
            batch = load_json(path)
            validate_batch(batch, family)
            completed[family["scenario"]["family_id"]] = batch

    print("Families prepared:", len(prepared))
    print("Previously generated:", len(completed))
    print(
        "Remaining API requests:",
        len(prepared) - len(completed),
    )
    print("Rubric protocol:", plan["rubric_protocol"])
    print("Reference labels: NOT USED")
    print("ESDSA evaluator: NOT RUN")
    print("Frozen policy: NOT MODIFIED")
    print()

    if not args.run:
        print("Dry run passed.")
        print("No API calls made.")
        return

    require(
        os.getenv("OPENAI_API_KEY"),
        "OPENAI_API_KEY is missing",
    )

    client = OpenAI(
        timeout=120.0,
        max_retries=0,
    )

    for index, family in enumerate(prepared, start=1):
        fid = family["scenario"]["family_id"]

        if fid in completed:
            print(f"[{index}/24] SKIP: {fid}")
            continue

        print(
            f"[{index}/24] Generating: {fid}",
            flush=True,
        )

        try:
            batch = generate_family(client, family)

        except Exception as exc:
            print(
                "Generation stopped:",
                type(exc).__name__,
                str(exc),
                flush=True,
            )

            print(
                "Completed families remain saved. "
                "Rerun --run to resume."
            )
            raise SystemExit(1) from exc

        completed[fid] = batch

        print(
            f"PASS: {fid} | 9 responses",
            flush=True,
        )

    consolidate(prepared)

    print()
    print("=" * 65)
    print("TEST GENERATION: COMPLETE")
    print("Families: 24/24")
    print("Responses: 216/216")
    print("Model:", EXPECTED_MODEL_VERSION)
    print("Consolidated:", CONSOLIDATED.relative_to(ROOT))
    print("Manifest:", MANIFEST.relative_to(ROOT))
    print("Independent references: NOT ESTABLISHED")
    print("ESDSA evaluation: NOT RUN")
    print("Frozen policy: NOT MODIFIED")


if __name__ == "__main__":
    main()
