"""Structural checks; does NOT validate semantic equivalence or construct validity."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from esdsa.benchmark import ROOT


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def validate(root: Path = ROOT) -> dict:
    inputs = read_csv(root / "data/model_inputs/pilot_responses.csv")
    refs = read_csv(root / "data/reference/pilot_reference.csv")
    rubric = json.loads((root / "data/model_inputs/rubric.json").read_text(encoding="utf-8"))
    assert len(inputs) == len(refs) == 9, "Expected exactly nine pilot responses"
    ids = [row["response_id"] for row in inputs]
    assert len(ids) == len(set(ids)), "Duplicate response IDs"
    assert set(ids) == {r["response_id"] for r in refs}, "Input/reference ID mismatch"
    assert all(r["answer"].strip() and r["question"].strip() for r in inputs)
    assert len(rubric["criteria"]) == 4
    assert all("reference_decision" not in r and "evidence_condition" not in r for r in inputs), "Leaked labels"
    counts = Counter(r["evidence_condition"] for r in refs)
    assert counts == {"positive": 3, "negative": 3, "insufficient": 3}
    grouped = defaultdict(set)
    for r in refs:
        assert r["reference_decision"] in {"ADVANCE", "DO_NOT_ADVANCE", "DEFER"}
        assert r["equivalence_status"] == "UNREVIEWED"
        grouped[r["evidence_condition"]].add(r["reference_decision"])
    assert all(len(vals) == 1 for vals in grouped.values())
    return {"status": "STRUCTURE_PASS", "responses": len(inputs), "conditions": dict(counts), "semantic_review": "NOT_PERFORMED"}


def main() -> None:
    print(json.dumps(validate(), indent=2))


if __name__ == "__main__":
    main()
