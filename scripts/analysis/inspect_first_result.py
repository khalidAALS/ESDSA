
import json
import csv
from pathlib import Path

result_path = Path("results/pilot_gpt-5.4-mini.jsonl")
reference_path = Path(
    "data/reference/evaluation_pilot_v1_reference.csv"
)

with result_path.open(encoding="utf-8") as f:
    results = [json.loads(line) for line in f if line.strip()]

with reference_path.open(newline="", encoding="utf-8") as f:
    references = {
        row["response_id"]: row
        for row in csv.DictReader(f)
    }

assert len(results) >= 1, "No results found."

result = results[0]
response_id = result["response_id"]
assessment = result["parsed_output"]
reference = references[response_id]

print("=" * 65)
print("ESDSA — FIRST EVALUATION REVIEW")
print("=" * 65)

print("Response:", response_id)
print("Model:", result["returned_model"])
print("Reference:", reference["reference_decision"])
print("Prediction:", assessment["recommendation"])
print("Reference status:", reference["validation_status"])

print("\nCRITERION-LEVEL EVIDENCE")

for item in assessment["criteria"]:
    print(f"\n{item['criterion_id']}")
    print("Status:", item["evidence_status"])
    print("Excerpt:", item["supporting_excerpt"])
    print("Explanation:", item["explanation"])

print("\nRECOMMENDATION REASON")
print(assessment["recommendation_reason"])

print("\nREFERENCE AGREEMENT")
print(
    "AGREEMENT" if (
        assessment["recommendation"]
        == reference["reference_decision"]
    ) else "DISAGREEMENT"
)

print("\nReview complete. No files modified.")

