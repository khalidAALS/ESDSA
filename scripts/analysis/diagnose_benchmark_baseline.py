
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path("data/benchmark")
INPUT = DATA / "development_responses_v1.csv"
RESULTS = Path("results/benchmark_evidence_aware_v1.jsonl")
OUTPUT = Path("results/benchmark_baseline_diagnostic_v1.txt")

if OUTPUT.exists():
    raise SystemExit("Diagnostic already exists; nothing overwritten.")

with INPUT.open(newline="", encoding="utf-8") as f:
    responses = {
        r["response_id"]: r
        for r in csv.DictReader(f)
    }

with RESULTS.open(encoding="utf-8") as f:
    records = [
        json.loads(line)
        for line in f if line.strip()
    ]

if len(responses) != 108 or len(records) != 108:
    raise ValueError("Expected 108 inputs and evaluations")

evaluations = {}

for record in records:
    rid = record["response_id"]
    if rid in evaluations:
        raise ValueError(f"Duplicate evaluation: {rid}")
    evaluations[rid] = record

if set(evaluations) != set(responses):
    raise ValueError("Response/evaluation mismatch")

conditions = defaultdict(Counter)
warning_types = Counter()

for rid, record in evaluations.items():
    condition = rid.rsplit("-", 1)[-1][:2]
    conditions[condition][record["decision"]] += 1

    for warning in record.get("validation_warnings", []):
        warning_types[warning.get("issue", "UNKNOWN")] += 1

lines = []

def add(value=""):
    lines.append(str(value))

add("ESDSA — BENCHMARK BASELINE DIAGNOSTIC")
add("=" * 72)

for condition in ("E1", "E2", "E3"):
    add(f"{condition}: {dict(conditions[condition])}")

add()
add("EXCERPT WARNING TYPES")
add(dict(warning_types))

selected = sorted(
    rid for rid in responses
    if rid.endswith("-E2L1")
)

selected += [
    "ESDSA-CSS02-02-E2L2",
    "ESDSA-SWE03-01-E3L1"
]

assert len(selected) == 14

for rid in selected:
    row = responses[rid]
    record = evaluations[rid]

    add()
    add("=" * 72)
    add(f"RESPONSE: {rid}")
    add(f"COMPETENCY: {row['competency_code']}")
    add(f"DECISION: {record['decision']}")
    add()
    add("QUESTION:")
    add(row["question"])
    add()
    add("ANSWER:")
    add(row["answer"])
    add()
    add("CRITERION ASSESSMENTS:")

    for criterion in record["parsed_output"]["criteria"]:
        add(
            f"{criterion['criterion_id']}: "
            f"{criterion['evidence_status']}"
        )
        add(
            f"  Explanation: "
            f"{criterion['explanation']}"
        )

    add(
        "Validation warnings: "
        f"{record.get('validation_warnings', [])}"
    )

OUTPUT.write_text(
    "\n".join(lines) + "\n",
    encoding="utf-8"
)

print("\nESDSA — BASELINE DIAGNOSTIC")
print("=" * 55)
print("Responses verified:", len(responses))
print("Evaluations verified:", len(evaluations))

for condition in ("E1", "E2", "E3"):
    print(condition, dict(conditions[condition]))

print("\nWarning types:", dict(warning_types))
print("Detailed cases exported:", len(selected))
print("Saved:", OUTPUT)
print("No API calls made.")
print("Original results unchanged.")
