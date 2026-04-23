from __future__ import annotations
from dataclasses import dataclass
import json
import subprocess


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
                data = json.loads(inner) if isinstance(inner, str) else inner
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
