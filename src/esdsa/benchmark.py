"""Create a nine-response *pilot*, not an externally validated benchmark.

Reference labels are written separately, and are intentionally excluded from
model-facing inputs. This is not a cryptographic blind: someone reading this
source file can see the test cases and labels. Before held-out evaluation,
create an independently reviewed test set inaccessible to model prompts and
any audit calibration procedure.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUESTION = (
    "A software update causes an application to return incorrect results for "
    "some users. Explain how you would investigate the problem and determine "
    "whether your proposed correction works."
)
RUBRIC = {
    "competency": "Defect diagnosis and verification",
    "criteria": {
        "C1": "Systematic approach to finding cause",
        "C2": "Uses relevant diagnostic evidence (logs, comparisons, tests)",
        "C3": "Reasoned correction of identified defect",
        "C4": "Verifies fix and checks for regression",
    },
    "decision_policy": (
        "ADVANCE requires sufficiently demonstrated safe diagnosis and verification; "
        "DO_NOT_ADVANCE requires affirmative evidence of unsafe practices; "
        "DEFER when evidence is inadequate to support either judgment. "
        "These are pilot response-level judgments, not candidate competence labels."
    ),
}

CASES = [
    {
        "condition": "positive",
        "reference": "ADVANCE",
        "reason": "Provides diagnosis, evidence collection, correction, and regression verification.",
        "variants": [
            "I would reproduce the error first, then compare affected and unaffected cases to narrow down the cause. I'd inspect logs and recent code changes, write a test that captures the failure, and check my proposed fix against that test. Before releasing it, I'd also run regression tests to make sure related functionality still works.",
            "First I'd try to get the same error happening again. Then I'd look at which users were affected, check the logs and recent changes, and try to pin down what caused it. I'd write a test for the problem, make the fix, check that test again, and run the other relevant tests before releasing anything.",
            "I'd start by reproducing it. Then check the affected cases against ones that work, look through logs and recent changes. Once I know where it's going wrong, I'd make a test that shows the issue, fix it and rerun the test. I'd check the other related tests too before deployment.",
        ],
    },
    {
        "condition": "negative",
        "reference": "DO_NOT_ADVANCE",
        "reason": "Explicitly advocates deploying guesses without investigating or verifying.",
        "variants": [
            "I'd change the part of the code that looked wrong and deploy the update. I wouldn't spend time reproducing the original problem or checking logs. If nobody complained afterwards, I'd assume the fix had worked. Running extra tests would probably slow things down.",
            "I'd probably just edit the code that seems wrong and ship it. I wouldn't bother reproducing the error or looking through logs. If no one reports another problem, I'd take that as proof it worked. More tests would only slow me down.",
            "Change what looks broken, deploy. No need to recreate the error or inspect logs first. No complaints afterwards means it's fixed, as far as I'm concerned. Extra tests would waste time.",
        ],
    },
    {
        "condition": "insufficient",
        "reference": "DEFER",
        "reason": "Only states generic intentions; no concrete diagnostic or verification evidence.",
        "variants": [
            "I'd investigate what happened, work out a solution, and make sure everything was working properly afterwards.",
            "Well, first I'd look into what went wrong. Then I'd figure out how to sort it out and make sure things were fine after that.",
            "I'd check the issue, find a way to fix it, and confirm it was working again.",
        ],
    },
]


def build(root: Path = ROOT) -> tuple[Path, Path]:
    inputs = root / "data" / "model_inputs"
    reference = root / "data" / "reference"
    inputs.mkdir(parents=True, exist_ok=True)
    reference.mkdir(parents=True, exist_ok=True)
    rows = []
    labels = []
    for case in CASES:
        for variant_idx, answer in enumerate(case["variants"]):
            response_id = f"PILOT-SW-01-{case['condition'].upper()}-V{variant_idx}"
            rows.append({
                "response_id": response_id,
                "scenario_id": "PILOT-SW-01",
                "question": QUESTION,
                "answer": answer,
                "rubric_id": "SW-DEFECT-V1",
            })
            labels.append({
                "response_id": response_id,
                "scenario_id": "PILOT-SW-01",
                "evidence_condition": case["condition"],
                "reference_decision": case["reference"],
                "reference_justification": case["reason"],
                "equivalence_status": "UNREVIEWED",
                "reference_validation_status": "UNREVIEWED",
            })
    input_path = inputs / "pilot_responses.csv"
    label_path = reference / "pilot_reference.csv"
    for path, data in [(input_path, rows), (label_path, labels)]:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            writer.writeheader()
            writer.writerows(data)
    (inputs / "rubric.json").write_text(json.dumps(RUBRIC, indent=2) + "\n", encoding="utf-8")
    return input_path, label_path


def main() -> None:
    a, b = build()
    print(f"Wrote model-facing responses: {a}")
    print(f"Wrote local-only pilot references: {b}")
    print("NOTE: All pilot reference judgments and equivalence claims remain UNREVIEWED.")


if __name__ == "__main__":
    main()
