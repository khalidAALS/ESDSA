
import csv
import hashlib
import json
from pathlib import Path

REGISTRY = Path("data/benchmark/scenario_registry_v1.csv")
OUTPUT_DIR = Path("data/benchmark/rubrics_v1")
MANIFEST = OUTPUT_DIR / "rubric_manifest.json"


RUBRICS = {
    "SWE01": [
        ("Reproduction", "Establish how to reproduce or characterise the reported failure.",
         "Recreates the failure with affected inputs.",
         "Explicitly chooses not to investigate whether the fault can be reproduced."),
        ("Comparison", "Compare failure conditions with functioning behaviour.",
         "Compares failing and successful execution paths.",
         "Dismisses relevant differences without examining them."),
        ("Systematic narrowing", "Use observations to narrow plausible causes.",
         "Isolates the issue to a specific component through checks.",
         "Selects an unrelated cause despite contradictory diagnostic evidence.")
    ],
    "SWE02": [
        ("Relevant sources", "Identify technical evidence appropriate to the failure.",
         "Examines relevant logs, traces or configuration changes.",
         "Discards relevant diagnostics without justification."),
        ("Hypothesis testing", "Propose checks that distinguish possible causes.",
         "Tests whether the issue follows a specific change.",
         "Treats an untested assumption as conclusive."),
        ("Evidence interpretation", "Connect observations to a diagnostic conclusion.",
         "Explains why an observed pattern supports a cause.",
         "Ignores observations that directly refute the proposed cause.")
    ],
    "SWE03": [
        ("Cause identification", "Identify a plausible cause supported by investigation.",
         "Traces the failure to faulty persistence logic.",
         "Claims a cause despite explicitly contrary evidence."),
        ("Linked correction", "Connect the proposed correction to that identified cause.",
         "Corrects the logic identified as responsible for the failure.",
         "Changes unrelated logic while acknowledging it is not causal."),
        ("Correction justification", "Explain why the correction addresses the problem.",
         "Explains how the change prevents the observed failure.",
         "Adopts a known ineffective fix without justification.")
    ],
    "SWE04": [
        ("Targeted verification", "Test whether the reported failure is resolved.",
         "Repeats the previously failing scenario after correction.",
         "Explicitly skips checking whether the fix works."),
        ("Regression consideration", "Assess potential impact on previously working behaviour.",
         "Runs related regression checks.",
         "Deliberately omits necessary regression checks despite known impact."),
        ("Outcome assessment", "Use verification findings to decide next action.",
         "Investigates a failed retest before releasing.",
         "Proceeds despite known failed verification without mitigation.")
    ],
    "CSS01": [
        ("Issue clarification", "Establish what problem the customer is experiencing.",
         "Asks the customer to describe the failed operation.",
         "Refuses to clarify an ambiguous complaint."),
        ("Impact identification", "Determine the customer's affected service or outcome.",
         "Checks which functions are unavailable and their impact.",
         "Ignores an explicitly reported serious impact."),
        ("Problem definition", "Summarise the issue before selecting a resolution.",
         "Confirms the specific problem with the customer.",
         "Pursues a solution known to address a different problem.")
    ],
    "CSS02": [
        ("Relevant questions", "Request information needed to understand the issue.",
         "Asks for the error message and steps preceding failure.",
         "Rejects necessary diagnostic details without reason."),
        ("Source verification", "Distinguish confirmed facts from assumptions.",
         "Checks account status against an authorised record.",
         "Presents unverified speculation as confirmed fact."),
        ("Proportionate collection", "Gather only information appropriate and authorised.",
         "Uses approved channels for relevant account details.",
         "Requests unnecessary sensitive information through an insecure channel.")
    ],
    "CSS03": [
        ("Option assessment", "Consider a resolution appropriate to the evidence.",
         "Checks eligibility before proposing a remedy.",
         "Selects a known inapplicable remedy."),
        ("Policy awareness", "Respect applicable authorisation and service constraints.",
         "Escalates an exception requiring supervisor approval.",
         "Knowingly bypasses an applicable approval requirement."),
        ("Uncertainty handling", "Recognise when additional information or escalation is needed.",
         "Pauses resolution until conflicting records are checked.",
         "Declares a disputed issue resolved without checking it.")
    ],
    "CSS04": [
        ("Clear explanation", "Communicate the proposed action understandably.",
         "Explains the next step and expected customer action.",
         "Intentionally withholds material next-step information."),
        ("Expectation management", "Set justified expectations without unsupported promises.",
         "Explains that timing depends on investigation.",
         "Guarantees a result known to be uncertain."),
        ("Follow-up", "Provide an appropriate mechanism for status or confirmation.",
         "Arranges confirmation after the service is restored.",
         "Closes a known unresolved issue without follow-up or escalation.")
    ],
    "OPS01": [
        ("Priority criteria", "Identify relevant urgency, impact and dependencies.",
         "Ranks tasks by deadline and operational consequence.",
         "Ignores a known critical dependency."),
        ("Trade-off reasoning", "Explain prioritisation choices using relevant evidence.",
         "Explains why a safety-critical task precedes routine work.",
         "Prioritises convenience despite acknowledged serious consequences."),
        ("Reprioritisation", "Reassess priorities when material conditions change.",
         "Updates the schedule after an urgent incident.",
         "Refuses to reconsider priorities after a major disruption.")
    ],
    "OPS02": [
        ("Hazard recognition", "Identify a plausible operational risk in context.",
         "Recognises a failure that could interrupt essential delivery.",
         "Explicitly disregards a known serious operational hazard."),
        ("Likelihood and impact", "Consider uncertainty and possible consequences.",
         "Assesses both disruption likelihood and service impact.",
         "Treats a documented high-impact risk as harmless without basis."),
        ("Risk response", "Propose proportionate mitigation or escalation.",
         "Adds a contingency and escalates a critical exposure.",
         "Continues an unsafe activity despite a known unmitigated risk.")
    ],
    "OPS03": [
        ("Evidence integration", "Use relevant information from operational sources.",
         "Reconciles supplier status with delivery records.",
         "Discards verified contradictory records."),
        ("Coordination", "Identify responsible parties and necessary dependencies.",
         "Confirms handoffs and owners before changing the schedule.",
         "Assigns mutually incompatible tasks without resolving ownership."),
        ("Decision traceability", "Explain actions using relevant operational evidence.",
         "Records why a schedule change was necessary.",
         "Knowingly documents an invented justification.")
    ],
    "OPS04": [
        ("Progress signals", "Identify information needed to monitor execution.",
         "Checks milestone completion against the delivery plan.",
         "Refuses to monitor a known high-risk dependency."),
        ("Trigger recognition", "Recognise when deviation requires action.",
         "Flags a missed critical milestone for review.",
         "Ignores an acknowledged escalation threshold."),
        ("Escalation and follow-through", "Direct issues to appropriate owners and verify response.",
         "Escalates a blocked delivery and checks resolution.",
         "Conceals a known critical blockage from responsible staff.")
    ]
}

