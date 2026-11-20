

"""Read-only audit of existing independent review worksheets."""

# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = (
    ROOT / "data/benchmark/content_review_v1/independent_reviews"
)

REVIEW_COLUMNS = [
    "A_criterion_1",
    "A_criterion_2",
    "A_criterion_3",
    "A_evidence_explanation",
    "B_criterion_1",
    "B_criterion_2",
    "B_criterion_3",
    "B_evidence_explanation",
    "C_criterion_1",
    "C_criterion_2",
    "C_criterion_3",
    "C_evidence_explanation",
    "pairwise_semantic_equivalence",
    "equivalence_explanation",
]


def filled(value):
    return bool((value or "").strip())


def main():
    paths = sorted(REVIEW_DIR.glob("benchmark_review_*.csv"))

    if not paths:
        raise FileNotFoundError(
            f"No independent-review files found in {REVIEW_DIR}"
        )

    print("INDEPENDENT REVIEW COMPLETION AUDIT")
    print("=" * 65)

    for path in paths:
        with path.open(
            encoding="utf-8-sig", newline=""
        ) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            columns = set(reader.fieldnames or [])

        missing_columns = set(REVIEW_COLUMNS) - columns

        if missing_columns:
            raise ValueError(
                f"{path.name}: missing columns {missing_columns}"
            )

        statuses = Counter(
            (r.get("review_status") or "").strip().upper()
            or "BLANK"
            for r in rows
        )

        fully_assessed = sum(
            all(filled(r.get(col)) for col in REVIEW_COLUMNS)
            for r in rows
        )

        partly_assessed = sum(
            any(filled(r.get(col)) for col in REVIEW_COLUMNS)
            and not all(
                filled(r.get(col)) for col in REVIEW_COLUMNS
            )
            for r in rows
        )

        untouched = sum(
            not any(filled(r.get(col)) for col in REVIEW_COLUMNS)
            for r in rows
        )

        print(f"\nFILE: {path.name}")
        print(f"Groups: {len(rows)}")
        print(f"Review statuses: {dict(statuses)}")
        print(f"All assessment fields filled: {fully_assessed}")
        print(f"Some assessment fields filled: {partly_assessed}")
        print(f"No assessment fields filled: {untouched}")

        print("\nFilled fields:")
        for col in REVIEW_COLUMNS:
            count = sum(
                filled(r.get(col)) for r in rows
            )
            print(f"  {col}: {count}/{len(rows)}")

        assessed_groups = [
            r["review_group"]
            for r in rows
            if any(
                filled(r.get(col))
                for col in REVIEW_COLUMNS
            )
        ]

        print("\nGroups containing review entries:")
        print(
            ", ".join(assessed_groups)
            if assessed_groups
            else "NONE"
        )

    print("\nAudit complete. No files were modified.")


if __name__ == "__main__":
    main()

