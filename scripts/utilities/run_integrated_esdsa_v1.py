

"""Integrated ESDSA v1 — development experiment.

Combines:
1. Criterion-level evidence sufficiency.
2. Literal traceability of supporting excerpts.
3. Unanimous actionable decisions across three variants.

The decision policy does not use reference labels.
No API calls. Source files remain unchanged.
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
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

DATA = Path("data/benchmark/development_responses_v1.csv")
MAPPING = Path(
    "data/benchmark/content_review_v1/"
    "private_review_mapping.json"
)
EVALUATIONS = Path(
    "results/benchmark_evidence_aware_v1.jsonl"
)

REFERENCE = Path(
    "data/benchmark/researcher_annotations_v1/"
    "development_reference_provisional_v1.csv"
)

OUTPUT = Path("results/integrated_esdsa_v1.json")
SPECIFICATION = Path(
    "results/integrated_esdsa_policy_v1.json"
)

VALID = {
    "POSITIVE_EVIDENCE",
    "NEGATIVE_EVIDENCE",
    "INSUFFICIENT_EVIDENCE",
}

ACTIONABLE = {"ADVANCE", "DO_NOT_ADVANCE"}


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_jsonl(path):
    with path.open(encoding="utf-8") as f:
        return [
            json.loads(line)
            for line in f if line.strip()
        ]


def sha(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def normalise(text):
    text = unicodedata.normalize("NFKC", text)
    return " ".join(text.casefold().split())


def excerpt_is_verifiable(excerpt, answer):
    """Exact substring check with limited formatting normalisation.

    This verifies literal traceability only.
    It does not verify that an excerpt supports its classification.
    """
    if not isinstance(excerpt, str) or not excerpt.strip():
        return False

    candidate = normalise(answer)
    snippet = normalise(excerpt)

    if snippet in candidate:
        return True

    snippet = snippet.strip(
        ' \t\n\r"\'“”‘’«»'
    )

    return bool(snippet) and snippet in candidate


def evaluate_evidence(record, answer):
    criteria = record["parsed_output"]["criteria"]

    if len(criteria) != 3:
        raise ValueError("Expected exactly three criteria.")

    audit = []
    statuses = []
    traceability_problem = False

    for item in criteria:
        status = item["evidence_status"]

        if status not in VALID:
            raise ValueError(
                f"Unknown evidence status: {status}"
            )

        excerpt = item.get("supporting_excerpt", "")

        if status == "INSUFFICIENT_EVIDENCE":
            verified = None
        else:
            verified = excerpt_is_verifiable(
                excerpt, answer
            )

            if not verified:
                traceability_problem = True

        statuses.append(status)

        audit.append({
            "criterion_id": item["criterion_id"],
            "status": status,
            "excerpt": excerpt,
            "excerpt_verifiable": verified,
        })


    if traceability_problem:
        decision = "DEFER"
        reason = "UNVERIFIABLE_REQUIRED_EVIDENCE"

    elif "NEGATIVE_EVIDENCE" in statuses:
        decision = "DO_NOT_ADVANCE"
        reason = "VERIFIABLE_NEGATIVE_EVIDENCE"

    elif all(
        status == "POSITIVE_EVIDENCE"
        for status in statuses
    ):
        decision = "ADVANCE"
        reason = "ALL_CRITERIA_POSITIVE_AND_TRACEABLE"

    else:
        decision = "DEFER"
        reason = "INSUFFICIENT_COMPETENCY_EVIDENCE"

    return decision, reason, audit


def consensus_gate(items):
    """Return a single group decision, or defer on disagreement."""
    decisions = {
        item["pre_stability_decision"]
        for item in items
    }

    if len(decisions) == 1:
        value = next(iter(decisions))

        if value in ACTIONABLE:
            return value, "UNANIMOUS_ACTIONABLE"

    return "DEFER", "NO_UNANIMOUS_ACTIONABLE_DECISION"


for required in (DATA, MAPPING, EVALUATIONS, REFERENCE):
    if not required.is_file():
        raise SystemExit(f"Missing input: {required}")

if OUTPUT.exists() or SPECIFICATION.exists():
    raise SystemExit(
        "One or more outputs already exist. "
        "Nothing overwritten."
    )


policy = {
    "name": "INTEGRATED_ESDSA_V1",
    "stage": "DEVELOPMENT_PROTOTYPE",
    "source": "Previously completed evidence-aware evaluations",
    "criteria": 3,
    "evidence_rule": {
        "negative": "DO_NOT_ADVANCE",
        "all_positive": "ADVANCE",
        "otherwise": "DEFER",
    },
    "traceability_rule": (
        "POSITIVE and NEGATIVE classifications require "
        "a nonempty supporting excerpt found within the "
        "candidate answer after limited text normalisation. "
        "Any failed required excerpt forces DEFER."
    ),
    "stability_rule": (
        "The three generated variants must receive the "
        "same actionable pre-stability decision; "
        "otherwise defer the entire group."
    ),
    "reference_labels_used_in_policy": False,
    "important_limitations": [
        "Groups are assumed to represent alternative "
        "linguistic presentations, but semantic equivalence "
        "has not been independently established.",
        "Literal excerpt matching does not establish "
        "that the excerpt proves the classification.",
        "Three variants are not independent repeat evaluations "
        "of one unchanged interview answer.",
        "Policy was specified after inspecting development "
        "results and must be tested on held-out cases.",
        "This is not a deployable automated hiring system.",
    ],
}

responses = read_csv(DATA)
evaluations = read_jsonl(EVALUATIONS)
references = read_csv(REFERENCE)

mapping = json.loads(
    MAPPING.read_text(encoding="utf-8")
)["groups"]

if (
    len(responses) != 108
    or len(evaluations) != 108
    or len(references) != 108
):
    raise SystemExit("Expected 108 records per input.")

response_by_id = {
    item["response_id"]: item
    for item in responses
}

evaluation_by_id = {
    item["response_id"]: item
    for item in evaluations
}

if (
    len(response_by_id) != 108
    or len(evaluation_by_id) != 108
):
    raise SystemExit("Duplicate response IDs detected.")

groups = defaultdict(list)
group_by_id = {}

for group, info in mapping.items():
    for letter, details in info["responses"].items():
        rid = details["response_id"]

        if rid in group_by_id:
            raise SystemExit(
                f"Duplicate group mapping: {rid}"
            )

        group_by_id[rid] = (group, letter)

if set(group_by_id) != set(response_by_id):
    raise SystemExit("Group mapping does not cover dataset.")

if set(evaluation_by_id) != set(response_by_id):
    raise SystemExit("Evaluations do not match dataset IDs.")


for rid, response in response_by_id.items():
    evaluation = evaluation_by_id[rid]

    if evaluation.get("answer_sha256") != sha(
        response["answer"]
    ):
        raise SystemExit(
            f"Answer hash mismatch: {rid}"
        )

    if evaluation["rubric_id"] != response["rubric_id"]:
        raise SystemExit(
            f"Rubric mismatch: {rid}"
        )

    group, letter = group_by_id[rid]

    provisional, reason, audit = evaluate_evidence(
        evaluation, response["answer"]
    )

    groups[group].append({
        "response_id": rid,
        "group": group,
        "letter": letter,
        "baseline_evidence_decision": evaluation["decision"],
        "pre_stability_decision": provisional,
        "pre_stability_reason": reason,
        "criterion_audit": audit,
    })


if len(groups) != 36:
    raise SystemExit("Expected 36 groups.")

records = []

for group, items in sorted(groups.items()):
    if (
        len(items) != 3
        or {item["letter"] for item in items}
        != {"A", "B", "C"}
    ):
        raise SystemExit(
            f"Invalid linguistic group: {group}"
        )

    final_decision, gate_reason = consensus_gate(items)

    for item in items:
        item["esdsa_decision"] = final_decision
        item["stability_reason"] = gate_reason
        item["stability_changed_decision"] = (
            item["pre_stability_decision"]
            != final_decision
        )

        records.append(item)

records.sort(
    key=lambda item: (
        item["group"],
        item["letter"]
    )
)


reference_by_id = {}

for row in references:
    group = row["review_group"]
    letter = row["response_label"]

    rid = mapping[
        group
    ]["responses"][letter]["response_id"]

    reference_by_id[rid] = {
        "decision": row["reference_decision"],
        "flagged": row["review_flag"],
        "semantic_equivalence": row["semantic_equivalence"],
    }

if len(reference_by_id) != 108:
    raise SystemExit("Invalid reference mapping.")

for item in records:
    reference = reference_by_id[item["response_id"]]

    item["reference_decision"] = reference["decision"]
    item["reference_flagged"] = reference["flagged"]
    item["semantic_equivalence"] = (
        reference["semantic_equivalence"]
    )

    item["agrees_with_provisional_reference"] = (
        item["esdsa_decision"]
        == reference["decision"]
    )


def metrics(items, field):
    actionable = [
        item for item in items
        if item[field] in ACTIONABLE
    ]

    disagreements = sum(
        item[field] != item["reference_decision"]
        for item in actionable
    )

    unsupported_advances = sum(
        item[field] == "ADVANCE"
        and item["reference_decision"] != "ADVANCE"
        for item in actionable
    )

    return {
        "count": len(items),
        "decisions": dict(
            Counter(item[field] for item in items)
        ),
        "actionable": len(actionable),
        "coverage": len(actionable) / len(items),
        "provisional_reference_agreement": (
            sum(
                item[field] == item["reference_decision"]
                for item in items
            ) / len(items)
        ),
        "actionable_disagreements": disagreements,
        "actionable_disagreement_rate": (
            disagreements / len(actionable)
            if actionable else None
        ),
        "advances_without_provisional_support":
            unsupported_advances,
        "deferrals_when_reference_actionable": sum(
            item[field] == "DEFER"
            and item["reference_decision"] in ACTIONABLE
            for item in items
        ),
    }


summary = {
    "evidence_aware": metrics(
        records, "baseline_evidence_decision"
    ),
    "traceability_only": metrics(
        records, "pre_stability_decision"
    ),
    "integrated_esdsa": metrics(
        records, "esdsa_decision"
    ),
}

unflagged = [
    item for item in records
    if item["reference_flagged"] == "NO"
]

equivalent = [
    item for item in records
    if item["semantic_equivalence"] == "YES"
]

diagnostics = {
    "unverifiable_required_excerpts": sum(
        item["pre_stability_reason"]
        == "UNVERIFIABLE_REQUIRED_EVIDENCE"
        for item in records
    ),
    "stability_changed_responses": sum(
        item["stability_changed_decision"]
        for item in records
    ),
    "groups_without_unanimous_actionable_decision": sum(
        consensus_gate(items)[0] == "DEFER"
        for items in groups.values()
    ),
    "unflagged_esdsa": metrics(
        unflagged, "esdsa_decision"
    ),
    "provisionally_equivalent_esdsa": metrics(
        equivalent, "esdsa_decision"
    ),
}

report = {
    "experiment": "INTEGRATED_ESDSA_V1_DEVELOPMENT",
    "timestamp_utc": datetime.now(
        timezone.utc
    ).isoformat(),
    "policy": policy,
    "summary": summary,
    "diagnostics": diagnostics,
    "records": records,
    "limitations": [
        "AI-assisted provisional reference.",
        "The method combines previous model outputs, "
        "literal evidence validation and a consensus gate.",
        "The results are not held-out validation.",
        "The semantic equivalence of variants is not "
        "guaranteed by group membership.",
        "No independent evidence audit was performed.",
        "Cross-method matched-coverage analysis remains necessary.",
    ],
}

SPECIFICATION.write_text(
    json.dumps(
        policy, indent=2, ensure_ascii=False
    ) + "\n",
    encoding="utf-8"
)

OUTPUT.write_text(
    json.dumps(
        report, indent=2, ensure_ascii=False
    ) + "\n",
    encoding="utf-8"
)


print("ESDSA — INTEGRATED DEVELOPMENT EXPERIMENT")
print("=" * 66)

for name, result in summary.items():
    print("\n" + name.upper())
    print("Decisions:", result["decisions"])
    print(
        "Coverage:",
        f"{result['actionable']}/{result['count']}",
        f"({result['coverage']:.1%})"
    )
    print(
        "Provisional reference agreement:",
        f"{result['provisional_reference_agreement']:.1%}"
    )
    print(
        "Actionable disagreements:",
        result["actionable_disagreements"]
    )
    print(
        "Advances without provisional support:",
        result["advances_without_provisional_support"]
    )
    print(
        "Unnecessary deferrals relative to reference:",
        result["deferrals_when_reference_actionable"]
    )

print("\nDIAGNOSTICS")
print(
    "Unverifiable required excerpts:",
    diagnostics["unverifiable_required_excerpts"]
)
print(
    "Responses changed by stability check:",
    diagnostics["stability_changed_responses"]
)
print(
    "Groups failing unanimous actionable decision:",
    diagnostics[
        "groups_without_unanimous_actionable_decision"
    ]
)

print("\nPolicy:", SPECIFICATION)
print("Results:", OUTPUT)
print("No API calls made.")
print("No source annotations or model outputs modified.")
print("Development results only; not validated accuracy.")
