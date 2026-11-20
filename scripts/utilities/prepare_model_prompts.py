
import csv
import json
from pathlib import Path

root = Path("data")

inputs_path = root / "model_inputs/evaluation_pilot_v1.csv"
rubric_path = root / "rubrics/SW-DEFECT-V1.json"
output_path = root / "model_inputs/evaluation_prompts_v1.jsonl"

if output_path.exists():
    raise SystemExit(f"Output already exists: {output_path}")

with inputs_path.open(newline="", encoding="utf-8") as f:
    responses = list(csv.DictReader(f))

rubric = json.loads(rubric_path.read_text(encoding="utf-8"))

assert len(responses) == 12
assert len({r["response_id"] for r in responses}) == 12

criteria = rubric["criteria"]

instructions = """
You are evaluating one response to a structured software
development interview question.

Assess only the competency evidence contained in the answer.

Do not infer qualifications, experience, personal characteristics,
or abilities that are not demonstrated in the response.

Evaluate each rubric criterion independently.

Use exactly one evidence status per criterion:
- POSITIVE_EVIDENCE: The response demonstrates the criterion.
- NEGATIVE_EVIDENCE: The response explicitly demonstrates a
  materially deficient practice against the criterion.
- INSUFFICIENT_EVIDENCE: The response does not provide enough
  information to determine whether the criterion is satisfied.

Absence of positive evidence is not negative evidence.

Apply these provisional pilot decision rules:
- ADVANCE: All four criteria have positive evidence.
- DO_NOT_ADVANCE: Explicit material negative evidence supports
  a negative recommendation under the supplied rubric.
- DEFER: Neither recommendation is adequately supported.

Return only a JSON object with:
- criteria: list containing criterion_id, evidence_status,
  supporting_excerpt, and explanation
- recommendation: ADVANCE, DO_NOT_ADVANCE, or DEFER
- recommendation_reason: concise explanation

Supporting excerpts must be copied from the candidate answer.
Use an empty string if no supporting excerpt exists.

Do not use external information or evaluate the candidate's
overall employment suitability.
""".strip()

records = []

for row in responses:
    if row["rubric_id"] != rubric["rubric_id"]:
        raise ValueError("Rubric mismatch")

    payload = {
        "question": row["question"],
        "candidate_answer": row["answer"],
        "competency": rubric["competency"],
        "criteria": criteria,
        "decision_rules": rubric["decision_rules"]
    }

    records.append({
        "response_id": row["response_id"],
        "instructions": instructions,
        "input": payload
    })

output_path.parent.mkdir(parents=True, exist_ok=True)

with output_path.open("w", encoding="utf-8") as f:
    for record in records:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

forbidden_keys = {
    "reference_decision",
    "expected_decision",
    "evidence_condition",
    "case_type",
    "validation_status",
    "original_response_id"
}

def collect_keys(value):
    if isinstance(value, dict):
        result = set(value)
        for item in value.values():
            result |= collect_keys(item)
        return result
    if isinstance(value, list):
        result = set()
        for item in value:
            result |= collect_keys(item)
        return result
    return set()

for record in records:
    leaked = collect_keys(record) & forbidden_keys
    if leaked:
        raise ValueError(f"Potential metadata leakage: {leaked}")

print(f"Created: {output_path}")
print(f"Evaluation prompts: {len(records)}")
print(f"Rubric criteria: {len(criteria)}")
print("Reference metadata check: PASS")
print("No model evaluations performed.")
