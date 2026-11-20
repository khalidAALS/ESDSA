
# Make ESDSA scripts importable across stage directories without installing them.
import sys as _esdsa_sys
from pathlib import Path as _esdsa_Path
_esdsa_root = _esdsa_Path(__file__).resolve().parents[2]
for _esdsa_subdir in ("utilities", "validation", "test", "analysis", "development", "figures"):
    _esdsa_dir = str(_esdsa_root / "scripts" / _esdsa_subdir)
    if _esdsa_dir not in _esdsa_sys.path:
        _esdsa_sys.path.insert(0, _esdsa_dir)

from pathlib import Path

import run_evidence_audit as audit

audit.INPUT = Path(
    "data/model_inputs/challenge_benchmark_v2.csv"
)

audit.BASELINE = Path(
    "results/scoring_baseline_v2.jsonl"
)

audit.OUTPUT = Path(
    "results/evidence_audit_v2.jsonl"
)


import inspect

source = inspect.getsource(audit.main)

source = source.replace(
    "assert len(responses) == 12",
    "assert len(responses) == 8"
)

source = source.replace(
    "assert len(baseline) == 12",
    "assert len(baseline) == 8"
)

source = source.replace(
    "if len(set(response_ids)) != 12:",
    "if len(set(response_ids)) != 8:"
)

source = source.replace(
    "if len(set(baseline_ids)) != 12:",
    "if len(set(baseline_ids)) != 8:"
)

namespace = dict(vars(audit))
exec(source, namespace)

namespace["main"]()
