

"""ESDSA scoring-only baseline on the 108 development responses.

Uses numeric competency scores, not evidence-status labels.
Resumable; validates inputs; makes OpenAI API calls.
"""

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
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

MODEL = "gpt-5.4-mini"

DATA = Path("data/benchmark/development_responses_v1.csv")
REFERENCE = Path(
    "data/benchmark/researcher_annotations_v1/"
    "development_reference_provisional_v1.csv"
)
MAPPING = Path(
    "data/benchmark/content_review_v1/"
    "private_review_mapping.json"
)

OUTPUT = Path("results/scoring_baseline_108_v1.jsonl")
ADVANCE_THRESHOLD = 3.0
REJECT_THRESHOLD = 1.5

SYSTEM_PROMPT = """
You are assessing a hypothetical job interview response.

Evaluate the candidate against exactly three supplied
competency criteria.

Use a four-point scale for each criterion:

1 = Does not demonstrate the competency, or describes
    a materially deficient approach.
2 = Limited or partial demonstration.
3 = Adequate demonstration.
4 = Strong and specific demonstration.

Use only the interview question, candidate answer and
supplied criteria. Do not invent candidate experience.

Evaluate each criterion separately. Do not require
unrequested activities or qualifications.

Return a valid JSON object. Your response must contain only JSON,
with no Markdown or additional text, using this structure:

{
  "criteria": [
    {
      "criterion_id": "EXACT_ID",
      "score": 1,
      "reason": "Concise justification"
    }
  ]
}

Return exactly three criterion records in the
same order as supplied.

Do not assign an overall recommendation.
Do not use evidence-sufficiency status categories.
"""


def load_csv(path):
    if not path.is_file():
        raise SystemExit(f"Missing file: {path}")

    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def digest(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def criterion_id(definition):
    if ":" not in definition:
        raise ValueError(
            f"Malformed criterion definition: {definition}"
        )

    return definition.split(":", 1)[0].strip()


def determine_decision(scores):
    mean = sum(scores) / len(scores)

    if mean >= ADVANCE_THRESHOLD:
        return "ADVANCE"

    if mean <= REJECT_THRESHOLD:
        return "DO_NOT_ADVANCE"

    return "DEFER"


def parse_response(raw, criteria):
    result = json.loads(raw)

    items = result.get("criteria")

    if not isinstance(items, list) or len(items) != 3:
        raise ValueError("Expected exactly three scored criteria.")

    expected_ids = [
        criterion_id(c)
        for c in criteria
    ]

    for index, (item, expected) in enumerate(
        zip(items, expected_ids), start=1
    ):
        if not isinstance(item, dict):
            raise ValueError(
                f"Criterion {index} is not an object."
            )

        if item.get("criterion_id") != expected:
            raise ValueError(
                f"Criterion mismatch at position {index}: "
                f"expected {expected}, got "
                f"{item.get('criterion_id')}"
            )

        score = item.get("score")

        if (
            type(score) is not int
            or score not in (1, 2, 3, 4)
        ):
            raise ValueError(
                f"Invalid score for {expected}: {score}"
            )

        if not isinstance(item.get("reason"), str):
            raise ValueError(
                f"Missing reason for {expected}"
            )

    return result


if not os.environ.get("OPENAI_API_KEY"):
    raise SystemExit(
        "OPENAI_API_KEY is not set in this terminal."
    )

responses = load_csv(DATA)
references = load_csv(REFERENCE)

mapping = json.loads(
    MAPPING.read_text(encoding="utf-8")
)["groups"]

if len(responses) != 108 or len(references) != 108:
    raise SystemExit("Expected exactly 108 input records.")

if len({
    r["response_id"] for r in responses
}) != 108:
    raise SystemExit("Duplicate response IDs in input data.")

criteria_by_id = {}

for row in references:
    response_id = mapping[
        row["review_group"]
    ]["responses"][
        row["response_label"]
    ]["response_id"]

    criteria_by_id[response_id] = [
        row[f"criterion_{i}"]
        for i in range(1, 4)
    ]

input_ids = {
    r["response_id"]
    for r in responses
}

if set(criteria_by_id) != input_ids:
    raise SystemExit("Reference/response mapping mismatch.")


OUTPUT.parent.mkdir(parents=True, exist_ok=True)

existing = {}

if OUTPUT.exists():
    with OUTPUT.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)
            rid = record["response_id"]

            if rid in existing:
                raise SystemExit(
                    f"Duplicate saved response: {rid}"
                )

            existing[rid] = record

    if not set(existing).issubset(input_ids):
        raise SystemExit(
            "Existing results contain unknown response IDs."
        )

    for row in responses:
        rid = row["response_id"]

        if rid in existing:
            if existing[rid].get("answer_sha256") != digest(
                row["answer"]
            ):
                raise SystemExit(
                    f"Input changed since prior evaluation: {rid}"
                )

            if existing[rid].get("requested_model") != MODEL:
                raise SystemExit(
                    f"Model mismatch in saved result: {rid}"
                )


