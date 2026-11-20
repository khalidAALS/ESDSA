

"""Blinded provisional annotations for the ESDSA TEST partition.

Reuses the established validation v2 annotation prompts and schemas.
Does not read ESDSA TEST predictions or use generation conditions
as reference decisions.

Prepare once, then run resumably. No policy changes.
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
import csv
import hashlib
import json
import os
import secrets
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

import run_validation_annotation_pilot_v1 as pilot
import run_validation_annotations_v2 as annotation_v2

ROOT = Path(__file__).resolve().parents[2]

DATASET = ROOT / "results/test_generation_v1/test_responses_v1.csv"
SCENARIOS = ROOT / "data/benchmark/test_scenarios_v1.csv"
RUBRICS = ROOT / "data/benchmark/rubrics_v1"

LOCK = (
    ROOT / "results/test_evaluator_predictions_v1/"
    "test_predictions_lock_v1.json"
)

OUT = ROOT / "results/test_ai_annotations_v2"
EVIDENCE_TEMPLATE = OUT / "test_evidence_template_v2.csv"
SEMANTIC_TEMPLATE = OUT / "test_semantic_template_v2.csv"
PRIVATE_KEY = OUT / "test_annotation_blinding_key_v2.csv"
TEMPLATE_MANIFEST = OUT / "test_annotation_template_manifest_v2.json"

EVIDENCE_DIR = OUT / "evidence"
SEMANTIC_DIR = OUT / "semantic"
REVIEW_DIR = OUT / "review_required"
PROGRESS = OUT / "test_annotation_progress_v2.json"

MODEL = "gpt-5.4-mini"
REVIEWER = "AI_ASSISTED_GPT54_MINI_V2"

CONDITIONS = {"SUFFICIENT", "INSUFFICIENT", "NEGATIVE"}
VARIANTS = {"CANONICAL", "CONVERSATIONAL", "CONCISE"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path):
    require(path.is_file(), f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path):
    require(path.is_file(), f"Missing file: {path}")

    with path.open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        return list(csv.DictReader(handle))


def write_csv_new(path, rows):
    require(rows, "Cannot write empty CSV")
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "x", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0])
        )
        writer.writeheader()
        writer.writerows(rows)


def write_json_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def verify_locked_inputs():
    lock = load_json(LOCK)

    require(
        lock["status"] == "LOCKED",
        "TEST predictions have not been locked",
    )

    require(
        lock["dataset_sha256"] == file_hash(DATASET),
        "TEST dataset differs from prediction lock",
    )

    for item in lock["prediction_files"].values():
        path = ROOT / item["file"]

        require(
            path.is_file()
            and file_hash(path) == item["sha256"],
            "A locked prediction file has changed",
        )

    responses = read_csv(DATASET)
    scenarios = read_csv(SCENARIOS)

    require(
        len(responses) == 216 and len(scenarios) == 24,
        "Unexpected TEST dimensions",
    )

    scenario_lookup = {
        row["family_id"]: row for row in scenarios
    }

    require(
        len(scenario_lookup) == 24,
        "Duplicate TEST scenario IDs",
    )

    groups = defaultdict(list)
    seen_ids = set()
    rubric_lookup = {}

    for row in responses:
        rid = row["response_id"]
        fid = row["family_id"]

        require(rid not in seen_ids, f"Duplicate response: {rid}")
        seen_ids.add(rid)

        require(
            row["partition"] == "TEST"
            and fid in scenario_lookup,
            f"Invalid TEST response: {rid}",
        )

        require(
            row["generation_condition"] in CONDITIONS
            and row["variant"] in VARIANTS,
            f"Invalid generation metadata: {rid}",
        )

        require(
            hashlib.sha256(
                row["answer"].encode("utf-8")
            ).hexdigest() == row["answer_sha256"],
            f"Answer hash mismatch: {rid}",
        )

        scenario = scenario_lookup[fid]
        code = scenario["competency_code"]

        if code not in rubric_lookup:
            rubric = load_json(
                RUBRICS / f"{code}_rubric_v1.json"
            )

            require(
                rubric["competency_code"] == code
                and len(rubric["criteria"]) == 3,
                f"Invalid rubric: {code}",
            )

            rubric_lookup[code] = rubric

        require(
            rubric_lookup[code]["rubric_id"]
            == scenario["rubric_id"],
            f"Rubric ID mismatch: {fid}",
        )

        groups[
            (fid, row["generation_condition"])
        ].append(row)

    require(
        len(groups) == 72 and len(seen_ids) == 216,
        "Unexpected group or response count",
    )

    for key, members in groups.items():
        require(
            len(members) == 3
            and {r["variant"] for r in members} == VARIANTS,
            f"Incorrect response variants: {key}",
        )

    return responses, scenario_lookup, rubric_lookup, groups


def prepare_templates():
    for path in (
        EVIDENCE_TEMPLATE,
        SEMANTIC_TEMPLATE,
        PRIVATE_KEY,
        TEMPLATE_MANIFEST,
    ):
        require(
            not path.exists(),
            f"Output already exists: {path}",
        )

    _, scenarios, rubrics, groups = verify_locked_inputs()

    evidence_rows = []
    semantic_rows = []
    key_rows = []

    used_ids = set()

    def new_id(prefix):
        while True:
            identifier = prefix + secrets.token_hex(8).upper()
            if identifier not in used_ids:
                used_ids.add(identifier)
                return identifier

    for (fid, condition), members in sorted(groups.items()):
        scenario = scenarios[fid]
        rubric = rubrics[scenario["competency_code"]]

        gid = new_id("TG-")

        question = (
            "Scenario: "
            + scenario["scenario_context"].strip()
            + "\n\nInterview question: "
            + scenario["interview_question"].strip()
        )

        semantic = {
            "blinded_group_id": gid,
            "family_id": fid,
            "competency_code": scenario["competency_code"],
            "competency_name": scenario["competency_name"],
            "interview_question": question,
        }

        shuffled = list(members)
        secrets.SystemRandom().shuffle(shuffled)

        for slot, response in zip("ABC", shuffled):
            rid = new_id("TR-")
            answer = response["answer"]

            semantic[f"response_{slot}_id"] = rid
            semantic[f"response_{slot}_text"] = answer

            evidence = {
                "blinded_response_id": rid,
                "blinded_group_id": gid,
                "family_id": fid,
                "role_name": scenario["role_name"],
                "competency_code": scenario["competency_code"],
                "competency_name": scenario["competency_name"],
                "scenario_profile": scenario["scenario_profile"],
                "interview_question": question,
                "rubric_id": rubric["rubric_id"],
                "answer": answer,
            }

            for i, criterion in enumerate(
                rubric["criteria"], start=1
            ):
                prefix = f"criterion_{i}"

                evidence[f"{prefix}_id"] = criterion["id"]
                evidence[f"{prefix}_name"] = criterion["name"]
                evidence[f"{prefix}_definition"] = (
                    criterion["definition"]
                )

            evidence_rows.append(evidence)

            key_rows.append({
                "blinded_response_id": rid,
                "blinded_group_id": gid,
                "semantic_slot": slot,
                "original_response_id": response["response_id"],
                "family_id": fid,
                "generation_condition": condition,
                "original_variant": response["variant"],
                "answer_sha256": response["answer_sha256"],
            })

        semantic_rows.append(semantic)

    secrets.SystemRandom().shuffle(evidence_rows)
    secrets.SystemRandom().shuffle(semantic_rows)

    write_csv_new(EVIDENCE_TEMPLATE, evidence_rows)
    write_csv_new(SEMANTIC_TEMPLATE, semantic_rows)
    write_csv_new(PRIVATE_KEY, key_rows)

    os.chmod(PRIVATE_KEY, 0o600)

    manifest = {
        "experiment": "ESDSA_TEST_ANNOTATION_V2",
        "status": "PREPARED",
        "responses": 216,
        "semantic_groups": 72,
        "annotation_prompt_version": "VALIDATION_V2_UNCHANGED",
        "dataset_sha256": file_hash(DATASET),
        "prediction_lock_sha256": file_hash(LOCK),
        "evidence_template_sha256": file_hash(
            EVIDENCE_TEMPLATE
        ),
        "semantic_template_sha256": file_hash(
            SEMANTIC_TEMPLATE
        ),
        "private_key_sha256": file_hash(PRIVATE_KEY),
        "generation_conditions_used_as_references": False,
        "independent_human_review": False,
    }

    write_json_new(TEMPLATE_MANIFEST, manifest)

    print("TEST ANNOTATION TEMPLATES: PREPARED")
    print("Responses: 216")
    print("Semantic groups: 72")
    print("Blinding key: created separately")
    print("Prediction results: NOT READ")
    print("API calls: 0")


def load_templates():
    manifest = load_json(TEMPLATE_MANIFEST)

    require(
        manifest["status"] == "PREPARED",
        "Annotation templates not prepared",
    )

    require(
        file_hash(EVIDENCE_TEMPLATE)
        == manifest["evidence_template_sha256"],
        "Evidence template changed",
    )

    require(
        file_hash(SEMANTIC_TEMPLATE)
        == manifest["semantic_template_sha256"],
        "Semantic template changed",
    )

    verify_locked_inputs()

    evidence = read_csv(EVIDENCE_TEMPLATE)
    semantic = read_csv(SEMANTIC_TEMPLATE)

    require(
        len(evidence) == 216 and len(semantic) == 72,
        "Annotation template count mismatch",
    )

    by_group = defaultdict(list)

    for row in evidence:
        by_group[row["blinded_group_id"]].append(row)

    for group in semantic:
        gid = group["blinded_group_id"]
        members = by_group[gid]

        require(
            len(members) == 3,
            f"Incorrect blinded group: {gid}",
        )

        for slot in "ABC":
            rid = group[f"response_{slot}_id"]
            answer = group[f"response_{slot}_text"]

            matching = [
                item for item in members
                if item["blinded_response_id"] == rid
                and item["answer"] == answer
            ]

            require(
                len(matching) == 1,
                f"Blinded member mismatch: {gid}/{slot}",
            )

    return evidence, semantic, by_group


def save_annotation(response, result, kind, identifier):
    record = {
        "experiment": "ESDSA_TEST_AI_ANNOTATION_V2",
        "partition": "TEST",
        "review_type": kind,
        "blinded_id": identifier,
        "reviewer_id": REVIEWER,
        "requested_model": MODEL,
        "returned_model": response.model,
        "api_response_id": response.id,
        "annotated_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "annotation": result,
        "reference_decision": None,
        "independent_human_review": False,
    }

    folder = (
        EVIDENCE_DIR
        if kind == "EVIDENCE"
        else SEMANTIC_DIR
    )

    write_json_new(folder / f"{identifier}.json", record)


def validate_existing(path, kind, identifier, source):
    saved = load_json(path)

    require(
        saved["experiment"] == "ESDSA_TEST_AI_ANNOTATION_V2"
        and saved["blinded_id"] == identifier
        and saved["review_type"] == kind
        and saved["reviewer_id"] == REVIEWER,
        f"Saved annotation mismatch: {identifier}",
    )

    if kind == "EVIDENCE":
        pilot.validate_evidence(
            source, saved["annotation"]
        )
    else:
        pilot.validate_semantic(saved["annotation"])


def annotate(client, kind, identifier, source, payload):
    folder = (
        EVIDENCE_DIR
        if kind == "EVIDENCE"
        else SEMANTIC_DIR
    )

    path = folder / f"{identifier}.json"

    if path.exists():
        validate_existing(path, kind, identifier, source)
        return False

    if kind == "EVIDENCE":
        instructions = annotation_v2.EVIDENCE_INSTRUCTIONS_V2
        schema = pilot.EVIDENCE_SCHEMA
        schema_name = "esdsa_evidence_annotation_v2"
    else:
        instructions = annotation_v2.SEMANTIC_INSTRUCTIONS_V2
        schema = pilot.SEMANTIC_SCHEMA
        schema_name = "esdsa_semantic_equivalence_v2"

    for attempt in (1, 2):
        response, result = pilot.call_model(
            client,
            instructions,
            payload,
            schema,
            schema_name,
        )

        try:
            if kind == "EVIDENCE":
                pilot.validate_evidence(source, result)
            else:
                pilot.validate_semantic(result)

        except SystemExit as exc:
            if attempt == 2:
                REVIEW_DIR.mkdir(
                    parents=True, exist_ok=True
                )

                flag = REVIEW_DIR / f"{identifier}.json"

                if not flag.exists():
                    write_json_new(flag, {
                        "blinded_id": identifier,
                        "kind": kind,
                        "error": str(exc),
                        "status": "MANUAL_REVIEW_REQUIRED",
                    })

                print(
                    f"FLAGGED: {identifier} | {exc}",
                    flush=True,
                )
                return False

            continue

        save_annotation(
            response, result, kind, identifier
        )
        return True

    return False


def progress_report(evidence, semantic):
    evidence_complete = 0
    semantic_complete = 0
    statuses = Counter()
    equivalences = Counter()

    for row in evidence:
        rid = row["blinded_response_id"]
        path = EVIDENCE_DIR / f"{rid}.json"

        if path.exists():
            validate_existing(path, "EVIDENCE", rid, row)
            saved = load_json(path)

            evidence_complete += 1

            for criterion in saved["annotation"]["criteria"]:
                statuses[criterion["status"]] += 1

    for row in semantic:
        gid = row["blinded_group_id"]
        path = SEMANTIC_DIR / f"{gid}.json"

        if path.exists():
            validate_existing(
                path, "SEMANTIC_EQUIVALENCE", gid, row
            )

            saved = load_json(path)
            semantic_complete += 1

            equivalences[
                saved["annotation"]["semantic_equivalence"]
            ] += 1

    return {
        "status": (
            "COMPLETE"
            if evidence_complete == 216
            and semantic_complete == 72
            else "IN_PROGRESS"
        ),
        "evidence_completed": evidence_complete,
        "indicator_assessments_completed": evidence_complete * 3,
        "semantic_completed": semantic_complete,
        "evidence_status_counts": dict(statuses),
        "semantic_equivalence_counts": dict(equivalences),
        "reference_decisions_assigned": 0,
        "independent_human_review": False,
        "test_prediction_comparison_performed": False,
        "updated_utc": datetime.now(
            timezone.utc
        ).isoformat(),
    }


def run_annotations():
    evidence, semantic, by_group = load_templates()

    require(
        os.environ.get("OPENAI_API_KEY"),
        "OPENAI_API_KEY is missing",
    )

    client = OpenAI(timeout=120, max_retries=0)

    try:
        for index, group in enumerate(
            sorted(
                semantic,
                key=lambda row: row["blinded_group_id"],
            ),
            start=1,
        ):
            gid = group["blinded_group_id"]
            members = sorted(
                by_group[gid],
                key=lambda row: row["blinded_response_id"],
            )

            pending = any(
                not (
                    EVIDENCE_DIR
                    / f"{row['blinded_response_id']}.json"
                ).exists()
                and not (
                    REVIEW_DIR
                    / f"{row['blinded_response_id']}.json"
                ).exists()
                for row in members
            )

            pending = pending or not (
                SEMANTIC_DIR / f"{gid}.json"
            ).exists()

            if not pending:
                continue

            print(
                f"[{index}/72] {gid}",
                flush=True,
            )

            for row in members:
                rid = row["blinded_response_id"]

                if (REVIEW_DIR / f"{rid}.json").exists():
                    continue

                annotate(
                    client,
                    "EVIDENCE",
                    rid,
                    row,
                    pilot.evidence_payload(row),
                )

            if not (REVIEW_DIR / f"{gid}.json").exists():
                annotate(
                    client,
                    "SEMANTIC_EQUIVALENCE",
                    gid,
                    group,
                    pilot.semantic_payload(group, members),
                )

            print(
                f"GROUP PROCESSED: {gid}",
                flush=True,
            )

    finally:
        result = progress_report(evidence, semantic)

        OUT.mkdir(parents=True, exist_ok=True)
        temporary = PROGRESS.with_suffix(".json.tmp")

        temporary.write_text(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

        temporary.replace(PROGRESS)

        print()
        print("=" * 65)
        print("TEST ANNOTATION PROGRESS")
        print(
            f"Evidence: "
            f"{result['evidence_completed']}/216"
        )
        print(
            f"Indicators: "
            f"{result['indicator_assessments_completed']}/648"
        )
        print(
            f"Semantic groups: "
            f"{result['semantic_completed']}/72"
        )
        print("Status:", result["status"])
        print("Predictions: NOT USED")
        print("Independent human reference: NOT ESTABLISHED")
        print("Frozen policy: NOT MODIFIED")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--prepare",
        action="store_true",
        help="Create blinded templates without API calls",
    )

    parser.add_argument(
        "--run",
        action="store_true",
        help="Run provisional AI annotation",
    )

    args = parser.parse_args()

    require(
        args.prepare != args.run,
        "Choose exactly one of --prepare or --run",
    )

    if args.prepare:
        prepare_templates()
    else:
        run_annotations()


if __name__ == "__main__":
    main()
