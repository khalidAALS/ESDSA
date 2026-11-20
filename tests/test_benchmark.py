from esdsa.benchmark import build
from esdsa.validate import validate


def test_build_and_validate(tmp_path):
    build(tmp_path)
    output = validate(tmp_path)
    assert output["status"] == "STRUCTURE_PASS"
    assert output["semantic_review"] == "NOT_PERFORMED"


def test_reproducibility(tmp_path):
    path, labels = build(tmp_path)
    a, b = path.read_bytes(), labels.read_bytes()
    build(tmp_path)
    assert path.read_bytes() == a
    assert labels.read_bytes() == b
