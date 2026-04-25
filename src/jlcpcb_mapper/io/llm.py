from __future__ import annotations
from dataclasses import dataclass
import json
import re
import subprocess


_FENCE_RE = re.compile(r"^\s*```(?:json|JSON)?\s*\n(.*?)\n\s*```\s*$", re.DOTALL)


def _strip_json_fence(s: str) -> str:
    """Strip a Markdown ```json ... ``` fence if the model wrapped its output.

    Haiku 4.5 sometimes wraps short JSON outputs in fenced code blocks even
    when explicitly asked for raw JSON. The leading backtick lands at column
    0 and trips json.loads() with "Expecting value: line 1 column 1 (char 0)".
    """
    if not s:
        return s
    m = _FENCE_RE.match(s)
    if m:
        return m.group(1).strip()
    return s.strip()


class LLMError(Exception):
    pass


@dataclass
class LLMResponse:
    data: dict
    raw_stdout: str


class ClaudeClient:
    def __init__(self, model: str, timeout: int = 60, retry: int = 1):
        self.model = model
        self.timeout = timeout
        self.retry = retry

    def smoke_check(self) -> bool:
        try:
            cp = subprocess.run(
                ["claude", "-p", "say 'ok'"],
                capture_output=True, text=True, timeout=self.timeout,
            )
            return cp.returncode == 0
        except FileNotFoundError:
            return False

    def call(self, prompt: str, schema_keys: list[str]) -> LLMResponse:
        attempts = self.retry + 1
        last_err: str | None = None
        for _ in range(attempts):
            cp = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "json", "--model", self.model],
                capture_output=True, text=True, timeout=self.timeout,
            )
            if cp.returncode != 0:
                last_err = f"claude exit {cp.returncode}: {cp.stderr[:200]}"
                continue
            try:
                outer = json.loads(cp.stdout)
                inner = outer.get("result") or outer.get("content") or cp.stdout
                if isinstance(inner, str):
                    inner = _strip_json_fence(inner)
                    data = json.loads(inner)
                else:
                    data = inner
                if not isinstance(data, dict):
                    last_err = f"expected dict, got {type(data).__name__}"
                    continue
                missing = [k for k in schema_keys if k not in data]
                if missing:
                    last_err = f"missing keys: {missing}"
                    continue
                return LLMResponse(data=data, raw_stdout=cp.stdout)
            except json.JSONDecodeError as e:
                last_err = f"parse error: {e}"
                continue
        raise LLMError(last_err or "unknown LLM failure")
