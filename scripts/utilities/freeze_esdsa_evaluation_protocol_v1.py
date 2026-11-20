

"""Freeze the original ESDSA model-generation and evaluation protocol.

Records original code, prompt hashes, schemas and explicit API settings.
Does not run models, modify existing data, or overwrite a freeze.
"""

# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FREEZE_DIR = (
    ROOT / "data/benchmark/policy_freeze_v2"
)

OUTPUT = (
    FREEZE_DIR / "esdsa_evaluation_protocol_freeze_v1.json"
)

EXPECTED_SCRIPTS = {
    "generate_development_responses_v1.py": {
        "sha256": (
            "9b367486b2324131327a617c86f39e1af46824211fc1d69c53771ed401f8ea15"
        ),
        "prompt_name": "INSTRUCTIONS",
        "prompt_sha256": (
            "0088e252816f04dbcc56e55b35c53b3ad3601c61a5ca4c494b3812ddaafa67aa"
        ),
        "output_format": "json_schema",
    },
    "run_benchmark_evaluator.py": {
        "sha256": (
            "c624b4efd26d26e6d78ab361c176556e114524b3603ca4e3bdfa46a03dbcde02"
        ),
        "prompt_name": "INSTRUCTIONS",
        "prompt_sha256": (
            "5a9b7d47b3f80906e00ebbab3d2ffc7a386f22ef141fe9d159841087c869ab62"
        ),
        "output_format": "json_schema",
    },
    "run_scoring_baseline_108.py": {
        "sha256": (
            "b0121cfc7833c4d822f9129018266c4acb7de9a48b5c465f7e1d05e8123e7800"
        ),
        "prompt_name": "SYSTEM_PROMPT",
        "prompt_sha256": (
            "db958078cc42f00d1ca93f2eece062d44dc10ab80d5e7b1878af558e5ecdb256"
        ),
        "output_format": "json_object",
    },
}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(path.read_bytes())


def get_constants(tree):
    constants = {}

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue

        if len(node.targets) != 1:
            continue

        target = node.targets[0]

        if not isinstance(target, ast.Name):
            continue

        if target.id not in {
            "MODEL", "INSTRUCTIONS", "SYSTEM_PROMPT"
        }:
            continue

        try:
            constants[target.id] = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue

    return constants


def get_api_calls(tree):
    calls = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if not isinstance(func, ast.Attribute):
            continue

        if func.attr != "create":
            continue

        owner = ast.unparse(func.value)

        if "responses" not in owner:
            continue

        keyword_expressions = {}

        for kw in node.keywords:
            if kw.arg is None:
                raise ValueError(
                    "Dynamic API keyword unpacking found. "
                    "Manual review is required."
                )

            keyword_expressions[kw.arg] = (
                ast.unparse(kw.value)
            )

        calls.append({
            "line": node.lineno,
            "keyword_expressions": keyword_expressions,
            "explicit_keywords": sorted(
                keyword_expressions
            ),
        })

    return calls


