
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
from run_scoring_baseline import (
    SCHEMA,
    INSTRUCTIONS,
    fingerprint
)

MODEL = "gpt-5.4-mini"

INPUT = Path("data/model_inputs/challenge_benchmark_v2.csv")
RUBRIC = Path("data/rubrics/SW-DEFECT-V1.json")
OUTPUT = Path("results/scoring_baseline_v2.jsonl")


def load_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_results(path):
    if not path.exists():
        return []

    with path.open(encoding="utf-8") as f:
        return [
            json.loads(line)
            for line in f if line.strip()
        ]


def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing")

    rows = load_csv(INPUT)
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    previous = load_results(OUTPUT)

    assert len(rows) == 8
    assert len({r["response_id"] for r in rows}) == 8

    completed = {}

    for record in previous:
        response_id = record["response_id"]

        if response_id in completed:
            raise ValueError("Duplicate saved result")

        completed[response_id] = record

    if not set(completed).issubset(
        {r["response_id"] for r in rows}
    ):
        raise ValueError("Unknown saved result IDs")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    client = OpenAI(timeout=90.0, max_retries=0)

    print("ESDSA — SCORING BASELINE V2")
    print("Responses:", len(rows))
    print("Model:", MODEL)
    print("Reference labels: NOT LOADED")

    for row in rows:
        response_id = row["response_id"]

        if row["rubric_id"] != rubric["rubric_id"]:
            raise ValueError("Rubric mismatch")

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

        if response_id in completed:
            if completed[response_id]["run_sha256"] != run_hash:
                raise ValueError(
                    f"Configuration mismatch: {response_id}"
                )

            if completed[response_id]["requested_model"] != MODEL:
                raise ValueError("Saved model mismatch")

            print("SKIP:", response_id)
            continue

        print("\nEvaluating:", response_id)

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
                        "name": "scoring_assessment",
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
                raise ValueError("Empty model output")

            parsed = json.loads(raw)

            expected_ids = {
                c["id"] for c in rubric["criteria"]
            }

            actual_ids = [
                c["criterion_id"]
                for c in parsed["criteria"]
            ]

            if (
                len(actual_ids) != len(expected_ids)
                or set(actual_ids) != expected_ids
            ):
                raise ValueError("Invalid criterion IDs")

            record = {
                "response_id": response_id,
                "requested_model": MODEL,
                "returned_model": response.model,
                "api_response_id": response.id,
                "timestamp_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "run_sha256": run_hash,
                "raw_output": raw,
                "parsed_output": parsed,
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

            print(
                "Scores:",
                [c["score"] for c in parsed["criteria"]]
            )
            print(
                "Recommendation:",
                parsed["recommendation"]
            )
            print("Saved:", OUTPUT)

        except Exception as exc:
            print(
                "Evaluation failed:",
                type(exc).__name__,
                str(exc)
            )
            raise SystemExit(1)

    print("\nScoring baseline v2 completed.")
    print("No reference labels accessed.")


if __name__ == "__main__":
    main()
