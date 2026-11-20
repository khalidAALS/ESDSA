
# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import os
import sys

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]

INPUT_DIR = ROOT / "results/validation_annotation_templates_v1"
EVIDENCE_CSV = INPUT_DIR / "validation_evidence_annotations_v1.csv"
SEMANTIC_CSV = INPUT_DIR / "validation_semantic_annotations_v1.csv"
MANIFEST = INPUT_DIR / "validation_annotation_template_manifest_v1.json"

OUTPUT_DIR = ROOT / "results/validation_ai_annotations_v1"
EVIDENCE_OUT = OUTPUT_DIR / "evidence"
SEMANTIC_OUT = OUTPUT_DIR / "semantic"
ERROR_OUT = OUTPUT_DIR / "errors"

MODEL = "gpt-5.4-mini"
REVIEWER_ID = "AI_ASSISTED_GPT54_MINI_V1"

ALLOWED_STATUSES = {
    "POSITIVE_EVIDENCE",
    "NEGATIVE_EVIDENCE",
    "INSUFFICIENT_EVIDENCE",
}
ALLOWED_EQUIVALENCE = {"YES", "NO", "UNCERTAIN"}


def fail(message):
    raise SystemExit(f"FAIL: {message}")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    if not path.is_file():
        fail(f"Missing input: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_json(path):
    if not path.is_file():
        fail(f"Missing input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def verify_inputs():
    manifest = load_json(MANIFEST)

    if manifest.get("status") != "TEMPLATES_CREATED":
        fail("Annotation manifest status is not valid")

    expected = manifest.get("output_sha256", {})

    for path in (EVIDENCE_CSV, SEMANTIC_CSV):
        if sha256(path) != expected.get(path.name):
            fail(f"Input SHA256 mismatch: {path.name}")

    evidence = read_csv(EVIDENCE_CSV)
    semantic = read_csv(SEMANTIC_CSV)

    if len(evidence) != 216 or len(semantic) != 72:
        fail("Unexpected annotation template dimensions")

    evidence_ids = [r["blinded_response_id"] for r in evidence]
    semantic_ids = [r["blinded_group_id"] for r in semantic]

    if len(set(evidence_ids)) != 216:
        fail("Duplicate blinded evidence IDs")

    if len(set(semantic_ids)) != 72:
        fail("Duplicate blinded semantic group IDs")

    by_group = {}

    for row in evidence:
        by_group.setdefault(row["blinded_group_id"], []).append(row)

    for group in semantic:
        gid = group["blinded_group_id"]
        members = by_group.get(gid, [])

        expected_ids = {
            group[f"response_{slot}_id"] for slot in "ABC"
        }

        if len(members) != 3:
            fail(f"Incorrect member count for {gid}")

        if {r["blinded_response_id"] for r in members} != expected_ids:
            fail(f"Blinded membership mismatch for {gid}")

        for slot in "ABC":
            rid = group[f"response_{slot}_id"]
            answer = group[f"response_{slot}_text"]

            matching = [
                r for r in members
                if r["blinded_response_id"] == rid
            ]

            if len(matching) != 1 or matching[0]["answer"] != answer:
                fail(f"Response text mismatch for {gid}, slot {slot}")

    return evidence, semantic, by_group


EVIDENCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "criteria": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "criterion_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": sorted(ALLOWED_STATUSES),
                    },
                    "passage": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": [
                    "criterion_id", "status",
                    "passage", "rationale",
                ],
            },
        },
        "annotation_notes": {"type": "string"},
    },
    "required": ["criteria", "annotation_notes"],
}


SEMANTIC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "semantic_equivalence": {
            "type": "string",
            "enum": sorted(ALLOWED_EQUIVALENCE),
        },
        "material_differences": {"type": "string"},
        "equivalence_rationale": {"type": "string"},
    },
    "required": [
        "semantic_equivalence",
        "material_differences",
        "equivalence_rationale",
    ],
}


EVIDENCE_INSTRUCTIONS = """
You are conducting provisional AI-assisted evidence annotation
for an academic research benchmark.

Assess ONE candidate interview answer against THREE supplied
competency criteria.

Use only the scenario, answer, and rubric information provided.

Statuses:
POSITIVE_EVIDENCE: The answer explicitly or clearly demonstrates
the criterion in the scenario context.

NEGATIVE_EVIDENCE: The answer explicitly demonstrates materially
deficient practice concerning that criterion.

INSUFFICIENT_EVIDENCE: The answer establishes neither positive
nor negative evidence for that criterion.

Rules:
- Judge demonstrated meaning, not length or fluency.
- Never infer negative evidence solely from omission.
- A brief answer may demonstrate sufficient evidence.
- An explicitly harmful approach may be negative evidence.
- Conditional proposals count only for what they establish.
- Do not assume hypothetical investigations were completed.
- Do not invent facts, actions, results, or supporting passages.
- For POSITIVE_EVIDENCE or NEGATIVE_EVIDENCE, provide one
  EXACT contiguous substring copied from the candidate answer.
- For INSUFFICIENT_EVIDENCE, set passage to an empty string.
- Explain each judgment with a concise substantive rationale.
- Evaluate each criterion separately.
- Do not infer generation conditions or hiring decisions.
- Do not use any other candidate answers.
- Return only the requested structured JSON.
"""


