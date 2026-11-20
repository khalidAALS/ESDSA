
# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

INPUT = Path("data/model_inputs/evaluation_prompts_v1.jsonl")
RESULTS = Path("results")
DEFAULT_MODEL = "gpt-5.4-mini"

STATUSES = [
    "POSITIVE_EVIDENCE",
    "NEGATIVE_EVIDENCE",
    "INSUFFICIENT_EVIDENCE"
]

DECISIONS = [
    "ADVANCE",
    "DO_NOT_ADVANCE",
    "DEFER"
]

SCHEMA = {
    "type": "object",
    "properties": {
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion_id": {"type": "string"},
                    "evidence_status": {
                        "type": "string",
                        "enum": STATUSES
                    },
                    "supporting_excerpt": {"type": "string"},
                    "explanation": {"type": "string"}
                },
                "required": [
                    "criterion_id",
                    "evidence_status",
                    "supporting_excerpt",
                    "explanation"
                ],
                "additionalProperties": False
            }
        },
        "recommendation": {
            "type": "string",
            "enum": DECISIONS
        },
        "recommendation_reason": {"type": "string"}
    },
    "required": [
        "criteria",
        "recommendation",
        "recommendation_reason"
    ],
    "additionalProperties": False
}



def validate_result(result, expected_ids, answer):
    criteria = result["criteria"]
    actual_ids = [c["criterion_id"] for c in criteria]

    if len(criteria) != len(expected_ids):
        raise ValueError("Incorrect criterion count")

    if set(actual_ids) != set(expected_ids):
        raise ValueError("Missing or duplicate criterion IDs")

    warnings = []

    for item in criteria:
        excerpt = item["supporting_excerpt"]

        if excerpt and excerpt not in answer:
            warnings.append({
                "criterion_id": item["criterion_id"],
                "issue": "EXCERPT_NOT_VERBATIM",
                "excerpt": excerpt
            })

    return warnings



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    if args.limit < 1:
        raise SystemExit("--limit must be positive")

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not configured")

    if not INPUT.exists():
        raise SystemExit(f"Missing input: {INPUT}")

    with INPUT.open(encoding="utf-8") as f:
        records = [
            json.loads(line)
            for line in f if line.strip()
        ]

    selected = records[:args.limit]
    RESULTS.mkdir(parents=True, exist_ok=True)

    safe_model = args.model.replace("/", "_")
    output = RESULTS / f"pilot_{safe_model}.jsonl"

    completed = set()

    if output.exists():
        with output.open(encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                completed.add(record["response_id"])

    client = OpenAI(timeout=90.0, max_retries=0)

    for record in selected:
        response_id = record["response_id"]

        if response_id in completed:
            print(f"SKIP: {response_id}")
            continue

        payload = record["input"]
        expected_ids = [
            c["id"] for c in payload["criteria"]
        ]

        prompt_hash = hashlib.sha256(
            json.dumps(
                record,
                sort_keys=True,
                ensure_ascii=False
            ).encode("utf-8")
        ).hexdigest()

        print(f"Evaluating: {response_id}")

        try:
            response = client.responses.create(
                model=args.model,
                instructions=record["instructions"],
                input=json.dumps(
                    payload, ensure_ascii=False
                ),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "interview_assessment",
                        "strict": True,
                        "schema": SCHEMA
                    }
                },
                store=False
            )

            if response.status != "completed":
                raise RuntimeError(
                    f"Response status: {response.status}"
                )

            raw_output = response.output_text
            result = json.loads(raw_output)


            validation_warnings = validate_result(
                result,
                expected_ids,
                payload["candidate_answer"]
            )


            output_record = {
                "response_id": response_id,
                "requested_model": args.model,
                "returned_model": response.model,
                "api_response_id": response.id,
                "timestamp_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "prompt_sha256": prompt_hash,
                "raw_output": raw_output,
                "parsed_output": result,
                "validation_warnings": validation_warnings,
                "input_tokens": (
                    response.usage.input_tokens
                    if response.usage else None
                ),
                "output_tokens": (
                    response.usage.output_tokens
                    if response.usage else None
                )
            }

            with output.open(
                "a", encoding="utf-8"
            ) as f:
                f.write(json.dumps(
                    output_record, ensure_ascii=False
                ) + "\n")

            completed.add(response_id)

            print("Recommendation:", result["recommendation"])
            print("Criterion assessments:")

            for item in result["criteria"]:
                print(
                    f"  {item['criterion_id']}: "
                    f"{item['evidence_status']}"
                )

            print("Saved:", output)
            
            
            if validation_warnings:
                print("EVIDENCE VALIDATION WARNINGS:")
                for warning in validation_warnings:
                    print(warning)


        except Exception as exc:
            print(f"Evaluation failed: {type(exc).__name__}")
            print(str(exc))
            raise SystemExit(1)

    print("Evaluation run finished.")


if __name__ == "__main__":
    main()