def main():
    if OUTPUT.exists():
        raise FileExistsError(
            "Evaluation protocol freeze already exists. "
            "It will not be overwritten."
        )

    policy_freeze = (
        FREEZE_DIR / "esdsa_v2_policy_freeze.json"
    )

    if not policy_freeze.exists():
        raise FileNotFoundError(
            "The ESDSA v2 policy must be frozen first."
        )

    scripts = {}

    for filename, expected in EXPECTED_SCRIPTS.items():
        path = ((ROOT / "archive/frozen_originals") if filename.endswith(".py") else ROOT) / filename

        if not path.is_file():
            raise FileNotFoundError(filename)

        source = path.read_text(encoding="utf-8")
        actual_hash = sha256_file(path)

        if actual_hash != expected["sha256"]:
            raise ValueError(
                f"Script changed since inspection: {filename}\n"
                f"Expected: {expected['sha256']}\n"
                f"Actual:   {actual_hash}"
            )

        tree = ast.parse(source)
        constants = get_constants(tree)

        model = constants.get("MODEL")

        if model != "gpt-5.4-mini":
            raise ValueError(
                f"Unexpected requested model: {filename}: {model}"
            )

        prompt_name = expected["prompt_name"]
        prompt = constants.get(prompt_name)

        if not isinstance(prompt, str):
            raise ValueError(
                f"Missing prompt constant: {filename}"
            )

        prompt_hash = sha256_bytes(
            prompt.encode("utf-8")
        )

        if prompt_hash != expected["prompt_sha256"]:
            raise ValueError(
                f"Prompt changed: {filename}"
            )

        api_calls = get_api_calls(tree)

        if len(api_calls) != 1:
            raise ValueError(
                f"Expected one Responses API call in {filename}; "
                f"found {len(api_calls)}"
            )

        api_keywords = set(
            api_calls[0]["explicit_keywords"]
        )

        if not {"model", "instructions", "input", "text", "store"}.issubset(
            api_keywords
        ):
            raise ValueError(
                f"Unexpected API call structure: {filename}"
            )

        explicitly_set = {
            name: name in api_keywords
            for name in [
                "temperature",
                "top_p",
                "seed",
                "max_output_tokens",
                "reasoning",
            ]
        }

        if any(
            explicitly_set[name]
            for name in ["temperature", "top_p", "seed"]
        ):
            raise ValueError(
                f"Sampling configuration has changed: {filename}"
            )

        scripts[filename] = {
            "sha256": actual_hash,
            "requested_model": model,
            "prompt_variable": prompt_name,
            "prompt_length": len(prompt),
            "prompt_sha256": prompt_hash,
            "expected_output_format": expected[
                "output_format"
            ],
            "api_calls": api_calls,
            "explicit_sampling_parameters": explicitly_set,
            "returned_model_version": (
                "Not established by this source-code audit"
            ),
        }

    supplementary = [
        "data/benchmark/scenario_registry_v2.csv",
        "data/benchmark/benchmark_specification_v1.json",
        "data/benchmark/rubrics_v1/rubric_manifest.json",
        "results/scoring_baseline_108_v1.jsonl",
        "results/integrated_esdsa_v2.json",
    ]

    supplementary_hashes = {}

    for filename in supplementary:
        path = ((ROOT / "archive/frozen_originals") if filename.endswith(".py") else ROOT) / filename

        if path.is_file():
            supplementary_hashes[filename] = (
                sha256_file(path)
            )

    manifest = {
        "name": "ESDSA evaluation protocol",
        "version": "v1-pre-validation-freeze",
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "policy_freeze_sha256": sha256_file(
            policy_freeze
        ),
        "scope": [
            "Synthetic response-generation implementation",
            "Evidence-aware evaluator implementation",
            "Scoring-only evaluator implementation",
            "Original model prompt fingerprints",
            "Explicit Responses API call arguments",
        ],
        "model_protocol": {
            "requested_model": "gpt-5.4-mini",
            "temperature": "not explicitly supplied",
            "top_p": "not explicitly supplied",
            "seed": "not explicitly supplied",
            "model_output_repeatability": (
                "Not guaranteed by this freeze"
            ),
        },
        "scripts": scripts,
        "supplementary_file_sha256": supplementary_hashes,
        "development": {
            "scenario_families": 12,
            "responses": 108,
            "policy_refined_after_development_analysis": True,
        },
        "held_out": {
            "planned_validation_families": 24,
            "planned_test_families": 24,
            "validation_responses_generated": False,
            "test_responses_generated": False,
        },
        "limitations": [
            "Source-code hashes preserve the inspected "
            "implementations but do not prove how the API "
            "executed historical requests.",
            "The precise returned model version should "
            "be obtained from original saved API records.",
            "The complete benchmark-generation payload "
            "and annotation protocol still require "
            "verification before held-out evaluation.",
            "The ESDSA v2 policy was refined on "
            "development data, not preregistered.",
            "This protocol freeze does not establish "
            "independent human reference validation.",
        ],
    }

    FREEZE_DIR.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        json.dumps(
            manifest, indent=2, ensure_ascii=False
        ),
        encoding="utf-8",
    )

    print("ESDSA EVALUATION PROTOCOL FREEZE")
    print("=" * 65)
    print("Requested model: gpt-5.4-mini")
    print("Original scripts verified:", len(scripts))
    print("Original prompts verified:", len(scripts))
    print("Temperature: NOT EXPLICITLY SET")
    print("top_p: NOT EXPLICITLY SET")
    print("Seed: NOT EXPLICITLY SET")
    print("Original experiment files modified: NO")
    print("API calls: NONE")
    print()
    print("Saved:", OUTPUT)
    print()
    print(
        "Reminder: Historical returned model versions, "
        "generation payloads and reference procedures "
        "still need verification."
    )


if __name__ == "__main__":
    main()
