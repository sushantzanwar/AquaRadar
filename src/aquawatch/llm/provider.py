"""Template-only, local, or remote completion. Failures stay visible."""

from __future__ import annotations

import json
import urllib.request

from aquawatch.settings import Settings


class TemplateProvider:
    name = "none"

    def complete(self, prompt: str) -> str:
        return ""


class HttpProvider:
    def __init__(self, name: str, base_url: str, model: str, api_key: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model = model or "local"
        self.api_key = api_key

    def complete(self, prompt: str) -> str:
        if not self.base_url:
            raise RuntimeError("LLM base URL is empty")
        if self.base_url.endswith("/api/generate"):
            return self._ollama(prompt)
        return self._chat(prompt)

    def _chat(self, prompt: str) -> str:
        url = self.base_url if self.base_url.endswith("completions") else self.base_url + "/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
        return _post(url, payload, self.api_key)["choices"][0]["message"]["content"]

    def _ollama(self, prompt: str) -> str:
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        return _post(self.base_url, payload, self.api_key)["response"]


def _post(url: str, payload: dict, api_key: str) -> dict:
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


def build_provider(settings: Settings):
    name = (settings.llm_provider or "none").lower()
    # Gemini is not used. Unknown names, including gemini, stay on the local corpus and platform series.
    if name in {"none", "gemini"} or name not in {"local", "api"}:
        return TemplateProvider()
    return HttpProvider(name, settings.llm_base_url, settings.llm_model, settings.llm_api_key)
