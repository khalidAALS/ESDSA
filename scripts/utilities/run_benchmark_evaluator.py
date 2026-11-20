
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

MODEL = "gpt-5.4-mini"

INPUT = Path("data/benchmark/development_responses_v1.csv")
RUBRIC_DIR = Path("data/benchmark/rubrics_v1")
OUTPUT = Path("results/benchmark_evidence_aware_v1.jsonl")

STATUSES = (
    "POSITIVE_EVIDENCE",
    "NEGATIVE_EVIDENCE",
    "INSUFFICIENT_EVIDENCE"
)

INSTRUCTIONS = """
You are assessing evidence presented in a synthetic
job-interview response for a research experiment.

Evaluate only the specified competency and its three
observable indicators.

For each indicator:
- POSITIVE_EVIDENCE: the answer clearly demonstrates it.
- NEGATIVE_EVIDENCE: the answer explicitly demonstrates
  materially deficient practice.
- INSUFFICIENT_EVIDENCE: the answer establishes neither.

Rules:
- Evaluate meaning, not fluency, length or writing style.
- Omission is not automatically negative evidence.
- Do not assume unmentioned actions were performed.
- Do not infer evidence from demographic characteristics.
- Consider the interview question and competency context.
- Quote an exact substring of the candidate answer
  supporting each positive or negative classification.
- For insufficient evidence, return an empty excerpt.
- Do not provide an overall hiring decision.
- Do not infer the intended experimental condition.
"""


def digest(value):
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_jsonl(path):
    if not path.exists():
        return {}

    result = {}

    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)
            response_id = record["response_id"]

            if response_id in result:
                raise ValueError(
                    f"Duplicate saved result: {response_id}"
                )

            result[response_id] = record

    return result


