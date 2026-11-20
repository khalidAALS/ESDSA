

"""Audit existing ESDSA evaluation files and benchmark coverage.

Read-only audit. No API calls or source-file modifications.
"""

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(".")
RESULTS = ROOT / "results"
BENCHMARK = ROOT / "data" / "benchmark"

REFERENCE = (
    BENCHMARK
    / "researcher_annotations_v1"
    / "development_reference_provisional_v1.csv"
)

MAPPING = (
    BENCHMARK
    / "content_review_v1"
    / "private_review_mapping.json"
)

REPORT = RESULTS / "baseline_inventory_v1.json"

IDENTIFIER_FIELDS = (
    "response_id",
    "candidate_response_id",
    "benchmark_response_id",
    "id",
)

VALID_DECISIONS = {
    "ADVANCE",
    "DEFER",
    "DO_NOT_ADVANCE",
}


def read_csv(path):
    with path.open(
        newline="", encoding="utf-8-sig"
    ) as f:
        return list(csv.DictReader(f))


def read_records(path):
    if path.suffix.lower() == ".csv":
        return read_csv(path)

    if path.suffix.lower() == ".jsonl":
        with path.open(encoding="utf-8") as f:
            return [
                json.loads(line)
                for line in f
                if line.strip()
            ]

    if path.suffix.lower() == ".json":
        with path.open(encoding="utf-8") as f:
            obj = json.load(f)

        if isinstance(obj, list):
            return obj

        if isinstance(obj, dict):
            for key in (
                "records",
                "evaluations",
                "results",
                "predictions",
                "responses",
            ):
                value = obj.get(key)
                if isinstance(value, list):
                    return value

            return [obj]

    return []


def get_id(record):
    if not isinstance(record, dict):
        return None

    for field in IDENTIFIER_FIELDS:
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def get_decision(record):
    if not isinstance(record, dict):
        return None

    for field in (
        "decision",
        "final_decision",
        "recommendation",
        "prediction",
    ):
        value = record.get(field)

        if isinstance(value, str):
            normalized = value.strip().upper()

            if normalized in VALID_DECISIONS:
                return normalized

    return None


if not REFERENCE.exists():
    raise SystemExit(f"Missing reference: {REFERENCE}")

if not MAPPING.exists():
    raise SystemExit(f"Missing mapping: {MAPPING}")

if not RESULTS.is_dir():
    raise SystemExit(f"Missing results folder: {RESULTS}")

if REPORT.exists():
    raise SystemExit(
        f"Report already exists: {REPORT}\n"
        "No files overwritten."
    )


reference_rows = read_csv(REFERENCE)

mapping = json.loads(
    MAPPING.read_text(encoding="utf-8")
)["groups"]

expected_ids = set()

for row in reference_rows:
    group = row["review_group"]
    letter = row["response_label"]

    response_id = (
        mapping[group]["responses"][letter]["response_id"]
    )

    expected_ids.add(response_id)

if len(expected_ids) != 108:
    raise SystemExit(
        f"Expected 108 unique IDs, found {len(expected_ids)}"
    )


inventory = []

supported_extensions = {".json", ".jsonl", ".csv"}

for path in sorted(RESULTS.rglob("*")):
    if not path.is_file():
        continue

    if path.suffix.lower() not in supported_extensions:
        continue

    try:
        records = read_records(path)
    except (OSError, ValueError, csv.Error) as exc:
        inventory.append({
            "file": str(path),
            "error": str(exc),
        })
        continue

    ids = [
        get_id(record)
        for record in records
    ]

    found_ids = {
        value for value in ids
        if value is not None
    }

    overlap = found_ids & expected_ids

    decisions = Counter(
        decision
        for record in records
        if (decision := get_decision(record)) is not None
    )

    sample_keys = []

    if records and isinstance(records[0], dict):
        sample_keys = sorted(records[0].keys())

    inventory.append({
        "file": str(path),
        "records": len(records),
        "unique_ids": len(found_ids),
        "matching_benchmark_ids": len(overlap),
        "missing_benchmark_ids": len(
            expected_ids - overlap
        ),
        "decisions": dict(decisions),
        "sample_keys": sample_keys[:30],
        "complete_id_coverage": (
            len(overlap) == len(expected_ids)
        ),
    })


report = {
    "benchmark_responses": len(expected_ids),
    "reference_status": (
        "AI-assisted provisional, not independently validated"
    ),
    "files_examined": len(inventory),
    "inventory": inventory,
    "note": (
        "Identifier coverage alone does not establish "
        "baseline validity or comparability. "
        "Prompt, model, decision rules and coverage "
        "must be checked separately."
    ),
}

REPORT.write_text(
    json.dumps(report, indent=2, ensure_ascii=False)
    + "\n",
    encoding="utf-8",
)


print("ESDSA — BASELINE COVERAGE AUDIT")
print("=" * 68)

print("Benchmark responses:", len(expected_ids))
print("Result files examined:", len(inventory))

print("\nFILES WITH MATCHING BENCHMARK IDENTIFIERS")
print("-" * 68)

matching_files = [
    item for item in inventory
    if item.get("matching_benchmark_ids", 0) > 0
]

if not matching_files:
    print("None found.")

for item in matching_files:
    print("\nFile:", item["file"])
    print("Records:", item["records"])
    print(
        "Benchmark coverage:",
        f"{item['matching_benchmark_ids']}/108"
    )
    print("Decisions:", item["decisions"])
    print("Fields:", ", ".join(item["sample_keys"]))


print("\nOTHER EVALUATION-RELATED FILES")
print("-" * 68)

keywords = (
    "baseline",
    "scoring",
    "evaluation",
    "benchmark",
    "stability",
    "repeatability",
    "gate",
)

for item in inventory:
    name = item["file"].lower()

    if (
        item.get("matching_benchmark_ids", 0) == 0
        and any(word in name for word in keywords)
    ):
        print(
            item["file"],
            "| Records:",
            item.get("records", "?"),
            "| Fields:",
            item.get("sample_keys", []),
        )


print("\nSUMMARY")
print("-" * 68)

complete = [
    item["file"]
    for item in matching_files
    if item["complete_id_coverage"]
]

print("Files covering all 108 IDs:", len(complete))

for name in complete:
    print(" ", name)

print("\nReport saved:", REPORT)
print("No API calls made.")
print("Original files unchanged.")
