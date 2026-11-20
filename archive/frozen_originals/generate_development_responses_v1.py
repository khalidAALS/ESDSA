
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

MODEL = "gpt-5.4-mini"

ROOT = Path("data/benchmark")
SCENARIOS = ROOT / "development_scenarios_v1.csv"
RUBRIC_DIR = ROOT / "rubrics_v1"

RAW_OUTPUT = Path(
    "results/development_generation_v1.jsonl"
)
MODEL_OUTPUT = ROOT / "development_responses_v1.csv"
REFERENCE_OUTPUT = ROOT / "development_response_design_v1.csv"

CONDITIONS = (
    "SUFFICIENT",
    "INSUFFICIENT",
    "NEGATIVE"
)

VARIANTS = (
    "CANONICAL",
    "CONVERSATIONAL",
    "CONCISE"
)

EXPECTED = {
    (condition, variant)
    for condition in CONDITIONS
    for variant in VARIANTS
}

INSTRUCTIONS = """
Generate synthetic candidate answers for a research benchmark
on evidence sufficiency in automated job interviews.

Create exactly nine answers to the supplied interview question.

For each evidence condition, create three linguistic variants:
CANONICAL, CONVERSATIONAL and CONCISE.

Evidence conditions:
SUFFICIENT: The answer demonstrates all three competency
indicators with contextually defensible evidence.

INSUFFICIENT: The answer genuinely leaves at least one
indicator unresolved, without explicitly demonstrating
deficient practice. Other indicators may be demonstrated.

NEGATIVE: The answer demonstrates a materially deficient
approach to at least one indicator. Make the weakness
plausible and context-specific, not a cartoonishly obvious
statement of incompetence.

Linguistic variants must preserve the same substantive
competency evidence within each condition.

CANONICAL: Clear, naturally structured spoken answer.
CONVERSATIONAL: Natural informal interview language.
CONCISE: Shorter, direct answer preserving the evidence.

Important:
- The three variants must not introduce different decisions,
  technical claims, safeguards or substantive actions.
- Do not treat brevity or informal language as incompetence.
- Do not use demographic or protected-attribute cues.
- Avoid identical formulaic responses across scenarios.
- Do not quote the rubric verbatim.
- Avoid unsupported certainty and irrelevant details.
- The answers should sound like plausible interview speech.
- Candidate answers must not mention experimental labels.
- Do not include scores or hiring recommendations.
"""

ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "condition": {
            "type": "string",
            "enum": list(CONDITIONS)
        },
        "variant": {
            "type": "string",
            "enum": list(VARIANTS)
        },
        "answer": {
            "type": "string"
        }
    },
    "required": [
        "condition",
        "variant",
        "answer"
    ],
    "additionalProperties": False
}

SCHEMA = {
    "type": "object",
    "properties": {
        "responses": {
            "type": "array",
            "items": ITEM_SCHEMA
        }
    },
    "required": ["responses"],
    "additionalProperties": False
}


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_hash(value):
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def read_csv(path):
    with path.open(
        newline="", encoding="utf-8"
    ) as f:
        return list(csv.DictReader(f))


def read_jsonl(path):
    if not path.exists():
        return []

    with path.open(encoding="utf-8") as f:
        return [
            json.loads(line)
            for line in f
            if line.strip()
        ]


def validate_generated(items):
    if len(items) != 9:
        raise ValueError(
            f"Expected 9 responses, received {len(items)}"
        )

    seen = set()
    answers = set()

    for item in items:
        key = (item["condition"], item["variant"])

        if key in seen:
            raise ValueError(f"Duplicate condition: {key}")

        seen.add(key)

        answer = item["answer"].strip()

        if len(answer) < 20:
            raise ValueError(f"Unusually short answer: {key}")

        if answer in answers:
            raise ValueError("Duplicate answer text")

        answers.add(answer)

    if seen != EXPECTED:
        raise ValueError(
            f"Missing or unexpected combinations: {seen ^ EXPECTED}"
        )


def write_csv(path, records):
    with path.open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=list(records[0])
        )
        writer.writeheader()
        writer.writerows(records)