def schema():
    criterion = {
        "type": "object",
        "properties": {
            "criterion_id": {"type": "string"},
            "evidence_status": {
                "type": "string",
                "enum": list(STATUSES)
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

    return {
        "type": "object",
        "properties": {
            "criteria": {
                "type": "array",
                "items": criterion
            }
        },
        "required": ["criteria"],
        "additionalProperties": False
    }


SCHEMA = schema()


def evaluate_output(parsed, rubric, answer):
    items = parsed["criteria"]
    expected = [c["id"] for c in rubric["criteria"]]
    actual = [c["criterion_id"] for c in items]

    if (
        len(items) != 3
        or len(set(actual)) != 3
        or set(actual) != set(expected)
    ):
        raise ValueError("Invalid criterion coverage")

    warnings = []

    for item in items:
        status = item["evidence_status"]
        excerpt = item["supporting_excerpt"]

        if status not in STATUSES:
            raise ValueError("Invalid evidence status")

        if not item["explanation"].strip():
            raise ValueError("Missing explanation")

        if status == "INSUFFICIENT_EVIDENCE":
            if excerpt.strip():
                warnings.append({
                    "criterion_id": item["criterion_id"],
                    "issue": "EXCERPT_FOR_INSUFFICIENT"
                })
        elif not excerpt.strip():
            warnings.append({
                "criterion_id": item["criterion_id"],
                "issue": "MISSING_EVIDENCE_EXCERPT"
            })
        elif excerpt not in answer:
            stripped = excerpt.strip().strip('"“”').strip()

            warnings.append({
                "criterion_id": item["criterion_id"],
                "issue": (
                    "OUTER_QUOTES_ONLY"
                    if stripped in answer
                    else "UNVERIFIABLE_EXCERPT"
                )
            })

    statuses = [i["evidence_status"] for i in items]

    if "NEGATIVE_EVIDENCE" in statuses:
        decision = "DO_NOT_ADVANCE"
    elif all(s == "POSITIVE_EVIDENCE" for s in statuses):
        decision = "ADVANCE"
    else:
        decision = "DEFER"

    return decision, warnings


def prepare(row):
    rubric_path = (
        RUBRIC_DIR /
        f"{row['competency_code']}_rubric_v1.json"
    )

    rubric = json.loads(
        rubric_path.read_text(encoding="utf-8")
    )

    if rubric["rubric_id"] != row["rubric_id"]:
        raise ValueError("Rubric mismatch")

    if len(rubric["criteria"]) != 3:
        raise ValueError("Expected three criteria")

    payload = {
        "role": rubric["role_name"],
        "competency": rubric["competency_name"],
        "interview_question": row["question"],
        "candidate_answer": row["answer"],
        "criteria": [
            {
                "id": c["id"],
                "name": c["name"],
                "definition": c["definition"]
            }
            for c in rubric["criteria"]
        ]
    }

    configuration = {
        "model": MODEL,
        "instructions": INSTRUCTIONS,
        "schema": SCHEMA,
        "payload": payload,
        "decision_policy": "ANY_NEGATIVE_ALL_POSITIVE_V1"
    }

    run_hash = digest(
        json.dumps(
            configuration,
            sort_keys=True,
            ensure_ascii=False
        )
    )

    return rubric, payload, run_hash


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--run",
        action="store_true",
        help="Make API requests. Default is dry-run."
    )

    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Select one response per occupational role."
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None
    )

    args = parser.parse_args()

    rows = read_csv(INPUT)

    if len(rows) != 108:
        raise ValueError("Expected 108 development responses")

    ids = [r["response_id"] for r in rows]

    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate response IDs")

    if args.smoke:
        selected = []
        roles_seen = set()

        for row in rows:
            if row["role_code"] not in roles_seen:
                selected.append(row)
                roles_seen.add(row["role_code"])

        if len(selected) != 3:
            raise ValueError("Expected three roles")

        rows = selected

    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("Limit must be positive")
        rows = rows[:args.limit]

    completed = load_jsonl(OUTPUT)
    configurations = {}

    for row in rows:
        rubric, payload, run_hash = prepare(row)
        configurations[row["response_id"]] = (
            rubric, payload, run_hash
        )

        if row["response_id"] in completed:
            if completed[row["response_id"]]["run_sha256"] != run_hash:
                raise ValueError(
                    f"Saved configuration mismatch: {row['response_id']}"
                )

    print("\nESDSA — EVIDENCE-AWARE BENCHMARK")
    print("=" * 62)
    print("Mode:", "API RUN" if args.run else "DRY RUN")
    print("Model:", MODEL)
    print("Selected responses:", len(rows))
    print("Already saved:", sum(
        r["response_id"] in completed for r in rows
    ))
    print("Reference labels: NOT LOADED")
    print("Experimental conditions: NOT LOADED")

    if not args.run:
        print("\nSelected IDs:")
        for row in rows:
            print(
                row["response_id"],
                "|", row["competency_code"]
            )
        print("\nNo API calls made.")
        return

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing")

    client = OpenAI(timeout=120.0, max_retries=0)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    for row in rows:
        response_id = row["response_id"]

        if response_id in completed:
            print("SKIP:", response_id)
            continue

        rubric, payload, run_hash = configurations[response_id]

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
                        "name": "esdsa_competency_evidence",
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

            if not response.output_text:
                raise ValueError("Empty model output")

            parsed = json.loads(response.output_text)

            decision, warnings = evaluate_output(
                parsed,
                rubric,
                row["answer"]
            )

            record = {
                "response_id": response_id,
                "experiment": "BENCHMARK_EVIDENCE_AWARE_V1",
                "requested_model": MODEL,
                "returned_model": response.model,
                "api_response_id": response.id,
                "timestamp_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "run_sha256": run_hash,
                "answer_sha256": digest(row["answer"]),
                "rubric_id": rubric["rubric_id"],
                "parsed_output": parsed,
                "raw_output": response.output_text,
                "decision": decision,
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

            completed[response_id] = record

            print(
                "Evidence:",
                {
                    item["criterion_id"]: item["evidence_status"]
                    for item in parsed["criteria"]
                }
            )
            print("Decision:", decision)
            print("Warnings:", len(warnings))

        except Exception as exc:
            print(
                "Stopped:",
                type(exc).__name__,
                str(exc)
            )
            raise SystemExit(1)

    print("\nCompleted selected evaluations.")
    print("Results:", OUTPUT)
    print("Original dataset unchanged.")


if __name__ == "__main__":
    main()
