
import csv
import json
from pathlib import Path

root = Path(".")

def read_jsonl(path):
    with path.open(encoding="utf-8") as f:
        return {
            row["response_id"]: row
            for line in f if line.strip()
            for row in [json.loads(line)]
        }

scoring = read_jsonl(
    root / "results/scoring_baseline_v1.jsonl"
)

evidence = read_jsonl(
    root / "results/pilot_gpt-5.4-mini.jsonl"
)

with (
    root / "data/reference/evaluation_pilot_v1_reference.csv"
).open(newline="", encoding="utf-8") as f:
    references = {
        row["response_id"]: row
        for row in csv.DictReader(f)
    }

with (
    root / "data/model_inputs/evaluation_pilot_v1.csv"
).open(newline="", encoding="utf-8") as f:
    inputs = {
        row["response_id"]: row
        for row in csv.DictReader(f)
    }

disputed = [
    response_id
    for response_id, ref in references.items()
    if ref["reference_decision"] == "DEFER"
]

assert len(disputed) == 4

for response_id in sorted(disputed):
    score = scoring[response_id]["parsed_output"]
    aware = evidence[response_id]["parsed_output"]

    print("\n" + "=" * 78)
    print("RESPONSE:", response_id)
    print("=" * 78)

    print("\nCANDIDATE ANSWER:")
    print(inputs[response_id]["answer"])

    print("\nSCORING-ONLY ASSESSMENT:")
    for item in score["criteria"]:
        print(
            f"{item['criterion_id']} | "
            f"Score: {item['score']} | "
            f"{item['reason']}"
        )

    print("\nSCORING RECOMMENDATION:")
    print(score["recommendation"])
    print(score["explanation"])

    print("\nEVIDENCE-AWARE ASSESSMENT:")
    for item in aware["criteria"]:
        print(
            f"{item['criterion_id']} | "
            f"{item['evidence_status']} | "
            f"{item['explanation']}"
        )

    print("\nEVIDENCE-AWARE RECOMMENDATION:")
    print(aware["recommendation"])

print("\nInspection complete. No files modified.")
