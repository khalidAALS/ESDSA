

"""Run original ESDSA evaluators on VALIDATION responses.

Original prompts, schemas, scoring thresholds and model settings
are preserved. No provisional reference annotations or TEST data
are accessed. Predictions are saved separately and resumably.
"""

# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

import argparse
import ast
import csv
import hashlib
import json
import os

from datetime import datetime, timezone
from pathlib import Path
from openai import OpenAI

import run_benchmark_evaluator as evidence


ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT
    / "results/validation_consolidated_v1/validation_responses_v1.csv"
)

SCENARIOS = ROOT / "data/benchmark/validation_scenarios_v2.csv"
RUBRICS = ROOT / "data/benchmark/rubrics_v1"

FREEZE = (
    ROOT
    / "data/benchmark/policy_freeze_v2/"
    "esdsa_evaluation_protocol_freeze_v1.json"
)

OUTPUT_DIR = ROOT / "results/validation_evaluator_predictions_v1"

EVIDENCE_OUT = (
    OUTPUT_DIR / "evidence_aware_validation_v1.jsonl"
)

SCORING_OUT = (
    OUTPUT_DIR / "scoring_only_validation_v1.jsonl"
)

EVIDENCE_PATH = ROOT / "archive/frozen_originals/run_benchmark_evaluator.py"
SCORING_PATH = ROOT / "archive/frozen_originals/run_scoring_baseline_108.py"

MODEL = "gpt-5.4-mini"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    require(path.is_file(), f"Missing input: {path}")

    with path.open(
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        return list(csv.DictReader(handle))


def extract_original_scoring():
    """Read original scoring definitions without running its experiment."""

    tree = ast.parse(
        SCORING_PATH.read_text(encoding="utf-8")
    )

    allowed_constants = {
        "MODEL",
        "SYSTEM_PROMPT",
        "ADVANCE_THRESHOLD",
        "REJECT_THRESHOLD",
    }

    allowed_functions = {
        "criterion_id",
        "determine_decision",
        "parse_response",
    }

    nodes = []

    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in allowed_functions
        ):
            nodes.append(node)

        elif isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in allowed_constants
            ):
                nodes.append(node)

    module = ast.fix_missing_locations(
        ast.Module(body=nodes, type_ignores=[])
    )

    namespace = {"json": json}

    exec(
        compile(module, str(SCORING_PATH), "exec"),
        namespace,
    )

    for name in allowed_constants | allowed_functions:
        require(
            name in namespace,
            f"Missing original scoring definition: {name}",
        )

    require(
        namespace["MODEL"] == MODEL,
        "Scoring model mismatch",
    )

    require(
        namespace["ADVANCE_THRESHOLD"] == 3.0,
        "Advance threshold mismatch",
    )

    require(
        namespace["REJECT_THRESHOLD"] == 1.5,
        "Reject threshold mismatch",
    )

    return namespace


def verify_freeze():
    freeze = json.loads(
        FREEZE.read_text(encoding="utf-8")
    )

    scripts = freeze["scripts"]

    for path in (EVIDENCE_PATH, SCORING_PATH):
        expected = scripts[path.name]["sha256"]
        actual = file_digest(path)

        require(
            actual == expected,
            f"Original evaluator altered: {path.name}",
        )

    require(
        evidence.MODEL == MODEL,
        "Evidence evaluator model mismatch",
    )

    require(
        digest(evidence.INSTRUCTIONS)
        == scripts[EVIDENCE_PATH.name]["prompt_sha256"],
        "Evidence evaluator prompt changed",
    )

    return freeze


def load_inputs():
    rows = read_csv(INPUT)
    scenarios = read_csv(SCENARIOS)

    require(
        len(rows) == 216 and len(scenarios) == 24,
        "Unexpected validation dataset dimensions",
    )

    by_family = {
        row["family_id"]: row
        for row in scenarios
    }

    require(
        len(by_family) == 24,
        "Duplicate scenario families",
    )

    ids = set()
    family_counts = {}
    rubric_cache = {}
    prepared = []

    for row in rows:
        rid = row["response_id"]
        fid = row["family_id"]

        require(
            rid not in ids,
            f"Duplicate response ID: {rid}",
        )
        ids.add(rid)

        require(
            row["partition"] == "VALIDATION",
            f"Non-validation response: {rid}",
        )

        require(
            fid in by_family,
            f"Unknown scenario family: {fid}",
        )

        require(
            bool(row["answer"].strip()),
            f"Empty candidate answer: {rid}",
        )

        require(
            digest(row["answer"]) == row["answer_sha256"],
            f"Answer hash mismatch: {rid}",
        )

        require(
            rid.startswith(fid + "__"),
            f"Invalid response identifier: {rid}",
        )

        source = by_family[fid]

        require(
            source["partition"] == "VALIDATION",
            f"Invalid scenario partition: {fid}",
        )

        family_counts[fid] = family_counts.get(fid, 0) + 1

        competency = source["competency_code"]

        if competency not in rubric_cache:
            path = (
                RUBRICS
                / f"{competency}_rubric_v1.json"
            )

            rubric_cache[competency] = json.loads(
                path.read_text(encoding="utf-8")
            )

        rubric = rubric_cache[competency]

        require(
            rubric["rubric_id"] == source["rubric_id"],
            f"Rubric mismatch: {rid}",
        )

        require(
            len(rubric["criteria"]) == 3,
            f"Expected three rubric criteria: {rid}",
        )

        require(
            row["returned_model"]
            == "gpt-5.4-mini-2026-03-17",
            f"Unexpected response-generator model: {rid}",
        )

        prepared.append((row, source, rubric))

    require(
        set(family_counts) == set(by_family),
        "Missing validation family",
    )

    require(
        all(count == 9 for count in family_counts.values()),
        "Expected nine responses per validation family",
    )

    return prepared


