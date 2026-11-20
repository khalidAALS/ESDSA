

"""Prepare 24 ESDSA TEST scenario questions.

Preserves the original registry and rubric assignments.
Does not generate candidate responses or evaluate ESDSA.
No API calls. Does not access TEST response data.
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
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher

ROOT = Path(__file__).resolve().parents[2]

REGISTRY = ROOT / "data/benchmark/scenario_registry_v2.csv"
VALIDATION = ROOT / "data/benchmark/validation_scenarios_v2.csv"
RUBRICS = ROOT / "data/benchmark/rubrics_v1"

OUTPUT = ROOT / "data/benchmark/test_scenarios_v1.csv"
MANIFEST = ROOT / "data/benchmark/test_scenarios_manifest_v1.json"


SCENARIOS = {
    "ESDSA-SWE01-03": (
        "Incomplete contextual information",
        "A web application's search page intermittently stops returning results. "
        "The report contains a screenshot and approximate time, but no steps "
        "to reproduce the problem. Other users have not reported it.",
        "You receive this report near the end of your shift. How would you "
        "investigate what is happening before deciding what needs fixing?"
    ),

    "ESDSA-SWE01-07": (
        "Stakeholder disagreement",
        "An internal dashboard sometimes shows outdated figures. The product "
        "manager believes the browser is caching old data, while an engineer "
        "suspects the service supplying the figures. Neither explanation has "
        "been tested, and the dashboard works for some users.",
        "How would you approach diagnosing the problem while the two "
        "stakeholders disagree about its cause?"
    ),

    "ESDSA-SWE02-05": (
        "Multiple competing priorities",
        "A backend service has elevated response times during peak usage. "
        "The team has limited time to investigate. Recent deployment changes, "
        "database load and a third-party dependency are all possible factors, "
        "but the available evidence is inconclusive.",
        "What technical investigation would you undertake, and how would "
        "you decide which findings justify further investigation?"
    ),

    "ESDSA-SWE02-10": (
        "Recovery after an unsuccessful attempt",
        "A developer increased worker capacity to address a queue-processing "
        "delay, but the delay persists. Monitoring shows intermittent spikes "
        "and the earlier change has not established why work is accumulating.",
        "How would you investigate the continuing delay after the first "
        "attempt failed to resolve it?"
    ),

    "ESDSA-SWE03-03": (
        "Incomplete contextual information",
        "A document-upload service occasionally stores duplicate attachments. "
        "There are indications that retries occur, but the available logs do "
        "not yet establish whether the client or server initiates them.",
        "You have been asked to recommend a correction. How would you "
        "determine what should change and justify your recommendation?"
    ),

    "ESDSA-SWE03-04": (
        "Conflicting information",
        "An application sends duplicate order-confirmation messages. "
        "Application logs suggest a single event was emitted, but messaging "
        "metrics show repeated deliveries. Both sources may be incomplete.",
        "How would you decide on an appropriate correction when the "
        "available diagnostic evidence points in different directions?"
    ),

    "ESDSA-SWE04-02": (
        "Time-sensitive problem",
        "A production patch is proposed for an urgent invoice-calculation "
        "error. The patch appears to correct the reported case, but the "
        "calculation logic also supports refunds and discount adjustments.",
        "With limited time before deployment, how would you determine "
        "whether the patch is ready and what should happen next?"
    ),

    "ESDSA-SWE04-08": (
        "Unexpected complication",
        "A fix for a failed report export passes the original reproduction "
        "test. During release checks, however, an older export format "
        "unexpectedly produces different output.",
        "How would you evaluate the fix and decide whether to release, "
        "revise or investigate further?"
    ),

    "ESDSA-CSS01-02": (
        "Time-sensitive problem",
        "A customer contacts support shortly before an important online "
        "appointment. They say the booking is missing, although an earlier "
        "notification suggested it was confirmed. Their account shows "
        "several recent booking changes.",
        "How would you establish the customer's actual problem before "
        "choosing how to help?"
    ),

    "ESDSA-CSS01-07": (
        "Stakeholder disagreement",
        "A customer reports that a shared subscription has lost access. "
        "The account administrator says access was deliberately restricted, "
        "while another authorised user says the change was accidental.",
        "How would you identify and define the support issue when the "
        "people involved disagree about what happened?"
    ),

    "ESDSA-CSS02-01": (
        "Routine operational problem",
        "A customer reports that a replacement item has not arrived, "
        "although an automated message indicates delivery. The tracking "
        "record shows a completed delivery event without identifying "
        "who received the package.",
        "What information would you gather to understand the situation "
        "and determine what is actually known?"
    ),

    "ESDSA-CSS02-03": (
        "Incomplete contextual information",
        "A customer says a promotional discount disappeared from their "
        "account. They cannot remember when the promotion was activated "
        "and have only a partial screenshot of an earlier checkout.",
        "How would you investigate the customer's claim while deciding "
        "which information is appropriate to request or verify?"
    ),

    "ESDSA-CSS03-05": (
        "Multiple competing priorities",
        "A customer has received the wrong item and wants an immediate "
        "replacement before an upcoming event. Stock is limited, "
        "the original shipment status is disputed, and expedited "
        "replacement requires authorisation.",
        "How would you determine an appropriate resolution given the "
        "customer's urgency and the available constraints?"
    ),

    "ESDSA-CSS03-06": (
        "Uncertain cause or outcome",
        "A customer reports repeated service interruptions. Initial account "
        "checks show no clear fault, while a regional incident notice may "
        "or may not cover their location. The customer requests a refund.",
        "How would you decide what action is justified while the cause "
        "and service impact remain uncertain?"
    ),

    "ESDSA-CSS04-01": (
        "Routine operational problem",
        "A customer contacts support about a replacement order. "
        "The request has been accepted but the warehouse has not yet "
        "confirmed dispatch or a delivery date.",
        "How would you explain the situation to the customer and manage "
        "communication until there is a confirmed outcome?"
    ),

    "ESDSA-CSS04-04": (
        "Conflicting information",
        "A support ticket is marked resolved, but the customer reports "
        "that the problem remains. An internal note says a fix was "
        "applied, while there is no confirmation that the customer "
        "successfully used the service afterward.",
        "What would you communicate to the customer, and how would "
        "you handle the next update or confirmation?"
    ),

    "ESDSA-OPS01-02": (
        "Time-sensitive problem",
        "An operations team is preparing for an afternoon service launch. "
        "A required equipment check is delayed, staff coverage is thinner "
        "than expected, and a separate routine report is due shortly.",
        "How would you prioritise the work, and what would lead you "
        "to change that order?"
    ),

    "ESDSA-OPS01-08": (
        "Unexpected complication",
        "A distribution centre has a planned workload for the day. "
        "A vehicle becomes unavailable without warning, and a large "
        "incoming delivery arrives earlier than expected while several "
        "customer orders are approaching their deadlines.",
        "How would you revise the operating priorities in response "
        "to these changes?"
    ),

    "ESDSA-OPS02-02": (
        "Time-sensitive problem",
        "A temperature-controlled shipment is due to leave shortly. "
        "One monitoring device reports a brief excursion, but a second "
        "device shows normal readings. The shipment is time-sensitive.",
        "How would you assess the operational risk and decide what "
        "precautions or escalation are justified?"
    ),

    "ESDSA-OPS02-10": (
        "Recovery after an unsuccessful attempt",
        "A temporary staffing adjustment was introduced to reduce "
        "congestion in a loading area, but waiting times remain high. "
        "A near-miss has since been reported and the congestion's "
        "underlying cause is still unclear.",
        "How would you reassess the risks and determine an "
        "appropriate response after the first intervention failed?"
    ),

    "ESDSA-OPS03-02": (
        "Time-sensitive problem",
        "A maintenance task must be completed before an evening "
        "operational handover. The maintenance team reports progress, "
        "but the scheduling system still shows a pending dependency "
        "and the receiving team has not confirmed readiness.",
        "How would you coordinate the remaining work and establish "
        "whether the handover can proceed?"
    ),

    "ESDSA-OPS03-07": (
        "Stakeholder disagreement",
        "A facilities supervisor says a meeting room is ready for a "
        "scheduled event, while the technical support team reports an "
        "unresolved audiovisual issue. The event coordinator needs "
        "a reliable status update.",
        "How would you coordinate the parties and decide what "
        "information should support the readiness update?"
    ),

    "ESDSA-OPS04-06": (
        "Uncertain cause or outcome",
        "A cleaning contractor reports completing a required overnight "
        "task. The digital completion record is missing, and an early "
        "inspection raises concerns about part of the area. Operations "
        "are due to begin soon.",
        "How would you monitor the situation and decide whether "
        "further action or escalation is necessary?"
    ),

    "ESDSA-OPS04-07": (
        "Stakeholder disagreement",
        "A site manager reports that a delayed repair is progressing "
        "normally. The contractor says an unresolved parts shortage "
        "could prevent completion, while the next operational shift "
        "is planning around the original schedule.",
        "How would you monitor the repair and manage escalation "
        "or follow-through when these reports disagree?"
    ),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    require(path.is_file(), f"Missing file: {path}")

    with path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as f:
        return list(csv.DictReader(f))


def normalized(text):
    return " ".join(text.lower().split())


def main():
    print("ESDSA — TEST SCENARIO PREPARATION")
    print("=" * 65)
    print("API requests: 0")
    print("Original scenario registry: READ ONLY")
    print("Existing validation scenarios: READ ONLY")
    print("TEST responses: NOT GENERATED")
    print()

    for path in (OUTPUT, MANIFEST):
        require(
            not path.exists(),
            f"Refusing to overwrite existing file: {path}"
        )

    registry = read_csv(REGISTRY)
    validation = read_csv(VALIDATION)

    test_rows = [
        row for row in registry
        if row["partition"] == "TEST"
    ]

    require(
        len(test_rows) == 24,
        f"Expected 24 TEST families, found {len(test_rows)}"
    )

    require(
        len(SCENARIOS) == 24,
        "Expected 24 authored TEST scenarios"
    )

    family_ids = [r["family_id"] for r in test_rows]

    require(
        len(set(family_ids)) == 24,
        "Duplicate TEST family identifiers"
    )

    require(
        set(family_ids) == set(SCENARIOS),
        "Authored scenarios do not match TEST registry IDs"
    )

    require(
        len(validation) == 24,
        "Expected 24 validation scenarios"
    )

    validation_questions = [
        normalized(row["interview_question"])
        for row in validation
    ]

    validation_families = {
        row["family_id"]
        for row in validation
    }

    require(
        not set(family_ids).intersection(validation_families),
        "TEST and validation family overlap"
    )

    outputs = []
    rubric_hashes = {}
    questions_seen = set()
    near_matches = []

    for row in test_rows:
        fid = row["family_id"]
        profile, context, question = SCENARIOS[fid]

        require(
            row["scenario_profile"] == profile,
            f"Scenario profile mismatch: {fid}"
        )

        require(
            not row["scenario_question"].strip()
            and not row["scenario_context"].strip(),
            f"Registry already contains scenario content: {fid}"
        )

        require(
            row["construction_status"] == "NOT_STARTED",
            f"Unexpected construction status: {fid}"
        )

        require(
            len(question.split()) >= 12,
            f"Question too short: {fid}"
        )

        require(
            len(context.split()) >= 20,
            f"Scenario context too short: {fid}"
        )

        nq = normalized(question)

        require(
            nq not in questions_seen,
            f"Duplicate TEST question: {fid}"
        )

        require(
            nq not in validation_questions,
            f"Exact validation question duplicated: {fid}"
        )

        questions_seen.add(nq)

        code = row["competency_code"]
        rubric_path = RUBRICS / f"{code}_rubric_v1.json"

        require(
            rubric_path.is_file(),
            f"Missing rubric: {code}"
        )

        rubric = json.loads(
            rubric_path.read_text(encoding="utf-8")
        )

        require(
            rubric["competency_code"] == code,
            f"Rubric competency mismatch: {fid}"
        )

        require(
            len(rubric["criteria"]) == 3,
            f"Rubric must contain three indicators: {fid}"
        )

        rubric_hashes[code] = file_hash(rubric_path)

        similarity = max(
            SequenceMatcher(
                None, nq, old
            ).ratio()
            for old in validation_questions
        )

        if similarity >= 0.80:
            near_matches.append({
                "family_id": fid,
                "maximum_question_similarity": round(
                    similarity, 3
                ),
            })

        outputs.append({
            "family_id": fid,
            "role_code": row["role_code"],
            "role_name": row["role_name"],
            "competency_code": code,
            "competency_name": row["competency_name"],
            "scenario_profile": profile,
            "partition": "TEST",
            "scenario_context": context,
            "interview_question": question,
            "rubric_id": rubric["rubric_id"],
            "rubric_file": rubric_path.name,
            "construction_status": "DRAFT_PRE_GENERATION",
            "expert_review": "PENDING",
            "reference_validation": "PENDING",
            "candidate_responses_generated": "NO",
        })

    require(
        len(outputs) == 24,
        "Unexpected output family count"
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    columns = list(outputs[0])

    with OUTPUT.open(
        "x", encoding="utf-8", newline=""
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=columns
        )
        writer.writeheader()
        writer.writerows(outputs)

    manifest = {
        "experiment": "ESDSA_TEST_SCENARIOS_V1",
        "status": "PREPARED_NOT_GENERATED",
        "partition": "TEST",
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "families": 24,
        "planned_responses": 216,
        "source_registry_sha256": file_hash(REGISTRY),
        "validation_scenarios_sha256": file_hash(VALIDATION),
        "rubric_sha256": dict(sorted(rubric_hashes.items())),
        "test_scenarios_sha256": file_hash(OUTPUT),
        "question_similarity_flags": near_matches,
        "methodological_disclosure": (
            "TEST questions were authored after observing "
            "VALIDATION results. TEST response generation, "
            "inference and outcomes had not yet been undertaken "
            "at the time of scenario preparation."
        ),
        "expert_review": "PENDING",
        "api_requests": 0,
        "test_responses_generated": False,
        "esdsa_predictions_generated": False,
        "frozen_policy_modified": False,
    }

    with MANIFEST.open(
        "x", encoding="utf-8"
    ) as f:
        json.dump(
            manifest,
            f,
            indent=2,
            ensure_ascii=False,
        )
        f.write("\n")

    print("TEST SCENARIO PREPARATION: PASSED")
    print("Families:", len(outputs))
    print("Competencies:", len(rubric_hashes))
    print("Planned candidate responses: 216")
    print("Exact duplicate validation questions: 0")
    print(
        "Potentially similar question flags:",
        len(near_matches)
    )
    print()
    print("Outputs:")
    print(OUTPUT.relative_to(ROOT))
    print(MANIFEST.relative_to(ROOT))
    print()
    print("Original registry: NOT MODIFIED")
    print("Frozen ESDSA policy: NOT MODIFIED")
    print("TEST responses: NOT GENERATED")
    print("API requests: 0")


if __name__ == "__main__":
    main()
