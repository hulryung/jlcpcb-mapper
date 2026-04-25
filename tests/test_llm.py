import json
from unittest.mock import patch, MagicMock
from jlcpcb_mapper.io.llm import ClaudeClient, LLMError

def _mock_run(output: str, returncode: int = 0):
    cp = MagicMock()
    cp.stdout = output
    cp.stderr = ""
    cp.returncode = returncode
    return cp

def test_pick_one_returns_parsed_json():
    client = ClaudeClient(model="claude-haiku-4-5", timeout=10)
    payload = {"result": json.dumps({"lcsc": "C17168", "reason": "basic, high stock"})}
    with patch("subprocess.run", return_value=_mock_run(json.dumps(payload))):
        resp = client.call("choose a part: ...", schema_keys=["lcsc", "reason"])
    assert resp.data["lcsc"] == "C17168"

def test_pick_one_retries_on_parse_fail_then_raises():
    client = ClaudeClient(model="claude-haiku-4-5", timeout=10, retry=1)
    bad = _mock_run(json.dumps({"result": "not valid json at all"}))
    with patch("subprocess.run", return_value=bad):
        raised = False
        try:
            client.call("...", schema_keys=["lcsc"])
        except LLMError:
            raised = True
        assert raised, "expected LLMError"

def test_pick_one_strips_markdown_json_fence():
    """Haiku 4.5 sometimes wraps JSON in ```json ... ``` even when told not to.
    The client must strip the fence before parsing.
    """
    client = ClaudeClient(model="claude-haiku-4-5", timeout=10)
    fenced_inner = '```json\n{"lcsc": "C1525", "reason": "basic, high stock"}\n```'
    payload = {"result": fenced_inner}
    with patch("subprocess.run", return_value=_mock_run(json.dumps(payload))):
        resp = client.call("...", schema_keys=["lcsc", "reason"])
    assert resp.data["lcsc"] == "C1525"
    assert resp.data["reason"] == "basic, high stock"


def test_pick_one_strips_bare_fence_without_language_tag():
    client = ClaudeClient(model="claude-haiku-4-5", timeout=10)
    fenced_inner = '```\n{"lcsc": "C42", "reason": "x"}\n```'
    payload = {"result": fenced_inner}
    with patch("subprocess.run", return_value=_mock_run(json.dumps(payload))):
        resp = client.call("...", schema_keys=["lcsc", "reason"])
    assert resp.data["lcsc"] == "C42"


def test_smoke_check_passes_on_zero_exit():
    client = ClaudeClient(model="m", timeout=5)
    with patch("subprocess.run", return_value=_mock_run("ok")):
        assert client.smoke_check() is True

def test_smoke_check_fails_on_nonzero():
    client = ClaudeClient(model="m", timeout=5)
    with patch("subprocess.run", return_value=_mock_run("err", returncode=1)):
        assert client.smoke_check() is False
