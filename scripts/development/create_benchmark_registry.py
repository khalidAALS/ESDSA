
import csv
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path("data/benchmark")
REGISTRY = ROOT / "scenario_registry_v1.csv"
SPECIFICATION = ROOT / "benchmark_specification_v1.json"

if REGISTRY.exists() or SPECIFICATION.exists():
    raise SystemExit(
        "Benchmark registry already exists. "
        "No files overwritten."
    )

SEED = 20261119
FAMILIES_PER_COMPETENCY = 10

ROLES = {
    "SWE": {
        "name": "Software Developer",
        "competencies": {
            "SWE01": "Systematic diagnosis",
            "SWE02": "Technical investigation",
            "SWE03": "Reasoned correction",
            "SWE04": "Verification and testing",
        }
    },
    "CSS": {
        "name": "Customer Support Specialist",
        "competencies": {
            "CSS01": "Problem identification",
            "CSS02": "Information gathering",
            "CSS03": "Resolution judgment",
            "CSS04": "Communication and follow-up",
        }
    },
    "OPS": {
        "name": "Operations Coordinator",
        "competencies": {
            "OPS01": "Prioritisation",
            "OPS02": "Risk identification",
            "OPS03": "Evidence-based coordination",
            "OPS04": "Monitoring and escalation",
        }
    }
}

EVIDENCE_CONDITIONS = [
    "SUFFICIENT",
    "INSUFFICIENT",
    "NEGATIVE"
]

LINGUISTIC_VARIANTS = [
    "CANONICAL",
    "CONVERSATIONAL",
    "CONCISE"
]

SCENARIO_PROFILES = [
    "Routine operational problem",
    "Time-sensitive problem",
    "Incomplete contextual information",
    "Conflicting information",
    "Multiple competing priorities",
    "Uncertain cause or outcome",
    "Stakeholder disagreement",
    "Unexpected complication",
    "High-consequence decision",
    "Recovery after an unsuccessful attempt"
]

records = []

for role_code, role in ROLES.items():
    for competency_code, competency in (
        role["competencies"].items()
    ):
        indices = list(
            range(1, FAMILIES_PER_COMPETENCY + 1)
        )

        rng = random.Random(
            SEED + sum(
                ord(char) for char in competency_code
            )
        )
        rng.shuffle(indices)


        partitions = {
            index: (
                "DEVELOPMENT" if pos < 6
                else "VALIDATION" if pos < 8
                else "TEST"
            )
            for pos, index in enumerate(indices)
        }

        for scenario_index in range(
            1, FAMILIES_PER_COMPETENCY + 1
        ):
            family_id = (
                f"ESDSA-{competency_code}-"
                f"{scenario_index:02d}"
            )

            records.append({
                "family_id": family_id,
                "role_code": role_code,
                "role_name": role["name"],
                "competency_code": competency_code,
                "competency_name": competency,
                "scenario_index": scenario_index,
                "scenario_profile": (
                    SCENARIO_PROFILES[
                        scenario_index - 1
                    ]
                ),
                "partition": partitions[
                    scenario_index
                ],
                "scenario_question": "",
                "scenario_context": "",
                "rubric_version": "PENDING",
                "reference_validation": "PENDING",
                "semantic_validation": "PENDING",
                "construction_status": "NOT_STARTED"
            })

assert len(records) == 120
assert len({
    record["family_id"] for record in records
}) == 120

counts = Counter(
    row["partition"] for row in records
)

assert counts == {
    "DEVELOPMENT": 72,
    "VALIDATION": 24,
    "TEST": 24
}

ROOT.mkdir(parents=True, exist_ok=True)

with REGISTRY.open(
    "w", newline="", encoding="utf-8"
) as f:
    writer = csv.DictWriter(
        f, fieldnames=list(records[0].keys())
    )
    writer.writeheader()
    writer.writerows(records)

registry_hash = hashlib.sha256(
    REGISTRY.read_bytes()
).hexdigest()

specification = {
    "benchmark_name": "ESDSA Interview Benchmark",
    "version": "1.0-development-registry",
    "random_seed": SEED,
    "registry_sha256": registry_hash,
    "roles": ROLES,
    "families_per_competency": 10,
    "scenario_profiles": SCENARIO_PROFILES,
    "evidence_conditions": EVIDENCE_CONDITIONS,
    "linguistic_variants": LINGUISTIC_VARIANTS,
    "target_scenario_families": 120,
    "target_response_texts": (
        120
        * len(EVIDENCE_CONDITIONS)
        * len(LINGUISTIC_VARIANTS)
    ),
    "family_partitions": dict(counts),
    "responses_by_partition": {
        partition: count * 9
        for partition, count in counts.items()
    },
    "partition_rule": (
        "Stratified 60/20/20 family-level split "
        "within each role-competency combination."
    ),
    "test_set_policy": (
        "All variants from the same scenario family "
        "must remain in one partition. The TEST "
        "partition must not be used for model "
        "selection, prompt modification, threshold "
        "selection or error-driven revisions."
    ),
    "scenario_status": "NOT_GENERATED",
    "rubric_status": "PENDING",
    "reference_status": "PROVISIONAL",
    "independent_validation": "PENDING",
    "important_limitations": [
        "Scenario profiles are planning categories, "
        "not completed interview questions.",
        "Evidence conditions are experimental categories, "
        "not automatically verified hiring labels.",
        "Linguistic equivalence must be checked.",
        "Job-specific rubrics require independent review.",
        "The response variants within a family are "
        "correlated observations, not independent cases."
    ]
}

SPECIFICATION.write_text(
    json.dumps(
        specification,
        indent=2,
        ensure_ascii=False
    ),
    encoding="utf-8"
)

print("\nESDSA — BENCHMARK REGISTRY V1")
print("=" * 60)

print("Roles:", len(ROLES))
print("Competencies:", sum(
    len(role["competencies"])
    for role in ROLES.values()
))
print("Scenario families:", len(records))
print("Evidence conditions per family:", 3)
print("Linguistic variants per condition:", 3)
print("Target response texts:", 1080)

print("\nFamily-level partitions:")

for partition in (
    "DEVELOPMENT",
    "VALIDATION",
    "TEST"
):
    print(
        f"{partition}: "
        f"{counts[partition]} families, "
        f"{counts[partition] * 9} planned responses"
    )

print("\nRegistry SHA256:", registry_hash)
print("Registry:", REGISTRY)
print("Specification:", SPECIFICATION)
print("\nNo interview responses generated.")
print("No reference labels validated.")
print("No API calls made.")
print("Existing experiments unchanged.")
