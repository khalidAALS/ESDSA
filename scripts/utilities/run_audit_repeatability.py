
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
import os
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

from run_evidence_audit import (
    SCHEMA,
    INSTRUCTIONS,
    validate_assessment,
    determine_support,
    fingerprint
)

MODEL = "gpt-5.4-mini"
REPETITIONS = 10
SEED = 20261119

INPUT = Path(
    "data/model_inputs/challenge_benchmark_v2.csv"
)
RUBRIC = Path(
    "data/rubrics/SW-DEFECT-V1.json"
)
OUTPUT = Path(
    "results/audit_repeatability_f02_v1.jsonl"
)

TARGET_IDS = (
    "ESDSA-V2-0006",
    "ESDSA-V2-0007"
)


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_existing(path):
    if not path.exists():
        return {}

    completed = {}

    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)
            key = (
                record["response_id"],
                record["repetition"]
            )

            if key in completed:
                raise ValueError(
                    f"Duplicate saved evaluation: {key}"
                )

            completed[key] = record

    return completed


def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing")

    rows = read_csv(INPUT)

    selected = {
        row["response_id"]: row
        for row in rows
        if row["response_id"] in TARGET_IDS
    }

    if set(selected) != set(TARGET_IDS):
        raise ValueError("Target responses missing")

    rubric = json.loads(
        RUBRIC.read_text(encoding="utf-8")
    )

    if rubric["rubric_id"] != "SW-DEFECT-V1":
        raise ValueError("Unexpected rubric")

    if any(
        row["rubric_id"] != rubric["rubric_id"]
        for row in selected.values()
    ):
        raise ValueError("Input rubric mismatch")

    tasks = [
        (response_id, repetition)
        for response_id in TARGET_IDS
        for repetition in range(1, REPETITIONS + 1)
    ]

    rng = random.Random(SEED)
    rng.shuffle(tasks)

    completed = load_existing(OUTPUT)

    if not set(completed).issubset(set(tasks)):
        raise ValueError(
            "Saved results contain unexpected tasks"
        )

    OUTPUT.parent.mkdir(
        parents=True, exist_ok=True
    )

    client = OpenAI(
        timeout=90.0,
        max_retries=0
    )

    print("\nESDSA — F02 AUDIT REPEATABILITY")
    print("=" * 65)
    print("Model:", MODEL)
    print("Responses:", len(selected))
    print("Repetitions per response:", REPETITIONS)
    print("Total scheduled:", len(tasks))
    print("Previously completed:", len(completed))
    print("Reference labels: NOT LOADED")

    for response_id, repetition in tasks:
        row = selected[response_id]

        payload = {
            "question": row["question"],
            "candidate_answer": row["answer"],
            "competency": rubric["competency"],
            "criteria": rubric["criteria"]
        }

        run_hash = fingerprint({
            "model": MODEL,
            "instructions": INSTRUCTIONS,
            "payload": payload,
            "schema": SCHEMA
        })

        key = (response_id, repetition)

        if key in completed:
            saved = completed[key]

            if saved["run_sha256"] != run_hash:
                raise ValueError(
                    f"Configuration mismatch: {key}"
                )

            if saved["requested_model"] != MODEL:
                raise ValueError(
                    f"Model mismatch: {key}"
                )

            print(
                f"SKIP: {response_id} "
                f"repetition {repetition}"
            )
            continue

        print(
            f"\nEvaluating: {response_id} "
            f"| repetition {repetition}/{REPETITIONS}"
        )

        try:
            response = client.responses.create(
                model=MODEL,
                instructions=INSTRUCTIONS,
                input=json.dumps(
                    payload,
                    ensure_ascii=False
                ),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "evidence_audit",
                        "strict": True,
                        "schema": SCHEMA
                    }
                },
                store=False
            )

            if response.status != "completed":
                raise RuntimeError(
                    f"Unexpected status: {response.status}"
                )

            raw = response.output_text

            if not raw:
                raise ValueError("Empty model response")

            assessment = json.loads(raw)

            warnings = validate_assessment(
                assessment,
                rubric["criteria"],
                row["answer"]
            )

            supported = determine_support(
                assessment
            )

            c3 = [
                item for item in assessment["criteria"]
                if item["criterion_id"] == "C3"
            ]

            if len(c3) != 1:
                raise ValueError(
                    "Missing or duplicate C3 result"
                )

            record = {
                "experiment": "F02_AUDIT_REPEATABILITY_V1",
                "response_id": response_id,
                "repetition": repetition,
                "requested_model": MODEL,
                "returned_model": response.model,
                "api_response_id": response.id,
                "timestamp_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "run_sha256": run_hash,
                "candidate_answer_sha256": hashlib.sha256(
                    row["answer"].encode("utf-8")
                ).hexdigest(),
                "c3_evidence_status": (
                    c3[0]["evidence_status"]
                ),
                "evidence_supported_decision": supported,
                "parsed_output": assessment,
                "raw_output": raw,
                "validation_warnings": warnings,
                "input_tokens": (
                    response.usage.input_tokens
                    if response.usage else None
                ),
                "output_tokens": (
                    response.usage.output_tokens
                    if response.usage else None
                )
            }


            with OUTPUT.open(
                "a", encoding="utf-8"
            ) as f:
                f.write(
                    json.dumps(
                        record,
                        ensure_ascii=False
                    ) + "\n"
                )

            completed[key] = record

            print(
                "C3:",
                record["c3_evidence_status"]
            )
            print(
                "Recommendation:",
                supported
            )
            print(
                "Excerpt warnings:",
                len(warnings)
            )

        except Exception as exc:
            print(
                "Evaluation failed:",
                type(exc).__name__,
                str(exc)
            )
            raise SystemExit(1)

    print("\n" + "=" * 65)
    print("REPEATABILITY SUMMARY")
    print("=" * 65)

    for response_id in TARGET_IDS:
        subset = [
            completed[(response_id, repetition)]
            for repetition in range(1, REPETITIONS + 1)
        ]

        statuses = Counter(
            r["c3_evidence_status"]
            for r in subset
        )

        decisions = Counter(
            r["evidence_supported_decision"]
            for r in subset
        )

        print(f"\nResponse: {response_id}")
        print("C3 classifications:", dict(statuses))
        print("Recommendations:", dict(decisions))

    print("\nSaved:", OUTPUT)
    print("Total completed:", len(completed))
    print("Original experiment files unchanged.")
    print("Independent semantic validation: PENDING")


if __name__ == "__main__":
    main()
