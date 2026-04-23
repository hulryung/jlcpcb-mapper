"""Golden-file regression test infrastructure.

Each `cases/*.yaml` describes input for one pipeline run. The harness
runs the pipeline, normalizes the resulting groups.jsonl (strips
timestamp_ms), and compares to the matching `expected/*.jsonl`.

Run `pytest tests/golden/ --update-golden` to regenerate expected files.
"""
from pathlib import Path
import json


CASES_DIR = Path(__file__).parent / "cases"
EXPECTED_DIR = Path(__file__).parent / "expected"

# NOTE: --update-golden is registered in tests/conftest.py (root) so it is
# visible whether pytest is invoked from the repo root or tests/golden/.


def normalize_jsonl(jsonl_text: str) -> str:
    """Strip timestamp_ms (non-deterministic) for stable comparison."""
    out = []
    for line in jsonl_text.splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        for e in obj.get("events", []):
            e["timestamp_ms"] = 0
        out.append(json.dumps(obj, ensure_ascii=False, sort_keys=True))
    return "\n".join(out)


def pytest_generate_tests(metafunc):
    if "golden_case" in metafunc.fixturenames:
        cases = sorted(CASES_DIR.glob("*.yaml")) if CASES_DIR.exists() else []
        if cases:
            metafunc.parametrize("golden_case", cases, ids=[c.stem for c in cases])
        else:
            metafunc.parametrize("golden_case", [], ids=[])
