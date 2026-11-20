
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
from collections import Counter
import argparse
import json
import os
import sys

from openai import OpenAI

import run_validation_annotation_pilot_v1 as pilot


ROOT = Path(__file__).resolve().parents[2]

OUT_DIR = ROOT / "results/validation_ai_annotations_v2"
EVIDENCE_DIR = OUT_DIR / "evidence"
SEMANTIC_DIR = OUT_DIR / "semantic"
SUMMARY_FILE = OUT_DIR / "annotation_progress_v2.json"

MODEL = pilot.MODEL
REVIEWER = "AI_ASSISTED_GPT54_MINI_V2"

EVIDENCE_INSTRUCTIONS_V2 = """
You are an AI-assisted research annotator assessing evidence
in synthetic job-interview answers.

Your judgments are provisional, not expert reference labels.

Assess the candidate answer independently against the three
supplied competency criteria.

Use ONLY the supplied scenario, interview question, answer,
and criterion definitions.

EVIDENCE STATUSES

POSITIVE_EVIDENCE:
The candidate explicitly or clearly demonstrates the
substantive behaviour required by the criterion.

NEGATIVE_EVIDENCE:
The candidate explicitly proposes or demonstrates behaviour
that materially contradicts the criterion.

INSUFFICIENT_EVIDENCE:
The candidate does not establish either positive or
negative evidence for that specific criterion.

MANDATORY DISTINCTIONS

1. Missing information is not negative evidence.

2. A weak, incomplete, vague, or narrowly focused answer
   is not automatically negative evidence.

3. Do not treat ordinary information gathering as proof
   that collection is authorised, proportionate, or safe.
   The answer must substantively demonstrate those qualities.

4. Do not treat absence of an explicit privacy safeguard
   as evidence of unauthorised or disproportionate collection.

5. Asking a customer to find supporting records is not,
   by itself, inappropriate or disproportionate.

6. A clearly stated unsafe, unjustified, or materially
   deficient action may constitute negative evidence.

7. Evaluate each criterion separately. Evidence relevant
   to one criterion does not automatically satisfy another.

8. An answer can be concise and still establish positive
   evidence. Do not reward verbosity.

9. Conditional plans establish what the candidate proposes,
   not what has already been accomplished.

10. Do not invent unstated actions, outcomes, permissions,
    safeguards, intentions, or scenario facts.

11. Do not infer any original generation condition,
    desired response quality, or final hiring decision.

SUPPORTING PASSAGES

For POSITIVE_EVIDENCE or NEGATIVE_EVIDENCE:
Provide one exact contiguous substring copied verbatim
from the candidate answer that substantively supports
the status. Do not paraphrase or fabricate quotations.

For INSUFFICIENT_EVIDENCE:
Return an empty passage string and explain what remains
unestablished without treating omission as misconduct.

When uncertain whether a deficiency is explicitly
negative, prefer INSUFFICIENT_EVIDENCE unless the answer
clearly demonstrates materially deficient practice.

Return only the required structured JSON.
"""


SEMANTIC_INSTRUCTIONS_V2 = """
You are an AI-assisted research annotator assessing whether
three versions of a synthetic job-interview response
preserve the same decision-relevant evidence.

Your judgment is provisional, not expert adjudication.

Assess the answers under the supplied three competency
criteria, using only the question, answers, and definitions.

Return YES when all three preserve substantially the same
criterion-level evidence and relevant operational commitments.

Return NO when a specific addition, omission, contradiction,
or change could plausibly change a criterion-level evidence
assessment or an important operational commitment.

Return UNCERTAIN when a potentially material difference
cannot be resolved confidently from the provided context.

IMPORTANT RULES

1. A response is not materially different merely because
   it is shorter, longer, more conversational, or more detailed.

2. A concise summary may preserve all meaningful evidence.

3. Do not require identical examples, wording, or level
   of elaboration.

4. A genuinely different assumption, promised action,
   safeguard, limitation, or factual claim may be material.

5. An omission is material only when it plausibly changes
   demonstrated evidence under one or more criteria.

6. Do not assume that an explicitly stated safeguard is
   present in another response that omits it.

7. Do not confuse shared general topic with genuine
   preservation of decision-relevant evidence.

8. For NO, identify the specific material difference
   and the criterion or commitment it could affect.

9. For UNCERTAIN, identify precisely what is unresolved.

10. Never infer the original generation conditions or
    assign a final hiring decision.

Return only the required structured JSON.
"""


def fail(message):
    raise SystemExit(f"FAIL: {message}")


