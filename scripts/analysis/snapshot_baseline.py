
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(".")
snapshot_dir = root / "results" / "snapshots"
snapshot_dir.mkdir(parents=True, exist_ok=True)

manifest_path = snapshot_dir / "development_pilot_v1_manifest.json"

if manifest_path.exists():
    raise SystemExit(
        f"Snapshot already exists: {manifest_path}"
    )

paths = [
    Path("results/pilot_gpt-5.4-mini.jsonl"),
    Path("data/model_inputs/evaluation_pilot_v1.csv"),
    Path("data/model_inputs/evaluation_prompts_v1.jsonl"),
    Path("data/reference/evaluation_pilot_v1_reference.csv"),
    Path("data/rubrics/SW-DEFECT-V1.json")
]

def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()

for path in paths:
    if not path.exists():
        raise FileNotFoundError(path)

with paths[0].open(encoding="utf-8") as f:
    results = [
        json.loads(line)
        for line in f if line.strip()
    ]

if len(results) != 12:
    raise ValueError("Expected exactly 12 results")

if len({r["response_id"] for r in results}) != 12:
    raise ValueError("Duplicate response IDs")

models = sorted({
    r["returned_model"]
    for r in results
})

manifest = {
    "experiment": "ESDSA development pilot",
    "version": "1.0",
    "created_utc": datetime.now(
        timezone.utc
    ).isoformat(),
    "evaluation_count": len(results),
    "models": models,
    "reference_status": "PROVISIONAL",
    "reported_reference_agreement": "12/12",
    "limitations": [
        "Synthetic development responses",
        "Reference decisions not independently validated",
        "Evaluator received explicit deferral rules",
        "One failed API generation was not preserved",
        "First six saved records lack excerpt-warning metadata",
        "No ESDSA audit evaluated"
    ],
    "files": {
        str(path): sha256(path)
        for path in paths
    }
}

manifest_path.write_text(
    json.dumps(manifest, indent=2),
    encoding="utf-8"
)

print(f"Created: {manifest_path}")
print(f"Evaluations: {len(results)}")
print(f"Models: {models}")
print(f"Files fingerprinted: {len(paths)}")
print("Existing results unchanged.")
