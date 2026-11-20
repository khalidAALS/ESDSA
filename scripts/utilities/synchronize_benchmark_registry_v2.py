

"""Reconcile completed development families with the benchmark registry.

Creates versioned outputs. Never modifies the original registry.
No API calls.
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
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data" / "benchmark"

REGISTRY = BASE / "scenario_registry_v1.csv"
RESPONSES = BASE / "development_responses_v1.csv"

OUTPUT = BASE / "scenario_registry_v2.csv"
REPORT = BASE / "scenario_registry_reconciliation_v2.json"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError(
            "Version 2 output already exists. "
            "Original outputs will not be overwritten."
        )

    registry, columns = read_csv(REGISTRY)
    responses, _ = read_csv(RESPONSES)

    if len(registry) != 120:
        raise ValueError("Expected 120 registry families")

    if len(responses) != 108:
        raise ValueError("Expected 108 development responses")

    required = {
        "family_id",
        "partition",
        "scenario_question",
        "construction_status",
    }

    if not required.issubset(columns):
        raise ValueError("Registry lacks required columns")

    by_family = {}

    for row in registry:
        fid = row["family_id"]

        if fid in by_family:
            raise ValueError(f"Duplicate registry family: {fid}")

        by_family[fid] = row

    developed = defaultdict(list)

    for response in responses:
        rid = response["response_id"]
        parts = rid.split("-")

        if len(parts) != 4:
            raise ValueError(f"Unexpected response ID: {rid}")

        family_id = "-".join(parts[:3])
        developed[family_id].append(response)

    if len(developed) != 12:
        raise ValueError("Expected exactly 12 developed families")

    changes = []

    for fid, family_responses in sorted(developed.items()):
        if fid not in by_family:
            raise ValueError(f"Missing registry family: {fid}")

        entry = by_family[fid]

        if entry["partition"] != "DEVELOPMENT":
            raise ValueError(
                f"Held-out family already exposed: {fid}"
            )

        if len(family_responses) != 9:
            raise ValueError(
                f"{fid}: expected 9 responses, "
                f"found {len(family_responses)}"
            )

        ids = [
            r["response_id"] for r in family_responses
        ]

        if len(set(ids)) != 9:
            raise ValueError(f"Duplicate responses in {fid}")

        questions = {
            " ".join(r["question"].split())
            for r in family_responses
        }

        if len(questions) != 1:
            raise ValueError(
                f"Inconsistent interview questions: {fid}"
            )

        question = next(iter(questions))

        if (
            entry["scenario_question"].strip()
            and " ".join(
                entry["scenario_question"].split()
            ) != question
        ):
            raise ValueError(
                f"Registry question differs: {fid}"
            )

        previous_status = entry["construction_status"]

        if previous_status != "NOT_STARTED":
            raise ValueError(
                f"Unexpected existing status: {fid}: "
                f"{previous_status}"
            )

        entry["scenario_question"] = question
        entry["construction_status"] = (
            "DEVELOPMENT_EVALUATED"
        )

        changes.append({
            "family_id": fid,
            "response_count": 9,
            "previous_status": previous_status,
            "new_status": "DEVELOPMENT_EVALUATED",
        })

    partitions = Counter(
        row["partition"] for row in registry
    )

    statuses = Counter(
        row["construction_status"] for row in registry
    )

    expected_partitions = {
        "DEVELOPMENT": 72,
        "VALIDATION": 24,
        "TEST": 24,
    }

    if dict(partitions) != expected_partitions:
        raise ValueError(
            f"Unexpected partitions: {dict(partitions)}"
        )

    if statuses["DEVELOPMENT_EVALUATED"] != 12:
        raise ValueError("Incorrect completed-family count")

    with OUTPUT.open(
        "w", encoding="utf-8", newline=""
    ) as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(registry)

    report = {
        "version": "2.0-registry-reconciliation",
        "date": str(date.today()),
        "original_registry_sha256": sha256(REGISTRY),
        "development_responses_sha256": sha256(RESPONSES),
        "updated_registry_sha256": sha256(OUTPUT),
        "total_families": len(registry),
        "partition_counts": dict(partitions),
        "construction_status_counts": dict(statuses),
        "reconciled_families": changes,
        "held_out_families_modified": 0,
        "reference_labels_modified": False,
        "model_evaluations_performed": False,
        "notes": [
            "The original registry remains unchanged.",
            "Only existing development-family questions "
            "and construction statuses were updated.",
            "Validation and test families remain untouched.",
            "Development reference judgments remain provisional.",
            "Registry synchronization is not independent validation.",
        ],
    }

    REPORT.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("BENCHMARK REGISTRY RECONCILIATION")
    print("=" * 60)
    print("Total families:", len(registry))
    print("Partition counts:", dict(partitions))
    print("Construction statuses:", dict(statuses))
    print("Development families reconciled:", len(changes))
    print("Validation/test families modified: 0")
    print("Original registry preserved: YES")
    print("Reference labels modified: NO")
    print("API calls: NONE")
    print()
    print("Saved:", OUTPUT)
    print("Saved:", REPORT)


if __name__ == "__main__":
    main()
