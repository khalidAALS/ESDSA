
# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

AUDIT = ROOT / "results/traceability_audit_v2.json"
RESPONSES = ROOT / "data/benchmark/development_responses_v1.csv"

with AUDIT.open(encoding="utf-8") as f:
    audit = json.load(f)

with RESPONSES.open(encoding="utf-8-sig", newline="") as f:
    responses = {
        row["response_id"]: row
        for row in csv.DictReader(f)
    }

unresolved = [
    item
    for item in audit["all_citation_audits"]
    if item["v2_outcome"] != "VERIFIED"
]

print(f"\nUNRESOLVED CITATIONS: {len(unresolved)}")
print(
    "AFFECTED RESPONSES:",
    len(set(x["response_id"] for x in unresolved))
)

for item in unresolved:
    response = responses[item["response_id"]]

    print("\n" + "=" * 85)
    print("RESPONSE ID:", item["response_id"])
    print("GROUP:", item["group"])
    print("CRITERION:", item["criterion_id"])
    print("CLASSIFICATION:", item["evidence_status"])
    print("V2 RESULT:", item["v2_outcome"])
    print("REASON:", item["v2_reason"])
    print("PROVISIONAL REFERENCE:", item["reference_decision"])
    print("EVIDENCE-AWARE DECISION:",
          item["baseline_evidence_decision"])

    print("\nREJECTED EXCERPT:")
    print(item["excerpt"])

    print("\nORIGINAL INTERVIEW QUESTION:")
    print(response["question"])

    print("\nCOMPLETE CANDIDATE ANSWER:")
    print(response["answer"])

    print("\n" + "=" * 85)