def output_paths(kind, identifier):
    if kind == "EVIDENCE":
        return EVIDENCE_DIR / f"{identifier}.json"
    return SEMANTIC_DIR / f"{identifier}.json"


def validate_saved(path, kind, identifier, source_row):
    saved = pilot.load_json(path)

    if saved.get("experiment") != "ESDSA_VALIDATION_AI_ANNOTATION_V2":
        fail(f"Wrong experiment in saved file: {path}")

    if saved.get("blinded_id") != identifier:
        fail(f"Blinded identifier mismatch: {path}")

    if saved.get("review_type") != kind:
        fail(f"Review type mismatch: {path}")

    if saved.get("reviewer_id") != REVIEWER:
        fail(f"Reviewer version mismatch: {path}")

    if saved.get("reference_decision") is not None:
        fail(f"Unexpected reference decision: {path}")

    if kind == "EVIDENCE":
        pilot.validate_evidence(source_row, saved["annotation"])
    else:
        pilot.validate_semantic(saved["annotation"])


def make_record(response, kind, identifier, annotation):
    result = pilot.record(response, kind, identifier, annotation)
    result["experiment"] = "ESDSA_VALIDATION_AI_ANNOTATION_V2"
    result["reviewer_id"] = REVIEWER
    result["annotation_protocol"] = "V2"
    result["provisional_ai_assessment"] = True
    result["independent_human_review"] = False
    result["reference_decision"] = None
    return result


def annotate_one(
    client,
    kind,
    identifier,
    source_row,
    payload,
):
    destination = output_paths(kind, identifier)

    if destination.exists():
        validate_saved(
            destination,
            kind,
            identifier,
            source_row,
        )
        return False

    if kind == "EVIDENCE":
        instructions = EVIDENCE_INSTRUCTIONS_V2
        schema = pilot.EVIDENCE_SCHEMA
        schema_name = "esdsa_evidence_annotation_v2"
    else:
        instructions = SEMANTIC_INSTRUCTIONS_V2
        schema = pilot.SEMANTIC_SCHEMA
        schema_name = "esdsa_semantic_equivalence_v2"

    for attempt in range(1, 4):
        response, annotation = pilot.call_model(
            client,
            instructions,
            payload,
            schema,
            schema_name,
        )

        try:
            if kind == "EVIDENCE":
                pilot.validate_evidence(source_row, annotation)
            else:
                pilot.validate_semantic(annotation)

        except SystemExit as exc:
            print(
                f"ANNOTATION VALIDATION FAILED "
                f"({kind}, {identifier}, attempt {attempt}/3): {exc}",
                flush=True,
            )

            if attempt == 3:
                raise

            continue

        pilot.save_json_new(
            destination,
            make_record(response, kind, identifier, annotation),
        )

        return True


def calculate_progress(evidence, semantic):
    evidence_complete = 0
    semantic_complete = 0
    evidence_statuses = Counter()
    semantic_statuses = Counter()

    for row in evidence:
        rid = row["blinded_response_id"]
        path = output_paths("EVIDENCE", rid)

        if not path.exists():
            continue

        validate_saved(path, "EVIDENCE", rid, row)
        saved = pilot.load_json(path)

        evidence_complete += 1

        for item in saved["annotation"]["criteria"]:
            evidence_statuses[item["status"]] += 1

    for row in semantic:
        gid = row["blinded_group_id"]
        path = output_paths("SEMANTIC_EQUIVALENCE", gid)

        if not path.exists():
            continue

        validate_saved(
            path,
            "SEMANTIC_EQUIVALENCE",
            gid,
            row,
        )

        saved = pilot.load_json(path)
        semantic_complete += 1
        semantic_statuses[
            saved["annotation"]["semantic_equivalence"]
        ] += 1

    return {
        "experiment": "ESDSA_VALIDATION_AI_ANNOTATION_V2",
        "status": (
            "COMPLETE"
            if evidence_complete == 216
            and semantic_complete == 72
            else "IN_PROGRESS"
        ),
        "partition": "VALIDATION",
        "annotator": REVIEWER,
        "evidence_completed": evidence_complete,
        "evidence_total": 216,
        "indicator_assessments_completed": (
            evidence_complete * 3
        ),
        "indicator_assessments_total": 648,
        "semantic_completed": semantic_complete,
        "semantic_total": 72,
        "evidence_status_counts": dict(evidence_statuses),
        "semantic_status_counts": dict(semantic_statuses),
        "reference_decisions_assigned": 0,
        "independent_human_review_completed": False,
        "updated_utc": datetime.now(
            timezone.utc
        ).isoformat(),
    }