def load_saved(path, expected_ids):
    records = {}

    if not path.exists():
        return records

    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue

            record = json.loads(line)
            rid = record["response_id"]

            require(
                rid in expected_ids,
                f"Unknown saved response: {rid}",
            )

            require(
                rid not in records,
                f"Duplicate saved response: {rid}",
            )

            records[rid] = record

    return records


def payload_evidence(row, source, rubric):
    return {
        "role": rubric["role_name"],
        "competency": rubric["competency_name"],
        "interview_question": source["interview_question"],
        "candidate_answer": row["answer"],
        "criteria": [
            {
                "id": criterion["id"],
                "name": criterion["name"],
                "definition": criterion["definition"],
            }
            for criterion in rubric["criteria"]
        ],
    }


def payload_scoring(row, source, rubric):

    descriptions = [
        (
            f"{criterion['id']}: "
            f"{criterion['name']} — "
            f"{criterion['definition']}"
        )
        for criterion in rubric["criteria"]
    ]

    content = {
        "role": source["role_code"],
        "interview_question": source["interview_question"],
        "candidate_answer": row["answer"],
        "criteria": [
            {
                "criterion_id": criterion["id"],
                "description": (
                    f"{criterion['name']} — "
                    f"{criterion['definition']}"
                ),
            }
            for criterion in rubric["criteria"]
        ],
    }

    user_prompt = (
        "Evaluate the following interview response "
        "and return JSON only.\n\n"
        + json.dumps(
            content,
            ensure_ascii=False,
            indent=2,
        )
    )

    return descriptions, user_prompt


def configuration_hash(kind, instructions, model_input, rubric):
    configuration = {
        "kind": kind,
        "model": MODEL,
        "instructions": instructions,
        "input": model_input,
        "rubric_id": rubric["rubric_id"],
        "evidence_schema": (
            evidence.SCHEMA if kind == "evidence" else None
        ),
        "scoring_thresholds": (
            [3.0, 1.5] if kind == "scoring" else None
        ),
        "scoring_max_output_tokens": (
            1200 if kind == "scoring" else None
        ),
    }

    return digest(
        json.dumps(
            configuration,
            sort_keys=True,
            ensure_ascii=False,
        )
    )


