
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

INPUT = Path("data/model_inputs/challenge_benchmark_v2.csv")
RESULTS = Path("results/audit_repeatability_f02_v1.jsonl")
OUTPUT = Path("results/audit_repeatability_f02_analysis.json")
DETAILS = Path("results/audit_repeatability_f02_details.csv")

if OUTPUT.exists() or DETAILS.exists():
    raise SystemExit("Analysis outputs exist; nothing overwritten.")

with INPUT.open(newline="", encoding="utf-8") as f:
    answers = {
        row["response_id"]: row["answer"]
        for row in csv.DictReader(f)
    }

with RESULTS.open(encoding="utf-8") as f:
    records = [
        json.loads(line)
        for line in f if line.strip()
    ]

targets = {"ESDSA-V2-0006", "ESDSA-V2-0007"}
assert len(records) == 20
assert {r["response_id"] for r in records} == targets

seen = set()
details = []
by_response = defaultdict(list)

for record in records:
    response_id = record["response_id"]
    repetition = record["repetition"]
    key = (response_id, repetition)

    if key in seen:
        raise ValueError(f"Duplicate: {key}")
    seen.add(key)

    answer = answers[response_id]
    actual_hash = hashlib.sha256(
        answer.encode("utf-8")
    ).hexdigest()

    if record["candidate_answer_sha256"] != actual_hash:
        raise ValueError(f"Answer changed: {response_id}")

    statuses = {
        c["criterion_id"]: c["evidence_status"]
        for c in record["parsed_output"]["criteria"]
    }

    if len(statuses) != 4:
        raise ValueError(f"Invalid criteria: {key}")

    if statuses["C3"] != record["c3_evidence_status"]:
        raise ValueError(f"C3 mismatch: {key}")

    excerpt_counts = Counter()

    for criterion in record["parsed_output"]["criteria"]:
        excerpt = criterion["supporting_excerpt"]

        if not excerpt:
            excerpt_counts["EMPTY"] += 1
        elif excerpt in answer:
            excerpt_counts["EXACT"] += 1
        elif excerpt.strip().strip('"“”').strip() in answer:
            excerpt_counts["OUTER_QUOTES_ONLY"] += 1
        else:
            excerpt_counts["UNVERIFIABLE"] += 1

    entry = {
        "response_id": response_id,
        "repetition": repetition,
        "c3_status": statuses["C3"],
        "recommendation": record["evidence_supported_decision"],
        "exact_excerpts": excerpt_counts["EXACT"],
        "outer_quotes_only": excerpt_counts["OUTER_QUOTES_ONLY"],
        "empty_excerpts": excerpt_counts["EMPTY"],
        "unverifiable_excerpts": excerpt_counts["UNVERIFIABLE"],
        "returned_model": record["returned_model"]
    }

    details.append(entry)
    by_response[response_id].append(entry)

for response_id in targets:
    observed = {
        e["repetition"]
        for e in by_response[response_id]
    }
    if observed != set(range(1, 11)):
        raise ValueError(f"Missing repetitions: {response_id}")

summary = {}

print("\nESDSA — F02 REPEATABILITY ANALYSIS")
print("=" * 60)

for response_id in sorted(targets):
    group = by_response[response_id]

    c3 = Counter(e["c3_status"] for e in group)
    decisions = Counter(
        e["recommendation"] for e in group
    )

    n = len(group)
    agreeing_pairs = sum(
        count * (count - 1) // 2
        for count in decisions.values()
    )
    total_pairs = n * (n - 1) // 2
    disagreement_rate = 1 - agreeing_pairs / total_pairs

    summary[response_id] = {
        "runs": n,
        "c3_counts": dict(c3),
        "recommendation_counts": dict(decisions),
        "observed_pairwise_disagreement_rate":
            round(disagreement_rate, 4),
        "unverifiable_excerpts": sum(
            e["unverifiable_excerpts"] for e in group
        )
    }

    print(f"\n{response_id}")
    print("C3:", dict(c3))
    print("Recommendations:", dict(decisions))
    print(
        "Observed pairwise disagreement:",
        f"{disagreement_rate:.1%}"
    )
    print(
        "Unverifiable excerpts:",
        summary[response_id]["unverifiable_excerpts"]
    )

details.sort(
    key=lambda r: (r["response_id"], r["repetition"])
)

with DETAILS.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f, fieldnames=list(details[0].keys())
    )
    writer.writeheader()
    writer.writerows(details)

report = {
    "experiment": "F02_AUDIT_REPEATABILITY_V1",
    "analysis_type": "EXPLORATORY",
    "independent_semantic_validation": "PENDING",
    "sample_size_per_response": 10,
    "results": summary,
    "limitations": [
        "Only two researcher-authored responses",
        "Repeated API calls may not be independent",
        "No inference about population-level wording effects",
        "No independently validated reference judgments"
    ]
}

OUTPUT.write_text(
    json.dumps(report, indent=2),
    encoding="utf-8"
)

print("\nSaved:", OUTPUT)
print("Run details:", DETAILS)
print("Original model outputs unchanged.")
