
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
from run_evaluator import SCHEMA, validate_result

MODEL = "gpt-5.4-mini"

INPUT = Path("data/model_inputs/controlled_pairs_v1.csv")
PILOT_PROMPTS = Path(
    "data/model_inputs/evaluation_prompts_v1.jsonl"
)
RUBRIC = Path("data/rubrics/SW-DEFECT-V1.json")
OUTPUT = Path("results/controlled_pairs_gpt-5.4-mini.jsonl")


def load_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


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

    rows = load_csv(INPUT)

    with PILOT_PROMPTS.open(encoding="utf-8") as f:
        pilot = json.loads(next(f))

    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))

    assert len(rows) == 6
    assert len({r["response_id"] for r in rows}) == 6
    assert all(
        r["rubric_id"] == rubric["rubric_id"]
        for r in rows
    )

    instructions = pilot["instructions"]
    question = pilot["input"]["question"]

    assert all(r["question"] == question for r in rows)

    unique_answers = {}

    for row in rows:
        unique_answers.setdefault(
            row["answer"], []
        ).append(row["response_id"])

    assert len(unique_answers) == 4, (
        "Expected four unique answer texts"
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    completed = {}

    if OUTPUT.exists():
        with OUTPUT.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    key = record["answer_sha256"]

                    if key in completed:
                        raise ValueError(
                            "Duplicate saved answer fingerprint"
                        )

                    completed[key] = record

    client = OpenAI(timeout=90.0, max_retries=0)

    print("ESDSA — CONTROLLED PAIR EVALUATION")
    print("Unique responses:", len(unique_answers))
    print("Model:", MODEL)

    for answer, response_ids in unique_answers.items():
        answer_hash = hashlib.sha256(
            answer.encode("utf-8")
        ).hexdigest()

        payload = {
            "question": question,
            "candidate_answer": answer,
            "competency": rubric["competency"],
            "criteria": rubric["criteria"],
            "decision_rules": rubric["decision_rules"]
        }

        prompt_hash = fingerprint({
            "instructions": instructions,
            "input": payload,
            "schema": SCHEMA
        })

        if answer_hash in completed:
            saved = completed[answer_hash]

            if saved["prompt_sha256"] != prompt_hash:
                raise ValueError("Prompt changed since saved run")

            if saved["requested_model"] != MODEL:
                raise ValueError("Model changed since saved run")

            if set(saved["response_ids"]) != set(response_ids):
                raise ValueError("Response mapping changed")

            print("SKIP:", response_ids)
            continue

        print("\nEvaluating:", response_ids)

        try:
            response = client.responses.create(
                model=MODEL,
                instructions=instructions,
                input=json.dumps(
                    payload,
                    ensure_ascii=False
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
                    f"Unexpected status: {response.status}"
                )

            raw = response.output_text

            if not raw:
                raise ValueError("Empty model output")

            parsed = json.loads(raw)

            expected_ids = [
                c["id"] for c in rubric["criteria"]
            ]

            warnings = validate_result(
                parsed,
                expected_ids,
                answer
            )

            record = {
                "response_ids": response_ids,
                "answer_sha256": answer_hash,
                "prompt_sha256": prompt_hash,
                "requested_model": MODEL,
                "returned_model": response.model,
                "api_response_id": response.id,
                "timestamp_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "raw_output": raw,
                "parsed_output": parsed,
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

            print(
                "Recommendation:",
                parsed["recommendation"]
            )
            print(
                "Excerpt warnings:",
                len(warnings)
            )
            print("Saved:", OUTPUT)

        except Exception as exc:
            print(
                "Evaluation failed:",
                type(exc).__name__,
                str(exc)
            )
            raise SystemExit(1)

    print("\nControlled-pair evaluation complete.")
    print("Reference labels were not sent to the model.")


if __name__ == "__main__":
    main()
