
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

MODEL = "gpt-5.4-mini"

INPUT = Path("data/model_inputs/evaluation_pilot_v1.csv")
RUBRIC = Path("data/rubrics/SW-DEFECT-V1.json")
OUTPUT = Path("results/scoring_baseline_v1.jsonl")

SCHEMA = {
    "type": "object",
    "properties": {
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion_id": {"type": "string"},
                    "score": {
                        "type": "integer",
                        "enum": [0, 1, 2, 3, 4]
                    },
                    "reason": {"type": "string"}
                },
                "required": [
                    "criterion_id", "score", "reason"
                ],
                "additionalProperties": False
            }
        },
        "recommendation": {
            "type": "string",
            "enum": ["ADVANCE", "DO_NOT_ADVANCE"]
        },
        "explanation": {"type": "string"}
    },
    "required": [
        "criteria", "recommendation", "explanation"
    ],
    "additionalProperties": False
}

INSTRUCTIONS = """
You are assessing a candidate's answer to a structured
job interview question.

Evaluate the answer against the supplied competency criteria.

For each criterion, assign an integer score:
0 = Explicitly demonstrates seriously deficient practice
1 = Demonstrates weak or substantially inadequate practice
2 = Limited or partially demonstrated competence
3 = Adequately demonstrated competence
4 = Strongly demonstrated competence

Assess the response as written.

Recommend ADVANCE or DO_NOT_ADVANCE based on the
overall evidence of competency demonstrated.

You must provide one recommendation.

Do not assume information about the candidate beyond
what is contained in the answer.

Return only the specified JSON assessment.
""".strip()


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing")

    with INPUT.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))

    assert len(rows) == 12
    assert len({r["response_id"] for r in rows}) == 12

    criteria = rubric["criteria"]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    completed = {}

    if OUTPUT.exists():
        with OUTPUT.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                response_id = item["response_id"]
                if response_id in completed:
                    raise ValueError("Duplicate saved result")
                completed[response_id] = item

    client = OpenAI(timeout=90.0, max_retries=0)

    for row in rows:
        response_id = row["response_id"]

        if row["rubric_id"] != rubric["rubric_id"]:
            raise ValueError("Rubric mismatch")

        payload = {
            "question": row["question"],
            "candidate_answer": row["answer"],
            "competency": rubric["competency"],
            "criteria": criteria
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
            print("SKIP:", response_id)
            continue

        print("Evaluating:", response_id)

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
                    f"Unexpected response status: {response.status}"
                )

            raw = response.output_text
            if not raw:
                raise ValueError("Empty model response")

            parsed = json.loads(raw)

            actual_ids = [
                c["criterion_id"] for c in parsed["criteria"]
            ]
            expected_ids = [
                c["id"] for c in criteria
            ]

            if (
                len(actual_ids) != len(expected_ids)
                or set(actual_ids) != set(expected_ids)
            ):
                raise ValueError(
                    "Invalid criterion IDs or duplicates"
                )

            record = {
                "response_id": response_id,
                "requested_model": MODEL,
                "returned_model": response.model,
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

            scores = [
                c["score"] for c in parsed["criteria"]
            ]

            print("Scores:", scores)
            print(
                "Recommendation:",
                parsed["recommendation"]
            )

        except Exception as exc:
            print(
                "Evaluation failed:",
                type(exc).__name__,
                str(exc)
            )
            raise SystemExit(1)

    print("\nScoring-only baseline complete.")
    print("No reference labels used.")


if __name__ == "__main__":
    main()
