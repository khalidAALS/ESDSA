
#!/usr/bin/env python3
"""Deterministic, development-only citation audit; does not change decisions."""

import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent

RESPONSES = ROOT / "data/benchmark/development_responses_v1.csv"
INTEGRATED = ROOT / "results/integrated_esdsa_v1.json"

OUT_JSON = ROOT / "results/traceability_audit_v2.json"
OUT_TXT = ROOT / "results/traceability_audit_v2.txt"


def normalize(s):
    s = unicodedata.normalize("NFKC", s or "")
    s = s.translate(str.maketrans({
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "\u00a0": " ",
    }))
    s = s.casefold()
    s = re.sub(r"[^\w]+", " ", s, flags=re.UNICODE)
    return " ".join(s.split())


def chunks(excerpt):
    # Treat three dots or a single ellipsis glyph as omissions.
    return [
        normalize(x)
        for x in re.split(r"\s*(?:\.{3,}|…)\s*", excerpt or "")
        if normalize(x)
    ]


def ordered_match(parts, source):
    """Check that quoted chunks occur in order, without overlap."""
    pos = 0

    for part in parts:
        at = source.find(part, pos)

        if at < 0:
            return False

        if at > 0 and source[at - 1] != " ":
            return False

        end = at + len(part)

        if end < len(source) and source[end] != " ":
            return False

        pos = end

    return bool(parts)


def classify(excerpt, answer, question):
    parts = chunks(excerpt)

    if not parts:
        return "UNVERIFIABLE", "empty_excerpt"

    answer_text = normalize(answer)
    question_text = normalize(question)

    if ordered_match(parts, answer_text):
        reason = (
            "ordered_answer_match"
            if len(parts) > 1
            else "answer_match"
        )
        return "VERIFIED", reason

    if ordered_match(parts, question_text):
        return "CONTEXT_ONLY", "question_match"

    return "UNVERIFIABLE", "no_exact_ordered_match"


def main():
    with RESPONSES.open(
        encoding="utf-8-sig", newline=""
    ) as f:
        response_rows = list(csv.DictReader(f))

    response_by_id = {
        r["response_id"]: r for r in response_rows
    }

    if len(response_by_id) != 108 or len(response_rows) != 108:
        raise ValueError("Expected 108 unique development responses")

    experiment = json.loads(
        INTEGRATED.read_text(encoding="utf-8")
    )
    records = experiment["records"]

    if len(records) != 108:
        raise ValueError("Expected 108 integrated records")

    details = []
    missing = []

    for r in records:
        rid = r["response_id"]

        if rid not in response_by_id:
            missing.append(rid)
            continue

        source = response_by_id[rid]

        for c in r["criterion_audit"]:
            if c["status"] == "INSUFFICIENT_EVIDENCE":
                continue

            outcome, reason = classify(
                c.get("excerpt"),
                source["answer"],
                source["question"],
            )

            details.append({
                "response_id": rid,
                "group": r["group"],
                "criterion_id": c["criterion_id"],
                "evidence_status": c["status"],
                "excerpt": c.get("excerpt", ""),
                "v1_verifiable": c["excerpt_verifiable"],
                "v2_outcome": outcome,
                "v2_reason": reason,
                "reference_decision": r["reference_decision"],
                "baseline_evidence_decision":
                    r["baseline_evidence_decision"],
                "semantic_equivalence":
                    r["semantic_equivalence"],
            })

    if missing:
        raise ValueError(f"Missing response IDs: {missing}")

    previously_failed = [
        d for d in details
        if d["v1_verifiable"] is False
    ]

    summary = {
        "total_citations_checked": len(details),
        "v1_failed_citations": len(previously_failed),
        "v1_failed_responses": len(set(
            d["response_id"] for d in previously_failed
        )),
        "v2_all_citation_outcomes": dict(
            Counter(d["v2_outcome"] for d in details)
        ),
        "v2_outcomes_among_v1_failures": dict(
            Counter(d["v2_outcome"] for d in previously_failed)
        ),
        "remaining_failed_responses": len(set(
            d["response_id"]
            for d in details
            if d["v2_outcome"] != "VERIFIED"
        )),
        "warning": (
            "Textual matching only: VERIFIED does not establish "
            "relevance or sufficiency. No decision policy is changed."
        ),
    }

    report = {
        "summary": summary,
        "previously_failed_citations": previously_failed,
        "all_citation_audits": details,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    OUT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "ESDSA V2 — QUOTATION VERIFICATION DIAGNOSTIC",
        json.dumps(summary, indent=2),
        "",
        "PREVIOUSLY FAILED CITATIONS",
    ]

    for d in previously_failed:
        lines.append(
            f"{d['response_id']} | "
            f"{d['criterion_id']} | "
            f"{d['evidence_status']} | "
            f"{d['v2_outcome']} | "
            f"{d['v2_reason']}"
        )
        lines.append(f"  excerpt: {d['excerpt']}")

    lines.extend([
        "",
        "IMPORTANT: This script does not alter v1 decisions "
        "or reference labels.",
    ])

    OUT_TXT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print("\n".join(lines))
    print(f"\nSaved: {OUT_JSON}")
    print(f"Saved: {OUT_TXT}")


if __name__ == "__main__":
    main()