pending = [
    row for row in responses
    if row["response_id"] not in existing
]

print("ESDSA — SCORING-ONLY BASELINE")
print("=" * 60)
print("Model:", MODEL)
print("Responses:", len(responses))
print("Already completed:", len(existing))
print("Remaining API evaluations:", len(pending))
print("Scoring scale: 1–4 per criterion")
print("Advance threshold: mean >= 3.0")
print("Reject threshold: mean <= 1.5")
print("Otherwise: DEFER")
print("Output:", OUTPUT)
print()

if not pending:
    print("All 108 evaluations already completed.")
    raise SystemExit(0)


client = OpenAI(timeout=90.0, max_retries=2)

for index, row in enumerate(pending, start=1):
    rid = row["response_id"]
    criteria = criteria_by_id[rid]

    content = {
        "role": row["role_code"],
        "interview_question": row["question"],
        "candidate_answer": row["answer"],
        "criteria": [
            {
                "criterion_id": criterion_id(c),
                "description": c.split(":", 1)[1].strip()
            }
            for c in criteria
        ],
    }

    user_prompt = (
        "Evaluate the following interview response and return JSON only.\n\n"
        + json.dumps(
            content,
            ensure_ascii=False,
            indent=2
        )
    )

    run_hash = digest(
        MODEL
        + SYSTEM_PROMPT
        + user_prompt
        + str(ADVANCE_THRESHOLD)
        + str(REJECT_THRESHOLD)
    )

    try:
        response = client.responses.create(
            model=MODEL,
            instructions=SYSTEM_PROMPT,
            input=user_prompt,
            text={
                "format": {
                    "type": "json_object"
                }
            },
            max_output_tokens=1200,
            store=False,
        )

        raw = response.output_text

        if not raw or not raw.strip():
            raise ValueError(
                "Model returned no parseable text."
            )

        parsed = parse_response(raw, criteria)

        scores = [
            item["score"]
            for item in parsed["criteria"]
        ]

        mean_score = sum(scores) / 3
        decision = determine_decision(scores)

        usage = response.usage

        record = {
            "response_id": rid,
            "experiment": "SCORING_BASELINE_108_V1",
            "requested_model": MODEL,
            "returned_model": response.model,
            "api_response_id": response.id,
            "timestamp_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "run_sha256": run_hash,
            "answer_sha256": digest(row["answer"]),
            "rubric_id": row["rubric_id"],
            "parsed_output": parsed,
            "raw_output": raw,
            "scores": scores,
            "mean_score": mean_score,
            "decision": decision,
            "input_tokens": (
                usage.input_tokens
                if usage else None
            ),
            "output_tokens": (
                usage.output_tokens
                if usage else None
            ),
            "scoring_rule": {
                "advance_mean_at_least": ADVANCE_THRESHOLD,
                "reject_mean_at_most": REJECT_THRESHOLD,
                "other": "DEFER",
            },
        }

        # Append only after full validation.
        with OUTPUT.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(record, ensure_ascii=False)
                + "\n"
            )
            f.flush()

        print(
            f"[{len(existing) + index}/108] "
            f"{rid} | {scores} | "
            f"{mean_score:.2f} | {decision}",
            flush=True,
        )

    except Exception as exc:
        print(
            f"\nStopped at {rid}: {type(exc).__name__}: {exc}"
        )
        print(
            "Completed records are saved. "
            "Rerun this script to resume."
        )
        raise SystemExit(1) from exc


    time.sleep(0.15)


with OUTPUT.open(encoding="utf-8") as f:
    completed = [
        json.loads(line)
        for line in f
        if line.strip()
    ]

counts = Counter(
    row["decision"] for row in completed
)

input_tokens = sum(
    row.get("input_tokens") or 0
    for row in completed
)

output_tokens = sum(
    row.get("output_tokens") or 0
    for row in completed
)

print("\n" + "=" * 60)
print("SCORING BASELINE COMPLETE")
print("Evaluations:", len(completed))
print("Decisions:", dict(counts))
print("Input tokens:", input_tokens)
print("Output tokens:", output_tokens)
print("Results:", OUTPUT)
print("Original source data unchanged.")