def append_new(path, record):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            json.dumps(
                record,
                ensure_ascii=False,
            ) + "\n"
        )

        handle.flush()
        os.fsync(handle.fileno())


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--run",
        action="store_true",
        help="Make API requests; otherwise dry run",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=432,
        help="Maximum NEW requests in this run",
    )

    parser.add_argument(
        "--only",
        choices=("both", "evidence", "scoring"),
        default="both",
    )

    args = parser.parse_args()

    require(
        args.limit > 0,
        "--limit must be positive",
    )

    freeze = verify_freeze()
    scoring = extract_original_scoring()

    require(
        digest(scoring["SYSTEM_PROMPT"])
        == freeze["scripts"][
            SCORING_PATH.name
        ]["prompt_sha256"],
        "Original scoring prompt changed",
    )

    prepared = load_inputs()

    ids = {
        row["response_id"]
        for row, _, _ in prepared
    }

    existing_evidence = load_saved(
        EVIDENCE_OUT,
        ids,
    )

    existing_scoring = load_saved(
        SCORING_OUT,
        ids,
    )

    tasks = []

    selected_kinds = (
        ("evidence", "scoring")
        if args.only == "both"
        else (args.only,)
    )

    for kind in selected_kinds:
        for row, source, rubric in prepared:
            rid = row["response_id"]

            if kind == "evidence":
                model_input = json.dumps(
                    payload_evidence(row, source, rubric),
                    ensure_ascii=False,
                )

                instructions = evidence.INSTRUCTIONS
                saved = existing_evidence.get(rid)

            else:
                descriptions, model_input = payload_scoring(
                    row,
                    source,
                    rubric,
                )

                instructions = scoring["SYSTEM_PROMPT"]
                saved = existing_scoring.get(rid)

            run_hash = configuration_hash(
                kind,
                instructions,
                model_input,
                rubric,
            )

            if saved:
                require(
                    saved["run_sha256"] == run_hash,
                    f"Saved configuration mismatch: {rid}",
                )

                require(
                    saved["answer_sha256"]
                    == digest(row["answer"]),
                    f"Saved answer mismatch: {rid}",
                )

                require(
                    saved["requested_model"] == MODEL,
                    f"Saved model mismatch: {rid}",
                )

            else:
                tasks.append((
                    kind,
                    row,
                    source,
                    rubric,
                    model_input,
                    run_hash,
                ))

    print("ESDSA VALIDATION — ORIGINAL EVALUATOR PROMPTS")
    print("=" * 65)

    print(
        "Mode:",
        "API RUN" if args.run else "DRY RUN",
    )

    print("Validation responses:", len(prepared))
    print("Original prompts: SHA256 VERIFIED")

    print(
        "Existing evidence predictions:",
        len(existing_evidence),
    )

    print(
        "Existing scoring predictions:",
        len(existing_scoring),
    )

    print(
        "Pending selected predictions:",
        len(tasks),
    )

    print(
        "Maximum new API calls:",
        min(args.limit, len(tasks)),
    )

    print("Provisional reference labels: NOT LOADED")
    print("Generation conditions: NOT SENT TO MODEL")
    print("Blinding key: NOT ACCESSED")
    print("TEST partition: NOT ACCESSED")

    if not args.run:
        print()
        print("No API calls made.")
        print("Re-run with --run.")
        return

    require(
        os.getenv("OPENAI_API_KEY"),
        "OPENAI_API_KEY is missing",
    )

    client = OpenAI(
        timeout=120.0,
        max_retries=0,
    )

    selected_tasks = tasks[:args.limit]

    for index, task in enumerate(selected_tasks, start=1):
        (
            kind,
            row,
            source,
            rubric,
            model_input,
            run_hash,
        ) = task

        rid = row["response_id"]

        print(
            f"[{index}/{len(selected_tasks)}] "
            f"{kind} {rid}",
            flush=True,
        )

        try:
            if kind == "evidence":
                response = client.responses.create(
                    model=MODEL,
                    instructions=evidence.INSTRUCTIONS,
                    input=model_input,
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "esdsa_competency_evidence",
                            "strict": True,
                            "schema": evidence.SCHEMA,
                        }
                    },
                    store=False,
                )

                require(
                    response.status == "completed"
                    and bool(response.output_text),
                    f"Incomplete evaluator response: {rid}",
                )

                parsed = json.loads(
                    response.output_text
                )

                decision, warnings = evidence.evaluate_output(
                    parsed,
                    rubric,
                    row["answer"],
                )

                details = {
                    "decision": decision,
                    "validation_warnings": warnings,
                }

                output_path = EVIDENCE_OUT

            else:
                descriptions, user_prompt = payload_scoring(
                    row,
                    source,
                    rubric,
                )

                require(
                    user_prompt == model_input,
                    "Scoring payload mismatch",
                )

                response = client.responses.create(
                    model=MODEL,
                    instructions=scoring["SYSTEM_PROMPT"],
                    input=user_prompt,
                    text={
                        "format": {
                            "type": "json_object",
                        }
                    },
                    max_output_tokens=1200,
                    store=False,
                )

                require(
                    response.status == "completed"
                    and bool(response.output_text),
                    f"Incomplete scoring response: {rid}",
                )

                parsed = scoring["parse_response"](
                    response.output_text,
                    descriptions,
                )

                scores = [
                    item["score"]
                    for item in parsed["criteria"]
                ]

                details = {
                    "scores": scores,
                    "mean_score": sum(scores) / 3,
                    "decision": scoring["determine_decision"](
                        scores
                    ),
                    "scoring_rule": {
                        "advance_mean_at_least": 3.0,
                        "reject_mean_at_most": 1.5,
                        "other": "DEFER",
                    },
                }

                output_path = SCORING_OUT

            require(
                response.model
                == "gpt-5.4-mini-2026-03-17",
                "Unexpected returned model version",
            )

            usage = response.usage

            record = {
                "response_id": rid,
                "family_id": row["family_id"],
                "partition": "VALIDATION",
                "experiment": (
                    f"ESDSA_VALIDATION_{kind.upper()}_V1"
                ),
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
                "input_tokens": (
                    usage.input_tokens
                    if usage else None
                ),
                "output_tokens": (
                    usage.output_tokens
                    if usage else None
                ),
                **details,
            }

            append_new(
                output_path,
                record,
            )

            print(
                f"  PASS: {details['decision']}",
                flush=True,
            )

        except Exception as exc:
            print(
                f"STOPPED: {type(exc).__name__}: {exc}",
                flush=True,
            )

            print(
                "Saved predictions remain intact. "
                "Rerun the same command to resume."
            )

            raise SystemExit(1) from exc

    evidence_count = len(
        load_saved(EVIDENCE_OUT, ids)
    )

    scoring_count = len(
        load_saved(SCORING_OUT, ids)
    )

    print()
    print("VALIDATION INFERENCE PROGRESS")
    print(
        f"Evidence-aware: {evidence_count}/216"
    )
    print(
        f"Scoring-only: {scoring_count}/216"
    )
    print(
        "No provisional reference labels loaded; "
        "TEST not accessed."
    )


if __name__ == "__main__":
    main()
