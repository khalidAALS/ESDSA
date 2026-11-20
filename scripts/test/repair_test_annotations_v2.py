

"""Repair only two flagged ESDSA TEST evidence annotations.

Uses unchanged validation v2 annotation instructions and schema.
Does not alter candidate responses, existing accepted annotations,
semantic groups, locked predictions, or frozen ESDSA policy.
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
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

import run_validation_annotation_pilot_v1 as pilot
import run_validation_annotations_v2 as annotation_v2

ROOT = Path("results/test_ai_annotations_v2")
TEMPLATE = ROOT / "test_evidence_template_v2.csv"
EVIDENCE = ROOT / "evidence"
FLAGS = ROOT / "review_required"
RESOLVED = ROOT / "resolved_review_flags"

TARGETS = (
    "TR-C574732B12EAA1D2",
    "TR-8C1304D89DCF3582",
)

MODEL = "gpt-5.4-mini"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    require(
        os.getenv("OPENAI_API_KEY"),
        "OPENAI_API_KEY is missing",
    )

    with TEMPLATE.open(
        encoding="utf-8-sig", newline=""
    ) as f:
        rows = list(csv.DictReader(f))

    lookup = {
        row["blinded_response_id"]: row
        for row in rows
    }

    require(
        len(rows) == 216 and len(lookup) == 216,
        "Unexpected evidence template dimensions",
    )

    client = OpenAI(timeout=120, max_retries=0)

    print("ESDSA — TARGETED TEST ANNOTATION REPAIR")
    print("=" * 65)
    print("Target annotations: 2")
    print("Original v2 annotation instructions: UNCHANGED")
    print("Existing accepted annotations: PRESERVED")
    print("Semantic annotations: UNCHANGED")
    print("Locked predictions: UNCHANGED")
    print()

    for rid in TARGETS:
        require(
            rid in lookup,
            f"Unknown blinded response: {rid}",
        )

        row = lookup[rid]
        output = EVIDENCE / f"{rid}.json"
        flag = FLAGS / f"{rid}.json"

        if output.exists():
            saved = json.loads(
                output.read_text(encoding="utf-8")
            )

            pilot.validate_evidence(
                row, saved["annotation"]
            )

            print("ALREADY COMPLETE:", rid)
            continue

        require(
            flag.exists(),
            f"Expected unresolved review flag: {rid}",
        )

        flag_data = json.loads(
            flag.read_text(encoding="utf-8")
        )

        require(
            flag_data["status"]
            == "MANUAL_REVIEW_REQUIRED",
            f"Unexpected review status: {rid}",
        )

        payload = pilot.evidence_payload(row)

        print("Repairing:", rid, flush=True)

        successful = False

        for attempt in range(1, 4):
            print(
                f"  Attempt {attempt}/3",
                flush=True,
            )

            response, result = pilot.call_model(
                client,
                annotation_v2.EVIDENCE_INSTRUCTIONS_V2,
                payload,
                pilot.EVIDENCE_SCHEMA,
                "esdsa_evidence_annotation_v2",
            )

            try:
                pilot.validate_evidence(row, result)

            except (SystemExit, ValueError, AssertionError) as exc:
                print(
                    f"  Validation failed: {exc}",
                    flush=True,
                )
                continue

            require(
                response.status == "completed",
                "Incomplete annotation response",
            )

            record = {
                "experiment": "ESDSA_TEST_AI_ANNOTATION_V2",
                "partition": "TEST",
                "review_type": "EVIDENCE",
                "blinded_id": rid,
                "reviewer_id": "AI_ASSISTED_GPT54_MINI_V2",
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

            EVIDENCE.mkdir(
                parents=True, exist_ok=True
            )

            with output.open(
                "x", encoding="utf-8"
            ) as f:
                json.dump(
                    record,
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
                f.write("\n")

            RESOLVED.mkdir(
                parents=True, exist_ok=True
            )

            archived = RESOLVED / flag.name

            require(
                not archived.exists(),
                "Resolved flag archive already exists",
            )

            flag.rename(archived)

            print(
                "  PASSED — original validator accepted annotation",
                flush=True,
            )

            successful = True
            break

        require(
            successful,
            f"Annotation still unresolved: {rid}",
        )

    completed = sum(
        (EVIDENCE / f"{r['blinded_response_id']}.json").exists()
        for r in rows
    )

    semantic_count = len(
        list((ROOT / "semantic").glob("TG-*.json"))
    )

    remaining_flags = len(
        list(FLAGS.glob("TR-*.json"))
    )

    print()
    print("=" * 65)
    print("TARGETED REPAIR SUMMARY")
    print(f"Evidence annotations: {completed}/216")
    print(f"Indicator assessments: {completed * 3}/648")
    print(f"Semantic groups: {semantic_count}/72")
    print("Unresolved evidence flags:", remaining_flags)
    print("Predictions: NOT MODIFIED")
    print("Frozen policy: NOT MODIFIED")

    require(
        completed == 216
        and semantic_count == 72
        and remaining_flags == 0,
        "TEST annotations are not fully resolved",
    )

    print("TEST ANNOTATION REPAIR: COMPLETE")


if __name__ == "__main__":
    main()
