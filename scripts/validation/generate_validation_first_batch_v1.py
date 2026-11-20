

"""Generate the first ESDSA validation family using the frozen protocol.

Exactly one OpenAI API request.
Saves the result before performing structural checks.
Never overwrites an existing batch or changes development/test files.
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
import os
import runpy
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data" / "benchmark"
RESULTS = ROOT / "results"

PLAN = BASE / "validation_generation_plan_v1.json"
PROTOCOL = (
    BASE / "policy_freeze_v2"
    / "esdsa_evaluation_protocol_freeze_v1.json"
)
GENERATOR = ROOT / "archive/frozen_originals/generate_development_responses_v1.py"

FAMILY_ID = "ESDSA-SWE01-05"

BATCH_DIR = RESULTS / "validation_generation_batches_v1"
OUTPUT = BATCH_DIR / f"{FAMILY_ID}.json"

EXPECTED_RETURNED_MODEL = "gpt-5.4-mini-2026-03-17"


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def main():
    if OUTPUT.exists():
        raise SystemExit(
            f"Batch already saved: {OUTPUT}\n"
            "No API request was made. "
            "Do not regenerate this family."
        )

    for path in (PLAN, PROTOCOL, GENERATOR):
        if not path.is_file():
            raise FileNotFoundError(path)

    plan = json.loads(
        PLAN.read_text(encoding="utf-8")
    )

    protocol = json.loads(
        PROTOCOL.read_text(encoding="utf-8")
    )

    if plan["status"] != "PREPARED_NOT_EXECUTED":
        raise ValueError("Unexpected generation plan status")

    if plan["partition"] != "VALIDATION":
        raise ValueError("Not a validation plan")

    if plan["expected_families"] != 24:
        raise ValueError("Expected 24 validation families")

    if plan["expected_responses"] != 216:
        raise ValueError("Expected 216 planned responses")

    if sha256_file(GENERATOR) != plan[
        "generation_script_sha256"
    ]:
        raise ValueError("Generator differs from plan")

    frozen = protocol["scripts"][
        "generate_development_responses_v1.py"
    ]

    if sha256_file(GENERATOR) != frozen["sha256"]:
        raise ValueError("Generator differs from frozen protocol")

    original = runpy.run_path(str(GENERATOR))

    model = original["MODEL"]
    instructions = original["INSTRUCTIONS"]
    schema = original["SCHEMA"]
    validate_generated = original["validate_generated"]

    if model != "gpt-5.4-mini":
        raise ValueError("Unexpected requested model")

    if model != plan["requested_model"]:
        raise ValueError("Model does not match plan")

    if sha256_text(instructions) != frozen[
        "prompt_sha256"
    ]:
        raise ValueError("Frozen instructions mismatch")

    if sha256_text(instructions) != plan[
        "instructions_sha256"
    ]:
        raise ValueError("Plan instructions mismatch")

    schema_hash = sha256_text(
        json.dumps(schema, sort_keys=True)
    )

    if schema_hash != plan["schema_sha256"]:
        raise ValueError("Generation schema mismatch")

    batches = plan["batches"]

    if len(batches) != 24:
        raise ValueError("Incorrect number of planned batches")

    batch = batches[0]

    if batch["family_id"] != FAMILY_ID:
        raise ValueError(
            "First planned family is not the expected family"
        )

    payload = batch["payload"]

    if payload["family_id"] != FAMILY_ID:
        raise ValueError("Payload family mismatch")

    signature = {
        "model": model,
        "instructions": instructions,
        "payload": payload,
        "schema": schema,
    }

    request_hash = sha256_text(
        json.dumps(
            signature,
            sort_keys=True,
            ensure_ascii=False,
        )
    )

    if request_hash != batch["run_sha256"]:
        raise ValueError(
            "Request differs from the approved generation plan"
        )

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is not configured. "
            "No API request was made."
        )

    print("ESDSA VALIDATION — FIRST GENERATION BATCH")
    print("=" * 65)
    print("Family:", FAMILY_ID)
    print("Competency:", batch["competency_code"])
    print("Requested model:", model)
    print("Expected responses:", 9)
    print("API requests planned: 1")
    print("TEST partition: NOT ACCESSED")
    print()

    client = OpenAI(
        timeout=120.0,
        max_retries=0,
    )

    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=json.dumps(
            payload,
            ensure_ascii=False,
        ),
        text={
            "format": {
                "type": "json_schema",
                "name": "esdsa_development_responses",
                "strict": True,
                "schema": schema,
            }
        },
        store=False,
    )

    raw_text = response.output_text or ""

    usage = (
        response.usage.model_dump()
        if response.usage is not None
        else None
    )

    saved = {
        "experiment": "ESDSA_VALIDATION_GENERATION_V1",
        "partition": "VALIDATION",
        "family_id": FAMILY_ID,
        "run_sha256": request_hash,
        "requested_model": model,
        "returned_model": response.model,
        "response_id": response.id,
        "response_status": response.status,
        "usage": usage,
        "raw_output_text": raw_text,
        "responses": None,
        "validation_status": "PENDING",
    }

    BATCH_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT.open("x", encoding="utf-8") as f:
        json.dump(
            saved,
            f,
            indent=2,
            ensure_ascii=False,
        )
        f.write("\n")

    print("Raw model output saved:", OUTPUT)
    print("Returned model:", response.model)
    print("Response status:", response.status)

    if response.status != "completed":
        raise RuntimeError(
            "API response was not completed. "
            "Raw output has been preserved."
        )

    if response.model != EXPECTED_RETURNED_MODEL:
        raise RuntimeError(
            "Returned model version differs from development. "
            "Do not continue generating other families."
        )

    if not raw_text:
        raise ValueError(
            "Empty response text. "
            "Original output has been preserved."
        )

    parsed = json.loads(raw_text)
    items = parsed["responses"]

    validate_generated(items)

    if len(items) != 9:
        raise ValueError("Expected exactly nine responses")

    saved["responses"] = items
    saved["validation_status"] = "STRUCTURE_PASSED"

    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(
            saved,
            f,
            indent=2,
            ensure_ascii=False,
        )
        f.write("\n")

    print("\nSTRUCTURAL VALIDATION: PASS")
    print("Generated responses:", len(items))

    print("\nCondition / variant combinations:")
    for item in sorted(
        items,
        key=lambda x: (x["condition"], x["variant"])
    ):
        print(
            f"  {item['condition']:13} | "
            f"{item['variant']:14} | "
            f"{len(item['answer'])} characters"
        )

    print("\nSaved:", OUTPUT)
    print("No existing development or TEST files modified.")
    print("Do not generate the remaining batches yet.")


if __name__ == "__main__":
    main()
