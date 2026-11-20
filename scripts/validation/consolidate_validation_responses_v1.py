
# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

from pathlib import Path
import csv
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[2]

BATCH_DIR = ROOT / "results/validation_generation_batches_v1"
PLAN_FILE = ROOT / "data/benchmark/validation_generation_plan_v1.json"
REGISTRY_FILE = ROOT / "data/benchmark/scenario_registry_v2.csv"

OUTPUT_DIR = ROOT / "results/validation_consolidated_v1"
OUTPUT_CSV = OUTPUT_DIR / "validation_responses_v1.csv"
OUTPUT_MANIFEST = OUTPUT_DIR / "validation_integrity_manifest_v1.json"

EXPECTED_FAMILIES = 24
EXPECTED_RESPONSES = 216
EXPECTED_MODEL = "gpt-5.4-mini-2026-03-17"

CONDITIONS = ("SUFFICIENT", "INSUFFICIENT", "NEGATIVE")
VARIANTS = ("CANONICAL", "CONVERSATIONAL", "CONCISE")

EXPECTED_PAIRS = {
    (condition, variant)
    for condition in CONDITIONS
    for variant in VARIANTS
}


def fail(message):
    print(f"FAIL: {message}")
    sys.exit(1)


def sha256_bytes(content):
    return hashlib.sha256(content).hexdigest()


def load_json(path):
    if not path.is_file():
        fail(f"Required file missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Cannot read {path}: {exc}")


def get_registry_ids():
    if not REGISTRY_FILE.is_file():
        fail(f"Registry missing: {REGISTRY_FILE}")

    with REGISTRY_FILE.open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []

        partition_col = next(
            (x for x in fields if x.lower() == "partition"),
            None
        )
        id_col = next(
            (
                x for x in fields
                if x.lower() in (
                    "family_id", "scenario_id", "scenario_family_id"
                )
            ),
            None
        )

        if not partition_col or not id_col:
            fail(
                "Registry columns not recognised. "
                f"Available columns: {fields}"
            )

        ids = [
            row[id_col].strip()
            for row in reader
            if row[partition_col].strip().upper() == "VALIDATION"
        ]

    if len(ids) != EXPECTED_FAMILIES:
        fail(
            "Expected 24 VALIDATION registry rows; "
            f"found {len(ids)}"
        )

    if len(set(ids)) != EXPECTED_FAMILIES:
        fail("Duplicate family IDs in VALIDATION registry")

    return set(ids)


