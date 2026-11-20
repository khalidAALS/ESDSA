

"""Generate ESDSA validation responses in controlled, resumable batches.

At most three new API requests per execution.
Preserves raw output before validation.
Never modifies development or TEST data.
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
BASE = ROOT / "data/benchmark"
RESULTS = ROOT / "results"

PLAN_FILE = BASE / "validation_generation_plan_v1.json"
PROTOCOL_FILE = (
    BASE / "policy_freeze_v2"
    / "esdsa_evaluation_protocol_freeze_v1.json"
)
GENERATOR = ROOT / "archive/frozen_originals/generate_development_responses_v1.py"

BATCH_DIR = RESULTS / "validation_generation_batches_v1"

EXPECTED_RETURNED_MODEL = "gpt-5.4-mini-2026-03-17"
MAX_NEW_FAMILIES = 3


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_hash(value):
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_new(path, record):
    with path.open("x", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
        f.write("\n")


def verify_existing(path, batch, validator):
    saved = load_json(path)

    if saved.get("family_id") != batch["family_id"]:
        raise ValueError(f"Family mismatch in {path}")

    if saved.get("partition") != "VALIDATION":
        raise ValueError(f"Invalid partition in {path}")

    if saved.get("run_sha256") != batch["run_sha256"]:
        raise ValueError(f"Request fingerprint mismatch: {path}")

    if saved.get("returned_model") != EXPECTED_RETURNED_MODEL:
        raise ValueError(f"Returned model mismatch: {path}")

    if saved.get("validation_status") != "STRUCTURE_PASSED":
        raise ValueError(
            f"Saved batch requires inspection: {path}"
        )

    items = saved.get("responses")
    if not isinstance(items, list):
        raise ValueError(f"Missing responses: {path}")

    validator(items)


def main():
    for path in (PLAN_FILE, PROTOCOL_FILE, GENERATOR):
        if not path.is_file():
            raise FileNotFoundError(path)

    plan = load_json(PLAN_FILE)
    protocol = load_json(PROTOCOL_FILE)

    if (
        plan["status"] != "PREPARED_NOT_EXECUTED"
        or plan["partition"] != "VALIDATION"
        or plan["expected_families"] != 24
        or plan["expected_responses"] != 216
    ):
        raise ValueError("Unexpected generation plan")

    frozen = protocol["scripts"][
        "generate_development_responses_v1.py"
    ]

    if (
        file_hash(GENERATOR) != frozen["sha256"]
        or file_hash(GENERATOR)
            != plan["generation_script_sha256"]
    ):
        raise ValueError("Generator fingerprint mismatch")

    original = runpy.run_path(str(GENERATOR))

    model = original["MODEL"]
    instructions = original["INSTRUCTIONS"]
    schema = original["SCHEMA"]
    validator = original["validate_generated"]

    if (
        model != "gpt-5.4-mini"
        or model != plan["requested_model"]
        or text_hash(instructions) != frozen["prompt_sha256"]
        or text_hash(instructions) != plan["instructions_sha256"]
        or text_hash(
            json.dumps(schema, sort_keys=True)
        ) != plan["schema_sha256"]
    ):
        raise ValueError("Frozen generation protocol mismatch")

    batches = plan["batches"]

    if len(batches) != 24:
        raise ValueError("Expected 24 planned families")

    if len({
        b["family_id"] for b in batches
    }) != 24:
        raise ValueError("Duplicate planned family IDs")

    BATCH_DIR.mkdir(parents=True, exist_ok=True)

    completed = []
    pending = []

    for batch in batches:
        family_id = batch["family_id"]
        path = BATCH_DIR / f"{family_id}.json"

        signature = {
            "model": model,
            "instructions": instructions,
            "payload": batch["payload"],
            "schema": schema,
        }

        actual_hash = text_hash(
            json.dumps(
                signature,
                sort_keys=True,
                ensure_ascii=False,
            )
        )

        if actual_hash != batch["run_sha256"]:
            raise ValueError(
                f"Invalid request signature: {family_id}"
            )

        if path.exists():
            verify_existing(path, batch, validator)
            completed.append(family_id)
        else:
            pending.append(batch)

    if not pending:
        print("All 24 validation families are complete.")
        print("API calls: NONE")
        return

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not configured")

    selected = pending[:MAX_NEW_FAMILIES]

    print("ESDSA VALIDATION — CONTROLLED GENERATION")
    print("=" * 65)
    print("Already complete:", len(completed))
    print("Remaining before this run:", len(pending))
    print("New families this run:", len(selected))
    print("Maximum API requests:", MAX_NEW_FAMILIES)
    print("Requested model:", model)
    print("TEST partition: NOT ACCESSED")

    client = OpenAI(timeout=120.0, max_retries=0)

    for batch in selected:
        family_id = batch["family_id"]
        output = BATCH_DIR / f"{family_id}.json"

        print(f"\nGenerating: {family_id}", flush=True)

        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=json.dumps(
                batch["payload"],
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
            "family_id": family_id,
            "run_sha256": batch["run_sha256"],
            "requested_model": model,
            "returned_model": response.model,
            "response_id": response.id,
            "response_status": response.status,
            "usage": usage,
            "raw_output_text": raw_text,
            "responses": None,
            "validation_status": "PENDING",
        }

        save_new(output, saved)

        if response.status != "completed":
            raise RuntimeError(
                f"{family_id}: incomplete model response. "
                f"Raw record preserved at {output}"
            )

        if response.model != EXPECTED_RETURNED_MODEL:
            raise RuntimeError(
                f"{family_id}: model version changed to "
                f"{response.model}. Stop generation."
            )

        if not raw_text:
            raise ValueError(
                f"{family_id}: empty output. "
                f"Raw record preserved."
            )

        parsed = json.loads(raw_text)
        items = parsed["responses"]

        validator(items)

        saved["responses"] = items
        saved["validation_status"] = "STRUCTURE_PASSED"

        with output.open("w", encoding="utf-8") as f:
            json.dump(
                saved,
                f,
                indent=2,
                ensure_ascii=False,
            )
            f.write("\n")

        print(
            f"PASS: {family_id} | "
            f"{len(items)} responses | "
            f"{response.model}"
        )

    total_complete = len(completed) + len(selected)

    print("\n" + "=" * 65)
    print("Validation families complete:", total_complete, "/24")
    print("Responses saved:", total_complete * 9, "/216")
    print("New API requests this run:", len(selected))
    print("No development or TEST files modified.")

    if total_complete < 24:
        print(
            "Further families remain; do not rerun "
            "until this batch has been reviewed."
        )


if __name__ == "__main__":
    main()
