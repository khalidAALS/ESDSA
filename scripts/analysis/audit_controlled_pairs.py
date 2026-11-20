
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

INPUT = Path("data/model_inputs/controlled_pairs_v1.csv")
RUBRIC = Path("data/rubrics/SW-DEFECT-V1.json")
OUTPUT = Path("results/controlled_evidence_audit_v1.jsonl")


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def answer_hash(answer):
    return hashlib.sha256(
        answer.encode("utf-8")
    ).hexdigest()


def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing")

    responses = read_csv(INPUT)
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))

    assert len(responses) == 6
    assert len({r["response_id"] for r in responses}) == 6

    unique_answers = {}

    for row in responses:
        unique_answers.setdefault(
            row["answer"], []
        ).append(row["response_id"])

    assert len(unique_answers) == 4

    completed = {}

    if OUTPUT.exists():
        with OUTPUT.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                record = json.loads(line)
                key = record["answer_sha256"]

                if key in completed:
                    raise ValueError("Duplicate saved audit")

                completed[key] = record

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    client = OpenAI(timeout=90.0, max_retries=0)

    print("ESDSA — CONTROLLED EVIDENCE AUDIT")
    print("Unique responses:", len(unique_answers))
    print("Reference labels: NOT LOADED")
    print("Original recommendations: NOT LOADED")

    for answer, response_ids in unique_answers.items():
        matching_rows = [
            row for row in responses
            if row["answer"] == answer
        ]

        question = matching_rows[0]["question"]

        if any(
            row["question"] != question
            or row["rubric_id"] != rubric["rubric_id"]
            for row in matching_rows
        ):
            raise ValueError("Inconsistent grouped inputs")

        payload = {
            "question": question,
            "candidate_answer": answer,
            "competency": rubric["competency"],
            "criteria": rubric["criteria"]
        }

        key = answer_hash(answer)

        run_hash = fingerprint({
            "model": MODEL,
            "instructions": INSTRUCTIONS,
            "payload": payload,
            "schema": SCHEMA
        })

        if key in completed:
            saved = completed[key]

            if saved["run_sha256"] != run_hash:
                raise ValueError("Audit configuration changed")

            if set(saved["response_ids"]) != set(response_ids):
                raise ValueError("Response mapping changed")

            print("SKIP:", response_ids)
            continue

        print("\nAuditing:", response_ids)

        try:
            response = client.responses.create(
                model=MODEL,
                instructions=INSTRUCTIONS,
                input=json.dumps(
                    payload, ensure_ascii=False
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
                answer
            )

            supported = determine_support(assessment)

            record = {
                "response_ids": response_ids,
                "answer_sha256": key,
                "run_sha256": run_hash,
                "requested_model": MODEL,
                "returned_model": response.model,
                "timestamp_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
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
                        record, ensure_ascii=False
                    ) + "\n"
                )

            print("Evidence-supported outcome:", supported)
            print("Excerpt warnings:", len(warnings))
            print("Saved:", OUTPUT)

        except Exception as exc:
            print(
                "Audit failed:",
                type(exc).__name__,
                str(exc)
            )
            raise SystemExit(1)

    print("\nControlled evidence audit complete.")
    print("No reference labels or original recommendations accessed.")


if __name__ == "__main__":
    main()