def write_summary(progress):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    temporary = SUMMARY_FILE.with_suffix(".json.tmp")

    temporary.write_text(
        json.dumps(
            progress,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    temporary.replace(SUMMARY_FILE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--max-groups",
        type=int,
        default=72,
        help="Maximum groups to attempt this run (default: 72)",
    )
    args = parser.parse_args()

    if not 1 <= args.max_groups <= 72:
        fail("--max-groups must be between 1 and 72")

    print("ESDSA VALIDATION — COMPLETE AI ANNOTATION V2")
    print("=" * 65)
    print("Annotation protocol: V2")
    print("Requested model:", MODEL)
    print("Groups per run, maximum:", args.max_groups)
    print("Blinding key: NOT ACCESSED")
    print("Frozen ESDSA policy: NOT MODIFIED")
    print("ESDSA evaluator: NOT RUN")
    print("TEST partition: NOT ACCESSED")
    print()

    evidence, semantic, by_group = pilot.verify_inputs()

    groups = sorted(
        semantic,
        key=lambda row: row["blinded_group_id"],
    )

    if not os.environ.get("OPENAI_API_KEY"):
        fail("OPENAI_API_KEY is not configured")

    client = OpenAI(timeout=120, max_retries=0)

    new_evidence = 0
    new_semantic = 0
    processed_groups = 0

    try:
        for group in groups:
            gid = group["blinded_group_id"]

            members = sorted(
                by_group[gid],
                key=lambda row: row["blinded_response_id"],
            )

            all_outputs_exist = (
                all(
                    output_paths(
                        "EVIDENCE",
                        r["blinded_response_id"],
                    ).exists()
                    for r in members
                )
                and output_paths(
                    "SEMANTIC_EQUIVALENCE", gid
                ).exists()
            )

            if all_outputs_exist:
                for row in members:
                    validate_saved(
                        output_paths(
                            "EVIDENCE",
                            row["blinded_response_id"],
                        ),
                        "EVIDENCE",
                        row["blinded_response_id"],
                        row,
                    )

                validate_saved(
                    output_paths("SEMANTIC_EQUIVALENCE", gid),
                    "SEMANTIC_EQUIVALENCE",
                    gid,
                    group,
                )
                continue

            if processed_groups >= args.max_groups:
                break

            processed_groups += 1

            print(
                f"[{processed_groups}] "
                f"{gid} | {group['competency_code']}",
                flush=True,
            )

            for row in members:
                rid = row["blinded_response_id"]

                review_file = (
                    OUT_DIR
                    / "annotation_review_required"
                    / f"{rid}.json"
                )

                if review_file.exists():
                    print(
                        f"REVIEW PENDING: {rid}",
                        flush=True,
                    )
                    continue

                try:
                    created = annotate_one(
                        client,
                        "EVIDENCE",
                        rid,
                        row,
                        pilot.evidence_payload(row),
                    )

                    if created:
                        new_evidence += 1

                except SystemExit as exc:
                    error_dir = OUT_DIR / "annotation_review_required"
                    error_dir.mkdir(parents=True, exist_ok=True)

                    error_file = error_dir / f"{rid}.json"

                    error_record = {
                        "blinded_response_id": rid,
                        "blinded_group_id": gid,
                        "status": "REQUIRES_MANUAL_REVIEW",
                        "error": str(exc),
                        "reference_decision": None,
                    }

                    if not error_file.exists():
                        pilot.save_json_new(error_file, error_record)

                    print(
                        f"FLAGGED FOR REVIEW: {rid} | {exc}",
                        flush=True,
                    )

                    continue

                created = annotate_one(
                client,
                "SEMANTIC_EQUIVALENCE",
                gid,
                group,
                pilot.semantic_payload(group, members),
            )

            if created:
                new_semantic += 1

            print(
                f"PASS: {gid} | "
                f"{len(members)} evidence + 1 semantic",
                flush=True,
            )

    finally:
        progress = calculate_progress(evidence, semantic)
        write_summary(progress)

        print()
        print("=" * 65)
        print("ANNOTATION PROGRESS")
        print(
            "Evidence:",
            f"{progress['evidence_completed']}/216",
        )
        print(
            "Indicator assessments:",
            f"{progress['indicator_assessments_completed']}/648",
        )
        print(
            "Semantic groups:",
            f"{progress['semantic_completed']}/72",
        )
        print("New evidence calls:", new_evidence)
        print("New semantic calls:", new_semantic)
        print("Status:", progress["status"])
        print()
        print("Progress file:")
        print(SUMMARY_FILE.relative_to(ROOT))
        print()
        print("No final reference decisions assigned.")
        print("TEST partition: NOT ACCESSED")


if __name__ == "__main__":
    main()