def main():
    print("ESDSA VALIDATION — DATASET CONSOLIDATION")
    print("=" * 65)
    print("Read-only input verification")
    print("API requests: 0")
    print("Development files: NOT MODIFIED")
    print("TEST partition: NOT ACCESSED")
    print()

    plan = load_json(PLAN_FILE)
    registry_ids = get_registry_ids()

    if not isinstance(plan, dict):
        fail("Generation plan must be a JSON object")


    plan_text = json.dumps(plan, ensure_ascii=False)
    plan_ids = set(
        re.findall(r"ESDSA-(?:SWE|CSS|OPS)\d{2}-\d{2}", plan_text)
    )

    if plan_ids != registry_ids:
        fail(
            "Generation-plan family IDs differ from registry. "
            f"Missing from plan: {sorted(registry_ids - plan_ids)}; "
            f"unexpected in plan: {sorted(plan_ids - registry_ids)}"
        )

    if not BATCH_DIR.is_dir():
        fail(f"Generation batch directory missing: {BATCH_DIR}")

    batch_files = sorted(BATCH_DIR.glob("ESDSA-*.json"))

    if len(batch_files) != EXPECTED_FAMILIES:
        fail(
            f"Expected 24 batch JSON files; found {len(batch_files)}"
        )

    all_records = []
    family_ids = set()
    batch_manifest = []

    for path in batch_files:
        batch = load_json(path)

        family_id = batch.get("family_id")
        if not isinstance(family_id, str):
            fail(f"Missing family_id in {path.name}")

        if family_id in family_ids:
            fail(f"Duplicate family: {family_id}")

        if family_id not in registry_ids:
            fail(f"Unregistered VALIDATION family: {family_id}")

        if path.name != f"{family_id}.json":
            fail(f"Filename/family mismatch: {path.name}")

        if batch.get("partition") != "VALIDATION":
            fail(f"Incorrect partition: {family_id}")

        if batch.get("validation_status") != "STRUCTURE_PASSED":
            fail(f"Structural validation not passed: {family_id}")

        if batch.get("response_status") != "completed":
            fail(f"Generation response incomplete: {family_id}")

        if batch.get("returned_model") != EXPECTED_MODEL:
            fail(f"Model mismatch: {family_id}")

        if batch.get("requested_model") != "gpt-5.4-mini":
            fail(f"Requested model mismatch: {family_id}")

        run_sha = batch.get("run_sha256")
        if not (
            isinstance(run_sha, str)
            and re.fullmatch(r"[0-9a-f]{64}", run_sha)
        ):
            fail(f"Invalid run fingerprint: {family_id}")

        responses = batch.get("responses")
        if not isinstance(responses, list) or len(responses) != 9:
            fail(f"Expected nine responses: {family_id}")

        raw_text = batch.get("raw_output_text")
        if not isinstance(raw_text, str):
            fail(f"Missing original raw output: {family_id}")

        try:
            raw_parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            fail(f"Original raw output is not valid JSON: {family_id}")

        if raw_parsed != {"responses": responses}:
            fail(
                "Saved responses do not exactly match "
                f"original raw output: {family_id}"
            )

        seen_pairs = set()

        for response in responses:
            if not isinstance(response, dict):
                fail(f"Invalid response object: {family_id}")

            pair = (
                response.get("condition"),
                response.get("variant")
            )

            if pair not in EXPECTED_PAIRS:
                fail(f"Unexpected condition/variant: {family_id}, {pair}")

            if pair in seen_pairs:
                fail(f"Duplicate condition/variant: {family_id}, {pair}")

            seen_pairs.add(pair)

            answer = response.get("answer")

            if not isinstance(answer, str) or not answer.strip():
                fail(f"Empty or invalid answer: {family_id}, {pair}")

            condition, variant = pair

            all_records.append({
                "response_id": f"{family_id}__{condition}__{variant}",
                "family_id": family_id,
                "partition": "VALIDATION",
                "generation_condition": condition,
                "variant": variant,
                "answer": answer,
                "answer_sha256": sha256_bytes(
                    answer.encode("utf-8")
                ),
                "returned_model": batch["returned_model"],
                "run_sha256": run_sha,
            })

        if seen_pairs != EXPECTED_PAIRS:
            fail(f"Missing condition/variant combinations: {family_id}")

        family_ids.add(family_id)

        batch_manifest.append({
            "family_id": family_id,
            "file": str(path.relative_to(ROOT)),
            "file_sha256": sha256_bytes(path.read_bytes()),
            "run_sha256": run_sha,
            "response_count": len(responses),
        })

        print(f"PASS: {family_id} | 9 responses")

    if family_ids != registry_ids:
        fail(
            "Completed families differ from registry. "
            f"Missing: {sorted(registry_ids - family_ids)}"
        )

    if len(all_records) != EXPECTED_RESPONSES:
        fail(
            f"Expected 216 responses; found {len(all_records)}"
        )

    response_ids = [row["response_id"] for row in all_records]

    if len(set(response_ids)) != EXPECTED_RESPONSES:
        fail("Duplicate response IDs")


    condition_order = {
        value: index for index, value in enumerate(CONDITIONS)
    }
    variant_order = {
        value: index for index, value in enumerate(VARIANTS)
    }

    all_records.sort(key=lambda row: (
        row["family_id"],
        condition_order[row["generation_condition"]],
        variant_order[row["variant"]],
    ))

    manifest = {
        "experiment": "ESDSA_VALIDATION_CONSOLIDATION_V1",
        "partition": "VALIDATION",
        "status": "PASSED",
        "family_count": len(family_ids),
        "response_count": len(all_records),
        "conditions": list(CONDITIONS),
        "variants": list(VARIANTS),
        "returned_model": EXPECTED_MODEL,
        "generation_plan_sha256": sha256_bytes(
            PLAN_FILE.read_bytes()
        ),
        "registry_sha256": sha256_bytes(
            REGISTRY_FILE.read_bytes()
        ),
        "checks": {
            "registry_plan_family_ids_match": True,
            "exactly_24_batch_files": True,
            "exactly_216_responses": True,
            "unique_response_ids": True,
            "nine_condition_variant_pairs_per_family": True,
            "raw_output_matches_saved_responses": True,
            "returned_model_consistent": True,
            "structural_status_passed": True,
            "validation_partition_only": True,
        },
        "limitations": [
            "Run fingerprints checked for presence and format, "
            "not independently recomputed from the generator payload.",
            "Reference decisions have not been adjudicated.",
            "Semantic equivalence has not been adjudicated.",
            "No evaluator or TEST partition was accessed.",
        ],
        "batches": batch_manifest,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    columns = [
        "response_id",
        "family_id",
        "partition",
        "generation_condition",
        "variant",
        "answer",
        "answer_sha256",
        "returned_model",
        "run_sha256",
    ]

    with OUTPUT_CSV.open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(all_records)

    manifest["output_csv_sha256"] = sha256_bytes(
        OUTPUT_CSV.read_bytes()
    )

    OUTPUT_MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 65)
    print("VALIDATION CONSOLIDATION: PASSED")
    print(f"Families: {len(family_ids)} / 24")
    print(f"Responses: {len(all_records)} / 216")
    print(f"Model: {EXPECTED_MODEL}")
    print(f"Dataset: {OUTPUT_CSV.relative_to(ROOT)}")
    print(f"Manifest: {OUTPUT_MANIFEST.relative_to(ROOT)}")
    print("No reference labels inferred.")
    print("No evaluator run.")
    print("TEST partition: NOT ACCESSED")


if __name__ == "__main__":
    main()
