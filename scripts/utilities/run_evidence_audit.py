
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
BASELINE = Path("results/scoring_baseline_v1.jsonl")
OUTPUT = Path("results/evidence_audit_v1.jsonl")

STATUSES = [
    "POSITIVE_EVIDENCE",
    "NEGATIVE_EVIDENCE",
    "INSUFFICIENT_EVIDENCE"
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
        }
    },
    "required": ["criteria"],
    "additionalProperties": False
}

INSTRUCTIONS = """
You are conducting an independent evidence review of
a structured interview response.

Your task is to determine what evidence the response
provides for each competency criterion.

You are NOT making a hiring recommendation.

Assess only the candidate's response against the
supplied competency criteria.

For each criterion, select exactly one status:

POSITIVE_EVIDENCE:
The response substantively demonstrates the criterion.

NEGATIVE_EVIDENCE:
The response explicitly demonstrates a materially
deficient practice against the criterion.

INSUFFICIENT_EVIDENCE:
The response does not provide sufficient information
to establish either positive or negative evidence.

Important rules:

1. Missing evidence is not negative evidence.
2. Do not infer incompetence from brevity.
3. Do not invent qualifications or professional experience.
4. Do not assume a verification method was performed
   unless the response demonstrates it.
5. Evaluate the substance of the answer rather than
   linguistic polish.
6. Copy supporting excerpts verbatim from the answer.
7. Use an empty excerpt when no direct supporting
   passage exists.
8. Do not make an overall recommendation.

Return only the required JSON object.
""".strip()


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def load_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_jsonl(path):
    if not path.exists():
        return []

    with path.open(encoding="utf-8") as f:
        return [
            json.loads(line)
            for line in f
            if line.strip()
        ]


def validate_assessment(result, criteria, answer):
    items = result["criteria"]

    expected = {c["id"] for c in criteria}
    actual = [x["criterion_id"] for x in items]

    if len(actual) != len(expected):
        raise ValueError("Incorrect criterion count")

    if set(actual) != expected:
        raise ValueError("Criterion ID mismatch")

    warnings = []

    for item in items:
        excerpt = item["supporting_excerpt"]

        if excerpt and excerpt not in answer:
            warnings.append({
                "criterion_id": item["criterion_id"],
                "issue": "EXCERPT_NOT_VERBATIM",
                "excerpt": excerpt
            })

    return warnings


def determine_support(assessment):
    statuses = [
        item["evidence_status"]
        for item in assessment["criteria"]
    ]

    if all(s == "POSITIVE_EVIDENCE" for s in statuses):
        return "ADVANCE"

    if any(s == "NEGATIVE_EVIDENCE" for s in statuses):
        return "DO_NOT_ADVANCE"

    return "DEFER"


def audit_recommendation(original, supported):
    if original == supported:
        return "SUPPORTED", original

    return "UNSUPPORTED", "DEFER"


def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing")

    responses = load_csv(INPUT)
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    baseline = load_jsonl(BASELINE)
    previous = load_jsonl(OUTPUT)

    assert len(responses) == 12
    assert len(baseline) == 12

    response_ids = [r["response_id"] for r in responses]
    baseline_ids = [r["response_id"] for r in baseline]

    if len(set(response_ids)) != 12:
        raise ValueError("Duplicate input IDs")

    if len(set(baseline_ids)) != 12:
        raise ValueError("Duplicate baseline IDs")

    if set(response_ids) != set(baseline_ids):
        raise ValueError("Input/baseline mismatch")

    baseline_map = {
        r["response_id"]: r for r in baseline
    }

    completed = {}

    for record in previous:
        response_id = record["response_id"]

        if response_id in completed:
            raise ValueError("Duplicate audit record")

        completed[response_id] = record

    if not set(completed).issubset(set(response_ids)):
        raise ValueError("Unknown saved audit IDs")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    client = OpenAI(timeout=90.0, max_retries=0)

    print("ESDSA — EVIDENCE SUFFICIENCY AUDIT")
    print("Model:", MODEL)
    print("Responses:", len(responses))
    print("Reference labels: NOT LOADED")

    for row in responses:
        response_id = row["response_id"]
        answer = row["answer"]

        if row["rubric_id"] != rubric["rubric_id"]:
            raise ValueError("Rubric mismatch")


        payload = {
            "question": row["question"],
            "candidate_answer": answer,
            "competency": rubric["competency"],
            "criteria": rubric["criteria"]
        }

        run_hash = fingerprint({
            "model": MODEL,
            "instructions": INSTRUCTIONS,
            "payload": payload,
            "schema": SCHEMA
        })

        original = baseline_map[response_id][
            "parsed_output"
        ]["recommendation"]

        if response_id in completed:
            saved = completed[response_id]

            if saved["run_sha256"] != run_hash:
                raise ValueError(
                    f"Configuration changed: {response_id}"
                )

            if saved["original_recommendation"] != original:
                raise ValueError(
                    f"Baseline changed: {response_id}"
                )

            print("SKIP:", response_id)
            continue

        print("\nAuditing:", response_id)

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
                raise ValueError("Empty model output")

            assessment = json.loads(raw)

            warnings = validate_assessment(
                assessment,
                rubric["criteria"],
                answer
            )

            supported = determine_support(assessment)

            verdict, final_decision = audit_recommendation(
                original, supported
            )

            record = {
                "response_id": response_id,
                "requested_model": MODEL,
                "returned_model": response.model,
                "timestamp_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "run_sha256": run_hash,
                "original_recommendation": original,
                "evidence_supported_decision": supported,
                "audit_verdict": verdict,
                "audited_recommendation": final_decision,
                "raw_output": raw,
                "parsed_output": assessment,
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
                f.write(json.dumps(
                    record, ensure_ascii=False
                ) + "\n")

            print("Original:", original)
            print("Evidence supports:", supported)
            print("Audit verdict:", verdict)
            print("Final recommendation:", final_decision)
            print("Excerpt warnings:", len(warnings))

        except Exception as exc:
            print(
                "Audit failed:",
                type(exc).__name__,
                str(exc)
            )
            raise SystemExit(1)

    print("\nEvidence audit run complete.")
    print("Results saved:", OUTPUT)
    print("Reference labels were not accessed.")


if __name__ == "__main__":
    main()