SEMANTIC_INSTRUCTIONS = """
You are conducting provisional semantic-equivalence annotation
for an academic research benchmark.

Compare three candidate responses to the SAME interview question.

Decide whether A, B and C preserve the same decision-relevant
evidence and substantive meaning under the competency rubric.

YES:
Differences are linguistic, stylistic, or non-material.
All three preserve the same substantive competency evidence.

NO:
At least one response adds, removes, contradicts, or materially
changes evidence or an operational commitment in a way that could
change criterion-level assessment.

UNCERTAIN:
There is a plausible material difference, but the rubric and
context do not allow it to be resolved confidently.

Rules:
- Do not treat shared general topic or tone as proof of equivalence.
- Distinguish paraphrasing from changed operational commitments.
- Shorter responses can be equivalent if evidence is preserved.
- Do not infer absent details.
- Do not infer any response's original generation condition.
- Give specific differences, or state none were found.
- Explain the judgment.
- Do not assign hiring decisions.
- Return only the requested structured JSON.
"""


def call_model(client, instructions, payload, schema, name):
    response = client.responses.create(
        model=MODEL,
        instructions=instructions,
        input=json.dumps(payload, ensure_ascii=False),
        text={
            "format": {
                "type": "json_schema",
                "name": name,
                "strict": True,
                "schema": schema,
            }
        },
        store=False,
    )

    if response.status != "completed":
        fail(f"API response not completed: {response.status}")

    if response.model != "gpt-5.4-mini-2026-03-17":
        fail(f"Unexpected annotator model: {response.model}")

    raw_text = response.output_text

    try:
        result = json.loads(raw_text)
    except (TypeError, json.JSONDecodeError):
        ERROR_OUT.mkdir(parents=True, exist_ok=True)
        error_file = ERROR_OUT / f"{response.id}.json"
        save_json_new(error_file, {
            "response_id": response.id,
            "raw_output_text": raw_text,
            "error": "INVALID_JSON",
        })
        fail("Annotator returned invalid JSON; raw output saved")

    return response, result


def validate_evidence(row, result):
    criteria = result.get("criteria")

    if not isinstance(criteria, list) or len(criteria) != 3:
        fail("Evidence annotation must contain three criteria")

    expected_ids = {
        row[f"criterion_{i}_id"] for i in (1, 2, 3)
    }

    observed = set()

    for item in criteria:
        cid = item.get("criterion_id")
        status = item.get("status")
        passage = item.get("passage")
        rationale = item.get("rationale")

        if cid not in expected_ids or cid in observed:
            fail(f"Invalid or duplicate criterion ID: {cid}")

        observed.add(cid)

        if status not in ALLOWED_STATUSES:
            fail(f"Invalid evidence status: {status}")

        if not isinstance(rationale, str) or not rationale.strip():
            fail(f"Missing evidence rationale: {cid}")

        if not isinstance(passage, str):
            fail(f"Invalid supporting passage: {cid}")

        if status == "INSUFFICIENT_EVIDENCE":
            if passage != "":
                fail(
                    "Insufficient evidence must have empty passage: "
                    f"{cid}"
                )
        else:
            if not passage or passage not in row["answer"]:
                fail(
                    "Supporting passage is not an exact substring "
                    f"of the candidate answer: {cid}"
                )

    if observed != expected_ids:
        fail("Missing rubric criterion assessment")

    if not isinstance(result.get("annotation_notes"), str):
        fail("Invalid annotation notes")


def validate_semantic(result):
    if result.get("semantic_equivalence") not in ALLOWED_EQUIVALENCE:
        fail("Invalid semantic equivalence value")

    if not isinstance(result.get("material_differences"), str):
        fail("Invalid material differences")

    rationale = result.get("equivalence_rationale")

    if not isinstance(rationale, str) or not rationale.strip():
        fail("Missing semantic equivalence rationale")

    if (
        result["semantic_equivalence"] == "NO"
        and not result["material_differences"].strip()
    ):
        fail("NO equivalence requires documented differences")


