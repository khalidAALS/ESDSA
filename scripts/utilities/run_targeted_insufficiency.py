
# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

import sys
from pathlib import Path

import run_benchmark_evaluator as evaluator

evaluator.INPUT = Path(
    "data/benchmark/targeted_insufficiency_v1.csv"
)

evaluator.OUTPUT = Path(
    "results/targeted_insufficiency_evaluations_v1.jsonl"
)


import inspect

source = inspect.getsource(evaluator.main)

old = 'if len(rows) != 108:'
new = 'if len(rows) != 12:'

if source.count(old) != 1:
    raise RuntimeError(
        "Expected response-count check not found. "
        "Review the evaluator before proceeding."
    )

source = source.replace(old, new)

namespace = dict(vars(evaluator))
exec(source, namespace)

sys.argv = [
    "run_targeted_insufficiency.py",
    "--run"
]

namespace["main"]()
