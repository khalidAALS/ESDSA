

"""Prepare 24 held-out ESDSA validation scenario drafts.

Uses the existing frozen registry and rubrics.
Does not generate candidate answers or call any model API.
Does not modify development or test data.
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
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data" / "benchmark"

REGISTRY = BASE / "scenario_registry_v2.csv"
DEVELOPMENT = BASE / "development_scenarios_v1.csv"
RUBRIC_DIR = BASE / "rubrics_v1"

OUTPUT = BASE / "validation_scenarios_v1.csv"
REPORT = BASE / "validation_scenarios_preparation_v1.json"


QUESTIONS = {
    "ESDSA-SWE01-05": (
        "During a working day, your team receives reports of "
        "incorrect search results, unusually slow file uploads, "
        "and occasional login failures. A recent deployment may "
        "be relevant, but the reports are incomplete and several "
        "teams are requesting attention. How would you investigate "
        "the problems and decide what to examine first?"
    ),

    "ESDSA-SWE01-10": (
        "A previous attempt to fix a dashboard calculation defect "
        "was unsuccessful. The issue still occurs for some users, "
        "although the original test case now passes. You have the "
        "earlier investigation notes, recent changes and a test "
        "environment. How would you approach the investigation now?"
    ),

    "ESDSA-SWE02-04": (
        "A service has begun returning intermittent errors. "
        "Application logs suggest a connection problem, but "
        "infrastructure monitoring shows no corresponding outage, "
        "and user reports describe different failure patterns. "
        "How would you investigate these conflicting signals?"
    ),

    "ESDSA-SWE02-06": (
        "A scheduled data-processing job sometimes finishes much "
        "later than expected. The delay does not occur consistently, "
        "and it is unclear whether the cause lies in incoming data, "
        "the processing code or an external dependency. What would "
        "your investigation involve?"
    ),

    "ESDSA-SWE03-05": (
        "Your team identifies a defect that affects a small number "
        "of users while also preparing a time-sensitive release. "
        "A quick patch is available, but it could interfere with "
        "another feature, and a more extensive change would delay "
        "the release. How would you decide what correction to make "
        "and how to proceed?"
    ),

    "ESDSA-SWE03-09": (
        "An error in a financial reporting application may produce "
        "incorrect figures in reports that customers rely on. "
        "One proposed fix changes a shared calculation component, "
        "while another limits the affected functionality until "
        "the problem is better understood. How would you evaluate "
        "the options and determine an appropriate correction?"
    ),

    "ESDSA-SWE04-05": (
        "A release includes changes to account permissions, "
        "search functionality and a background export process. "
        "Testing time is limited, and the team has identified "
        "different risks in each area. How would you organise "
        "verification before release and respond to unexpected "
        "test findings?"
    ),

    "ESDSA-SWE04-09": (
        "A software update changes the rules used to approve "
        "high-value transactions. The implementation passes the "
        "developer's initial tests, but an incorrect approval "
        "could have serious consequences. How would you assess "
        "whether the change is adequately verified before "
        "deployment?"
    ),

    "ESDSA-CSS01-08": (
        "A customer initially contacts support because an order "
        "confirmation has not arrived. During the conversation, "
        "they mention that their account also shows an unfamiliar "
        "delivery address, and they are unsure whether the order "
        "was placed successfully. How would you establish the "
        "nature and priority of the problem?"
    ),

    "ESDSA-CSS01-10": (
        "A customer returns after a previous support interaction "
        "failed to resolve repeated account lockouts. The earlier "
        "case notes say the issue was fixed, but the customer "
        "reports that the same problem happened again. How would "
        "you identify the actual problem and determine what "
        "information matters?"
    ),

    "ESDSA-CSS02-05": (
        "A customer reports several related billing discrepancies "
        "while also requesting an urgent account change. Some "
        "records are available through approved internal systems, "
        "but other information must come from the customer. "
        "How would you organise the information-gathering process "
        "while respecting the customer's privacy?"
    ),

    "ESDSA-CSS02-06": (
        "A customer believes a subscription cancellation did "
        "not take effect. The customer cannot recall the exact "
        "date, the account history is incomplete, and the "
        "available payment information does not clearly establish "
        "what happened. How would you gather and assess the "
        "information needed to investigate?"
    ),

    "ESDSA-CSS03-01": (
        "A customer asks to change the delivery address after "
        "placing an order. The order may already be moving through "
        "the fulfilment process, and the available options depend "
        "on its current status. How would you decide what "
        "resolution to offer?"
    ),

    "ESDSA-CSS03-03": (
        "A customer requests a refund because an electronic "
        "product appears to have stopped working. They have "
        "provided only a short description, and the purchase "
        "record is not immediately available. Several possible "
        "resolutions exist, depending on the circumstances. "
        "How would you decide what action is appropriate?"
    ),

    "ESDSA-CSS04-06": (
        "A customer is waiting for an investigation into a "
        "recurring service interruption. The technical team "
        "has not confirmed the cause or supplied a reliable "
        "resolution date. The customer wants a firm commitment. "
        "How would you communicate the situation and manage "
        "the follow-up?"
    ),

    "ESDSA-CSS04-10": (
        "A customer was promised an update on a complaint, "
        "but the promised contact did not happen and the "
        "underlying problem remains unresolved. You are now "
        "responsible for the case. How would you communicate "
        "with the customer and organise the next follow-up?"
    ),

    "ESDSA-OPS01-05": (
        "You have one available team and three competing tasks: "
        "a scheduled warehouse count, an urgent request to "
        "replenish stock for an active customer order, and "
        "equipment maintenance that may affect access to the "
        "warehouse. How would you establish priorities and "
        "adjust them if circumstances change?"
    ),

    "ESDSA-OPS01-09": (
        "An operations team must decide between continuing "
        "a time-sensitive delivery and stopping work to "
        "investigate a potential equipment safety concern. "
        "The available information is incomplete, and delaying "
        "the delivery would have substantial consequences. "
        "How would you determine the priorities?"
    ),

    "ESDSA-OPS02-01": (
        "A distribution centre has experienced several small "
        "stock discrepancies during routine daily checks. "
        "Operations have continued without interruption, "
        "but the discrepancies have appeared on multiple days. "
        "How would you assess the operational risks and "
        "determine an appropriate response?"
    ),

    "ESDSA-OPS02-06": (
        "A delivery partner reports that its capacity may "
        "be reduced next week, but cannot confirm how severely. "
        "Customer demand is also uncertain, and alternative "
        "transport arrangements have different costs and "
        "lead times. How would you assess and respond to "
        "the operational risk?"
    ),

    "ESDSA-OPS03-03": (
        "Two departments are preparing for a service launch. "
        "One reports that its work is complete, while the other "
        "says essential dependencies remain unresolved. "
        "Progress reports contain gaps and some dates conflict. "
        "How would you coordinate the teams and determine "
        "a defensible way forward?"
    ),

    "ESDSA-OPS03-10": (
        "A previous attempt to coordinate a site relocation "
        "failed because several handovers were missed. "
        "A revised schedule has been proposed, but some "
        "teams disagree about who owns the remaining tasks. "
        "How would you use the available evidence to "
        "coordinate the next attempt?"
    ),

    "ESDSA-OPS04-03": (
        "A facility monitoring system reports that operating "
        "conditions may be drifting outside the expected range, "
        "but some sensor readings are missing. The local team "
        "has not reported a problem. How would you monitor "
        "the situation and decide whether escalation is needed?"
    ),

    "ESDSA-OPS04-05": (
        "You are monitoring several active service activities "
        "with limited staff. One activity is approaching its "
        "deadline, another has recently developed a quality "
        "concern, and a third depends on information from "
        "an external partner. How would you track progress, "
        "identify changes requiring attention and decide "
        "when to escalate?"
    ),
}


def read_csv(path):
    with path.open(
        encoding="utf-8-sig", newline=""
    ) as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames


def normalized(text):
    return re.sub(
        r"\s+", " ",
        re.sub(r"[^\w\s]", " ", text.casefold())
    ).strip()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError(
            "Validation scenario outputs already exist. "
            "No existing files will be overwritten."
        )

    registry, _ = read_csv(REGISTRY)
    development, _ = read_csv(DEVELOPMENT)

    validation = [
        r for r in registry
        if r["partition"] == "VALIDATION"
    ]

    if len(validation) != 24:
        raise ValueError(
            f"Expected 24 validation families; got {len(validation)}"
        )

    registry_ids = {
        r["family_id"] for r in validation
    }

    if registry_ids != set(QUESTIONS):
        raise ValueError(
            "Question IDs do not exactly match "
            "the validation registry IDs.\n"
            f"Missing: {sorted(registry_ids - set(QUESTIONS))}\n"
            f"Extra: {sorted(set(QUESTIONS) - registry_ids)}"
        )

    competency_counts = Counter(
        r["competency_code"] for r in validation
    )

    if (
        len(competency_counts) != 12
        or any(n != 2 for n in competency_counts.values())
    ):
        raise ValueError(
            "Expected two validation families "
            "for each of 12 competencies"
        )

    development_questions = [
        r["interview_question"]
        for r in development
    ]

    all_questions = []

    rows = []

    for r in validation:
        family_id = r["family_id"]
        question = QUESTIONS[family_id].strip()

        if len(question) < 100:
            raise ValueError(
                f"Question unexpectedly short: {family_id}"
            )

        rubric_file = (
            r["competency_code"] + "_rubric_v1.json"
        )
        rubric_path = RUBRIC_DIR / rubric_file

        if not rubric_path.is_file():
            raise FileNotFoundError(rubric_path)

        rubric = json.loads(
            rubric_path.read_text(encoding="utf-8")
        )

        rubric_id = rubric["rubric_id"]


        if normalized(question) in {
            normalized(q)
            for q in development_questions + all_questions
        }:
            raise ValueError(
                f"Duplicate question: {family_id}"
            )

        all_questions.append(question)

        rows.append({
            "family_id": family_id,
            "role_code": r["role_code"],
            "role_name": r["role_name"],
            "competency_code": r["competency_code"],
            "competency_name": r["competency_name"],
            "scenario_profile": r["scenario_profile"],
            "partition": "VALIDATION",
            "interview_question": question,
            "rubric_id": rubric_id,
            "rubric_file": rubric_file,
            "draft_status":
                "DRAFT_PENDING_RESEARCHER_APPROVAL",
            "expert_review": "PENDING",
            "reference_validation": "PENDING",
            "candidate_responses_generated": "NO",
        })

    similarity_warnings = []

    for row in rows:
        question = normalized(row["interview_question"])

        for earlier in development:
            similarity = SequenceMatcher(
                None,
                question,
                normalized(earlier["interview_question"])
            ).ratio()

            if similarity >= 0.75:
                similarity_warnings.append({
                    "validation_family": row["family_id"],
                    "development_family":
                        earlier["family_id"],
                    "similarity": round(similarity, 3),
                })

    fields = [
        "family_id",
        "role_code",
        "role_name",
        "competency_code",
        "competency_name",
        "scenario_profile",
        "partition",
        "interview_question",
        "rubric_id",
        "rubric_file",
        "draft_status",
        "expert_review",
        "reference_validation",
        "candidate_responses_generated",
    ]

    OUTPUT.parent.mkdir(
        parents=True, exist_ok=True
    )

    with OUTPUT.open(
        "w", encoding="utf-8", newline=""
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=fields
        )
        writer.writeheader()
        writer.writerows(rows)

    report = {
        "name": "ESDSA validation scenario preparation",
        "scenario_count": len(rows),
        "competency_counts": dict(competency_counts),
        "partition": "VALIDATION",
        "planned_responses": len(rows) * 9,
        "source_registry_sha256": sha256(REGISTRY),
        "validation_scenarios_sha256": sha256(OUTPUT),
        "textual_similarity_warnings": similarity_warnings,
        "candidate_answers_generated": False,
        "model_evaluations_performed": False,
        "reference_annotations_created": False,
        "test_families_accessed_for_generation": False,
        "status": "PENDING_RESEARCHER_APPROVAL",
        "notes": [
            "These are proposed validation question drafts.",
            "Existing family IDs, profiles and rubrics "
            "were preserved.",
            "Text similarity is a screening measure, "
            "not proof of semantic distinctness.",
            "No candidate answers or reference decisions "
            "were generated.",
            "No original experimental files were modified.",
        ],
    }

    REPORT.write_text(
        json.dumps(
            report, indent=2, ensure_ascii=False
        ),
        encoding="utf-8",
    )

    print("ESDSA VALIDATION SCENARIO PREPARATION")
    print("=" * 65)
    print("Validation families:", len(rows))
    print("Competencies represented:", len(competency_counts))
    print("Planned candidate responses:", len(rows) * 9)
    print(
        "Similarity warnings:",
        len(similarity_warnings)
    )
    print("Questions approved for evaluation: NO")
    print("Candidate responses generated: NO")
    print("Original registry modified: NO")
    print("Test families modified: NO")
    print("API calls: NONE")

    print("\nVALIDATION QUESTIONS")

    for row in rows:
        print("\n" + "-" * 65)
        print(row["family_id"])
        print(
            row["competency_name"],
            "|",
            row["scenario_profile"]
        )
        print(row["interview_question"])

    if similarity_warnings:
        print("\nSIMILARITY WARNINGS")
        for warning in similarity_warnings:
            print(warning)

    print("\nSaved:", OUTPUT)
    print("Saved:", REPORT)


if __name__ == "__main__":
    main()