def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing")

    scenarios = read_csv(SCENARIOS)

    if len(scenarios) != 12:
        raise ValueError("Expected 12 development scenarios")

    family_ids = [r["family_id"] for r in scenarios]

    if len(set(family_ids)) != 12:
        raise ValueError("Duplicate scenario family")

    if any(r["partition"] != "DEVELOPMENT" for r in scenarios):
        raise ValueError("Non-development scenario detected")

    if MODEL_OUTPUT.exists() or REFERENCE_OUTPUT.exists():
        raise SystemExit(
            "Final outputs already exist. "
            "No files overwritten."
        )

    existing = read_jsonl(RAW_OUTPUT)
    completed = {}

    for record in existing:
        family_id = record["family_id"]

        if family_id in completed:
            raise ValueError(
                f"Duplicate saved family: {family_id}"
            )

        completed[family_id] = record

    if not set(completed).issubset(set(family_ids)):
        raise ValueError("Unknown saved family")

    client = OpenAI(
        timeout=120.0,
        max_retries=0
    )

    RAW_OUTPUT.parent.mkdir(
        parents=True, exist_ok=True
    )

    print("\nESDSA — DEVELOPMENT RESPONSE GENERATION")
    print("=" * 65)
    print("Model:", MODEL)
    print("Scenario families:", len(scenarios))
    print("Responses per family:", 9)
    print("Target responses:", 108)
    print("Previously completed:", len(completed))
    print("Partition: DEVELOPMENT ONLY")

    for scenario in scenarios:
        family_id = scenario["family_id"]

        rubric_path = (
            RUBRIC_DIR / scenario["rubric_file"]
        )

        rubric = json.loads(
            rubric_path.read_text(encoding="utf-8")
        )

        if rubric["rubric_id"] != scenario["rubric_id"]:
            raise ValueError(
                f"Rubric mismatch: {family_id}"
            )

        payload = {
            "family_id": family_id,
            "role": scenario["role_name"],
            "competency": scenario["competency_name"],
            "question": scenario["interview_question"],
            "rubric": {
                "criteria": rubric["criteria"],
                "evidence_statuses": rubric[
                    "evidence_statuses"
                ]
            }
        }

        run_hash = text_hash(
            json.dumps(
                {
                    "model": MODEL,
                    "instructions": INSTRUCTIONS,
                    "payload": payload,
                    "schema": SCHEMA
                },
                sort_keys=True,
                ensure_ascii=False
            )
        )

        if family_id in completed:
            saved = completed[family_id]

            if saved["run_sha256"] != run_hash:
                raise ValueError(
                    f"Saved configuration mismatch: {family_id}"
                )

            if saved["requested_model"] != MODEL:
                raise ValueError(
                    f"Saved model mismatch: {family_id}"
                )

            validate_generated(saved["responses"])
            print("SKIP:", family_id)
            continue

        print("\nGenerating:", family_id)

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
                        "name": "esdsa_development_responses",
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
                raise ValueError("Empty API output")

            parsed = json.loads(raw)
            items = parsed["responses"]

            validate_generated(items)

            record = {
                "family_id": family_id,
                "requested_model": MODEL,
                "returned_model": response.model,
                "api_response_id": response.id,
                "timestamp_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "run_sha256": run_hash,
                "scenario_file_sha256": file_hash(
                    SCENARIOS
                ),
                "rubric_sha256": file_hash(
                    rubric_path
                ),
                "responses": items,
                "raw_output": raw,
                "input_tokens": (
                    response.usage.input_tokens
                    if response.usage else None
                ),
                "output_tokens": (
                    response.usage.output_tokens
                    if response.usage else None
                )
            }

            with RAW_OUTPUT.open(
                "a", encoding="utf-8"
            ) as f:
                f.write(
                    json.dumps(
                        record, ensure_ascii=False
                    ) + "\n"
                )

            completed[family_id] = record
            print("Saved 9 responses")

        except Exception as exc:
            print(
                "Generation stopped:",
                type(exc).__name__,
                str(exc)
            )
            print(
                "Completed families remain saved. "
                "Rerun the same command to resume."
            )
            raise SystemExit(1)

    model_rows = []
    design_rows = []

    for scenario in scenarios:
        family_id = scenario["family_id"]
        record = completed[family_id]

        item_map = {
            (item["condition"], item["variant"]): item
            for item in record["responses"]
        }

        for condition_index, condition in enumerate(
            CONDITIONS, start=1
        ):
            for variant_index, variant in enumerate(
                VARIANTS, start=1
            ):
                item = item_map[(condition, variant)]

                response_id = (
                    f"{family_id}-"
                    f"E{condition_index}L{variant_index}"
                )

                answer = item["answer"].strip()

                model_rows.append({
                    "response_id": response_id,
                    "family_id": family_id,
                    "role_code": scenario["role_code"],
                    "competency_code": scenario[
                        "competency_code"
                    ],
                    "question": scenario[
                        "interview_question"
                    ],
                    "answer": answer,
                    "rubric_id": scenario["rubric_id"]
                })

                design_rows.append({
                    "response_id": response_id,
                    "family_id": family_id,
                    "intended_condition": condition,
                    "linguistic_variant": variant,
                    "response_sha256": text_hash(answer),
                    "evidence_validation": "PENDING",
                    "semantic_validation": "PENDING",
                    "reference_decision": "UNDETERMINED",
                    "partition": "DEVELOPMENT",
                    "origin": "SYNTHETIC_MODEL_GENERATED"
                })

    if len(model_rows) != 108:
        raise ValueError("Expected 108 responses")

    if len({
        r["response_id"] for r in model_rows
    }) != 108:
        raise ValueError("Duplicate response IDs")

    write_csv(MODEL_OUTPUT, model_rows)
    write_csv(REFERENCE_OUTPUT, design_rows)

    print("\n" + "=" * 65)
    print("GENERATION COMPLETE")
    print("Families:", len(completed))
    print("Responses:", len(model_rows))
    print("Model-facing data:", MODEL_OUTPUT)
    print("Design metadata:", REFERENCE_OUTPUT)
    print("Raw API records:", RAW_OUTPUT)
    print("Model data SHA256:", file_hash(MODEL_OUTPUT))
    print("Design data SHA256:", file_hash(REFERENCE_OUTPUT))
    print("Evidence validation: PENDING")
    print("Semantic validation: PENDING")
    print("Held-out test set: UNTOUCHED")


if __name__ == "__main__":
    main()