with REGISTRY.open(newline="", encoding="utf-8") as f:
    registry = list(csv.DictReader(f))

competencies = {}

for row in registry:
    code = row["competency_code"]
    identity = (
        row["role_code"],
        row["role_name"],
        row["competency_name"]
    )

    if code in competencies and competencies[code] != identity:
        raise ValueError(f"Inconsistent registry entry: {code}")

    competencies[code] = identity

if len(registry) != 120 or set(competencies) != set(RUBRICS):
    raise ValueError("Registry and rubric definitions disagree")

if OUTPUT_DIR.exists() and any(OUTPUT_DIR.iterdir()):
    raise SystemExit(
        "Rubric output folder is not empty. No files overwritten."
    )

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

manifest_entries = []

for code, indicators in sorted(RUBRICS.items()):
    if len(indicators) != 3:
        raise ValueError(f"Expected three indicators: {code}")

    role_code, role_name, competency_name = competencies[code]

    criteria = []

    for index, item in enumerate(indicators, start=1):
        name, definition, positive, negative = item

        if not all(item):
            raise ValueError(f"Empty criterion content: {code}")

        criteria.append({
            "id": f"{code}-C{index}",
            "name": name,
            "definition": definition,
            "illustrative_positive_evidence": positive,
            "illustrative_negative_evidence": negative
        })

    rubric = {
        "rubric_id": f"ESDSA-{code}-R1",
        "version": "1.0-draft",
        "role_code": role_code,
        "role_name": role_name,
        "competency_code": code,
        "competency_name": competency_name,
        "criteria": criteria,
        "evidence_statuses": {
            "POSITIVE_EVIDENCE": (
                "The answer explicitly or clearly demonstrates "
                "the indicator in context."
            ),
            "NEGATIVE_EVIDENCE": (
                "The answer explicitly demonstrates a materially "
                "deficient approach concerning the indicator."
            ),
            "INSUFFICIENT_EVIDENCE": (
                "The answer does not establish either positive "
                "or negative evidence for the indicator."
            )
        },
        "interpretation_rules": [
            "Assess demonstrated meaning, not exact wording.",
            "Do not infer deficient practice solely from omission.",
            "A brief answer can provide sufficient evidence.",
            "A fluent or lengthy answer is not sufficient by itself.",
            "Consider scenario context and applicable constraints.",
            "Record the supporting passage or indicate absence.",
            "Illustrative examples are not exhaustive.",
            "Do not infer protected or demographic attributes."
        ],
        "decision_policy": "NOT_YET_VALIDATED",
        "expert_review": "PENDING",
        "reference_validation": "PENDING"
    }

    path = OUTPUT_DIR / f"{code}_rubric_v1.json"

    path.write_text(
        json.dumps(rubric, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    manifest_entries.append({
        "competency_code": code,
        "file": path.name,
        "sha256": file_hash,
        "criteria_count": len(criteria)
    })

manifest = {
    "version": "1.0-draft",
    "registry_sha256": hashlib.sha256(
        REGISTRY.read_bytes()
    ).hexdigest(),
    "rubric_count": len(manifest_entries),
    "total_indicators": sum(
        item["criteria_count"] for item in manifest_entries
    ),
    "status": "UNVALIDATED_RESEARCHER_AUTHORED",
    "rubrics": manifest_entries
}

MANIFEST.write_text(
    json.dumps(manifest, indent=2),
    encoding="utf-8"
)

print("\nESDSA — COMPETENCY RUBRICS V1")
print("=" * 60)
print("Roles:", len({v[0] for v in competencies.values()}))
print("Competency rubrics:", len(manifest_entries))
print("Observable indicators:", manifest["total_indicators"])
print("Status: DRAFT — EXPERT REVIEW PENDING")
print("Decision policy: NOT YET VALIDATED")
print("Folder:", OUTPUT_DIR)
print("Manifest:", MANIFEST)
print("\nNo API calls made.")
print("Original experiments and registry unchanged.")
