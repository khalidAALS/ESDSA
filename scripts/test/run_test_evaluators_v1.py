

"""ESDSA held-out TEST inference.

Reuses the previously verified validation evaluator functions,
the original frozen prompts, schemas and scoring thresholds.

No reference annotations, generation-condition labels, or
TEST performance comparisons are used in model inference.

Resumable: each completed model prediction is saved.
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
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

import run_validation_evaluators_v1 as evaluator
import generate_test_responses_v1 as generator

ROOT = Path(__file__).resolve().parents[2]

DATASET = ROOT / "results/test_generation_v1/test_responses_v1.csv"
GENERATION_MANIFEST = (
    ROOT / "results/test_generation_v1/test_generation_manifest_v1.json"
)
SCENARIOS = ROOT / "data/benchmark/test_scenarios_v1.csv"
SCENARIO_MANIFEST = (
    ROOT / "data/benchmark/test_scenarios_manifest_v1.json"
)
RUBRIC_DIR = ROOT / "data/benchmark/rubrics_v1"

OUT_DIR = ROOT / "results/test_evaluator_predictions_v1"
EVIDENCE_OUT = OUT_DIR / "evidence_aware_test_v1.jsonl"
SCORING_OUT = OUT_DIR / "scoring_only_test_v1.jsonl"

MODEL = "gpt-5.4-mini"
RETURNED_MODEL = "gpt-5.4-mini-2026-03-17"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_inputs():
    manifest = evaluator.read_csv  

    generation = json.loads(
        GENERATION_MANIFEST.read_text(encoding="utf-8")
    )
    scenario_record = json.loads(
        SCENARIO_MANIFEST.read_text(encoding="utf-8")
    )

    require(
        generation["status"] == "COMPLETE",
        "TEST generation has not completed",
    )
    require(
        generation["responses"] == 216
        and generation["families"] == 24,
        "Unexpected TEST generation counts",
    )
    require(
        file_hash(DATASET) == generation["consolidated_sha256"],
        "TEST dataset integrity check failed",
    )
    require(
        file_hash(SCENARIOS)
        == scenario_record["test_scenarios_sha256"]
        == generation["test_scenarios_sha256"],
        "TEST scenario file integrity mismatch",
    )
    require(
        generation["returned_model"] == RETURNED_MODEL,
        "Unexpected TEST generation model",
    )

    responses = manifest(DATASET)
    scenarios = manifest(SCENARIOS)

    require(
        len(responses) == 216 and len(scenarios) == 24,
        "Unexpected TEST dimensions",
    )

    scenario_lookup = {
        row["family_id"]: row for row in scenarios
    }

    require(
        len(scenario_lookup) == 24,
        "Duplicate TEST scenario families",
    )

    prepared = []
    seen_ids = set()
    counts = {}

    for row in responses:
        rid = row["response_id"]
        fid = row["family_id"]

        require(
            rid not in seen_ids,
            f"Duplicate TEST response ID: {rid}",
        )
        seen_ids.add(rid)

        require(
            row["partition"] == "TEST",
            f"Incorrect partition: {rid}",
        )
        require(
            fid in scenario_lookup,
            f"Unregistered TEST family: {fid}",
        )
        require(
            row["returned_model"] == RETURNED_MODEL,
            f"Incorrect source model: {rid}",
        )
        require(
            evaluator.digest(row["answer"])
            == row["answer_sha256"],
            f"Answer hash mismatch: {rid}",
        )
        require(
            rid.startswith(fid + "__"),
            f"Invalid response identifier: {rid}",
        )

        counts[fid] = counts.get(fid, 0) + 1
        scenario = scenario_lookup[fid]

        require(
            scenario["partition"] == "TEST",
            f"Non-TEST scenario: {fid}",
        )

        source = dict(scenario)
        source["interview_question"] = (
            generator.make_question(scenario)
        )

        rubric_path = (
            RUBRIC_DIR
            / f"{scenario['competency_code']}_rubric_v1.json"
        )
        rubric = json.loads(
            rubric_path.read_text(encoding="utf-8")
        )

        require(
            rubric["rubric_id"] == scenario["rubric_id"],
            f"Rubric mismatch: {rid}",
        )
        require(
            len(rubric["criteria"]) == 3,
            f"Rubric criterion mismatch: {rid}",
        )

        prepared.append((row, source, rubric))

    require(
        len(counts) == 24
        and all(n == 9 for n in counts.values()),
        "Expected nine responses for each TEST family",
    )

    return prepared


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run",
        action="store_true",
        help="Make API requests; default is dry run",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=432,
        help="Maximum new predictions in this run",
    )
    args = parser.parse_args()

    require(args.limit > 0, "Limit must be positive")

    freeze = evaluator.verify_freeze()
    scoring = evaluator.extract_original_scoring()

    require(
        evaluator.digest(scoring["SYSTEM_PROMPT"])
        == freeze["scripts"][
            "run_scoring_baseline_108.py"
        ]["prompt_sha256"],
        "Scoring prompt fingerprint mismatch",
    )

    prepared = prepare_inputs()
    ids = {row["response_id"] for row, _, _ in prepared}

    existing_evidence = evaluator.load_saved(
        EVIDENCE_OUT, ids
    )
    existing_scoring = evaluator.load_saved(
        SCORING_OUT, ids
    )

    tasks = []

    for kind in ("evidence", "scoring"):
        for row, source, rubric in prepared:
            rid = row["response_id"]

            if kind == "evidence":
                payload = evaluator.payload_evidence(
                    row, source, rubric
                )
                model_input = json.dumps(
                    payload, ensure_ascii=False
                )
                instructions = evaluator.evidence.INSTRUCTIONS
                saved = existing_evidence.get(rid)

            else:
                _, model_input = evaluator.payload_scoring(
                    row, source, rubric
                )
                instructions = scoring["SYSTEM_PROMPT"]
                saved = existing_scoring.get(rid)

            run_hash = evaluator.configuration_hash(
                kind,
                instructions,
                model_input,
                rubric,
            )

            if saved is not None:
                require(
                    saved["run_sha256"] == run_hash,
                    f"Saved configuration mismatch: {rid}",
                )
                require(
                    saved["answer_sha256"]
                    == evaluator.digest(row["answer"]),
                    f"Saved answer mismatch: {rid}",
                )
                require(
                    saved["requested_model"] == MODEL
                    and saved["partition"] == "TEST",
                    f"Saved metadata mismatch: {rid}",
                )
            else:
                tasks.append((
                    kind, row, source, rubric,
                    model_input, run_hash,
                ))

    print("ESDSA — HELD-OUT TEST EVALUATORS")
    print("=" * 65)
    print("Mode:", "API RUN" if args.run else "DRY RUN")
    print("TEST responses:", len(prepared))
    print("Original evaluator prompts: VERIFIED")
    print("Evidence-aware saved:", len(existing_evidence))
    print("Scoring-only saved:", len(existing_scoring))
    print("Pending predictions:", len(tasks))
    print("New API requests this run:", min(args.limit, len(tasks)))
    print("Reference labels: NOT LOADED")
    print("Generation conditions: NOT SENT TO MODEL")
    print("Frozen ESDSA policy: NOT MODIFIED")
    print()

    if not args.run:
        print("DRY RUN PASSED — zero API requests.")
        return

    require(
        os.environ.get("OPENAI_API_KEY"),
        "OPENAI_API_KEY is missing",
    )

    client = OpenAI(timeout=120.0, max_retries=0)
    selected = tasks[:args.limit]

    for index, task in enumerate(selected, start=1):
        kind, row, source, rubric, model_input, run_hash = task
        rid = row["response_id"]

        print(
            f"[{index}/{len(selected)}] {kind}: {rid}",
            flush=True,
        )

        try:
            if kind == "evidence":
                response = client.responses.create(
                    model=MODEL,
                    instructions=evaluator.evidence.INSTRUCTIONS,
                    input=model_input,
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "esdsa_competency_evidence",
                            "strict": True,
                            "schema": evaluator.evidence.SCHEMA,
                        }
                    },
                    store=False,
                )

                require(
                    response.status == "completed"
                    and bool(response.output_text),
                    f"Incomplete response: {rid}",
                )

                parsed = json.loads(response.output_text)

                decision, warnings = (
                    evaluator.evidence.evaluate_output(
                        parsed, rubric, row["answer"]
                    )
                )

                details = {
                    "decision": decision,
                    "validation_warnings": warnings,
                }
                destination = EVIDENCE_OUT

            else:
                descriptions, user_prompt = (
                    evaluator.payload_scoring(
                        row, source, rubric
                    )
                )

                require(
                    user_prompt == model_input,
                    f"Scoring input mismatch: {rid}",
                )

                response = client.responses.create(
                    model=MODEL,
                    instructions=scoring["SYSTEM_PROMPT"],
                    input=user_prompt,
                    text={"format": {"type": "json_object"}},
                    max_output_tokens=1200,
                    store=False,
                )

                require(
                    response.status == "completed"
                    and bool(response.output_text),
                    f"Incomplete scoring response: {rid}",
                )

                parsed = scoring["parse_response"](
                    response.output_text, descriptions
                )
                scores = [
                    item["score"] for item in parsed["criteria"]
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
                destination = SCORING_OUT

            require(
                response.model == RETURNED_MODEL,
                f"Unexpected returned model: {rid}",
            )

            usage = response.usage

            record = {
                "response_id": rid,
                "family_id": row["family_id"],
                "partition": "TEST",
                "experiment": (
                    f"ESDSA_TEST_{kind.upper()}_V1"
                ),
                "requested_model": MODEL,
                "returned_model": response.model,
                "api_response_id": response.id,
                "timestamp_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "run_sha256": run_hash,
                "answer_sha256": evaluator.digest(row["answer"]),
                "rubric_id": rubric["rubric_id"],
                "parsed_output": parsed,
                "raw_output": response.output_text,
                "input_tokens": (
                    usage.input_tokens if usage else None
                ),
                "output_tokens": (
                    usage.output_tokens if usage else None
                ),
                **details,
            }

            evaluator.append_new(destination, record)

            print(
                f"PASS: {kind} | {details['decision']}",
                flush=True,
            )

        except Exception as exc:
            print(
                f"STOPPED: {type(exc).__name__}: {exc}",
                flush=True,
            )
            print(
                "Saved predictions remain intact. "
                "Rerun to resume."
            )
            raise SystemExit(1) from exc

    evidence_count = len(
        evaluator.load_saved(EVIDENCE_OUT, ids)
    )
    scoring_count = len(
        evaluator.load_saved(SCORING_OUT, ids)
    )

    print()
    print("=" * 65)
    print("TEST INFERENCE PROGRESS")
    print(f"Evidence-aware: {evidence_count}/216")
    print(f"Scoring-only: {scoring_count}/216")
    print("Reference labels: NOT LOADED")
    print("Frozen policy: NOT MODIFIED")


if __name__ == "__main__":
    main()