def evidence_payload(row):
    criteria = []

    for number in (1, 2, 3):
        prefix = f"criterion_{number}"
        criteria.append({
            "criterion_id": row[f"{prefix}_id"],
            "name": row[f"{prefix}_name"],
            "definition": row[f"{prefix}_definition"],
        })

    return {
        "role": row["role_name"],
        "competency": row["competency_name"],
        "scenario_profile": row["scenario_profile"],
        "interview_question": row["interview_question"],
        "candidate_answer": row["answer"],
        "criteria": criteria,
    }


def semantic_payload(row, members):
    criterion_info = [
        {
            "criterion_id": members[0][f"criterion_{i}_id"],
            "name": members[0][f"criterion_{i}_name"],
            "definition": members[0][f"criterion_{i}_definition"],
        }
        for i in (1, 2, 3)
    ]

    return {
        "competency": row["competency_name"],
        "interview_question": row["interview_question"],
        "criteria": criterion_info,
        "responses": {
            slot: row[f"response_{slot}_text"]
            for slot in "ABC"
        },
    }


def record(response, kind, identifier, result):
    return {
        "experiment": "ESDSA_VALIDATION_AI_ANNOTATION_PILOT_V1",
        "partition": "VALIDATION",
        "review_type": kind,
        "blinded_id": identifier,
        "reviewer_id": REVIEWER_ID,
        "requested_model": MODEL,
        "returned_model": response.model,
        "api_response_id": response.id,
        "annotated_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "reference_decision": None,
        "annotation": result,
    }


def main():
    print("ESDSA VALIDATION — BLINDED ANNOTATION PILOT")
    print("=" * 65)
    print("Pilot scope: 1 group, 3 evidence reviews, 1 semantic review")
    print("Maximum new API requests: 4")
    print("Blinding key: NOT ACCESSED")
    print("ESDSA evaluator: NOT RUN")
    print("TEST partition: NOT ACCESSED")
    print()

    evidence, semantic, by_group = verify_inputs()

    group = semantic[0]
    gid = group["blinded_group_id"]
    members = sorted(
        by_group[gid],
        key=lambda row: row["blinded_response_id"],
    )

    print(f"Pilot group: {gid}")
    print(f"Competency: {group['competency_code']}")
    print(f"Family: {group['family_id']}")
    print()

    if not os.environ.get("OPENAI_API_KEY"):
        fail("OPENAI_API_KEY environment variable is not set")

    client = OpenAI(timeout=120, max_retries=0)

    for row in members:
        rid = row["blinded_response_id"]
        output_file = EVIDENCE_OUT / f"{rid}.json"

        if output_file.exists():
            saved = load_json(output_file)
            if (
                saved.get("blinded_id") != rid
                or saved.get("review_type") != "EVIDENCE"
            ):
                fail(f"Existing evidence record mismatch: {rid}")
            validate_evidence(row, saved["annotation"])
            print(f"ALREADY SAVED: evidence {rid}")
            continue

        print(f"Annotating evidence: {rid}")

        response, result = call_model(
            client,
            EVIDENCE_INSTRUCTIONS,
            evidence_payload(row),
            EVIDENCE_SCHEMA,
            "esdsa_evidence_annotation_v1",
        )

        validate_evidence(row, result)
        save_json_new(
            output_file,
            record(response, "EVIDENCE", rid, result),
        )
        print(f"PASS: evidence {rid}")

    semantic_file = SEMANTIC_OUT / f"{gid}.json"

    if semantic_file.exists():
        saved = load_json(semantic_file)
        if (
            saved.get("blinded_id") != gid
            or saved.get("review_type") != "SEMANTIC_EQUIVALENCE"
        ):
            fail("Existing semantic record mismatch")
        validate_semantic(saved["annotation"])
        print(f"ALREADY SAVED: semantic {gid}")
    else:
        print(f"Annotating semantic equivalence: {gid}")

        response, result = call_model(
            client,
            SEMANTIC_INSTRUCTIONS,
            semantic_payload(group, members),
            SEMANTIC_SCHEMA,
            "esdsa_semantic_equivalence_v1",
        )

        validate_semantic(result)
        save_json_new(
            semantic_file,
            record(
                response,
                "SEMANTIC_EQUIVALENCE",
                gid,
                result,
            ),
        )
        print(f"PASS: semantic {gid}")

    print()
    print("=" * 65)
    print("ANNOTATION PILOT: PASSED")
    print("Evidence responses: 3 / 216")
    print("Semantic groups: 1 / 72")
    print(f"Output directory: {OUTPUT_DIR.relative_to(ROOT)}")
    print("Original templates: NOT MODIFIED")
    print("No final reference decisions assigned.")
    print("TEST partition: NOT ACCESSED")


if __name__ == "__main__":
    main()
