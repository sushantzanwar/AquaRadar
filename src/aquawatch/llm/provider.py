"""Template-only, local, remote, or Gemini completion. Failures stay visible."""

from __future__ import annotations

import json
import urllib.request

from aquawatch.settings import Settings


class TemplateProvider:
    name = "none"

    def complete(self, prompt: str, history: list[dict] | None = None) -> str:
        return ""


class HttpProvider:
    def __init__(self, name: str, base_url: str, model: str, api_key: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model = model or "local"
        self.api_key = api_key

    def complete(self, prompt: str, history: list[dict] | None = None) -> str:
        if not self.base_url:
            raise RuntimeError("LLM base URL is empty")
        if self.base_url.endswith("/api/generate"):
            return self._ollama(prompt)
        return self._chat(prompt, history)

    def _chat(self, prompt: str, history: list[dict] | None = None) -> str:
        url = self.base_url if self.base_url.endswith("completions") else self.base_url + "/v1/chat/completions"
        messages = list(history or [])
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        return _post(url, payload, self.api_key)["choices"][0]["message"]["content"]

    def _ollama(self, prompt: str) -> str:
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        return _post(self.base_url, payload, self.api_key)["response"]


class GeminiProvider:
    """Google Gemini via the REST API — no SDK required, works with a free API key.

    Set LLM_PROVIDER=gemini and LLM_API_KEY=<your_key> in the environment.
    Optionally set LLM_MODEL to override (default: gemini-1.5-flash).
    Get a free key at https://aistudio.google.com/app/apikey
    """

    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        if not api_key:
            raise RuntimeError(
                "Gemini API key is missing. Set LLM_API_KEY=<your_key> in the environment. "
                "Get a free key at https://aistudio.google.com/app/apikey"
            )
        self.api_key = api_key
        self.model = model or "gemini-1.5-flash"

    def complete(self, prompt: str, history: list[dict] | None = None) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        # Build Gemini-format contents array (user/model turns)
        contents: list[dict] = []
        for msg in (history or []):
            role = "user" if msg.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        # Append the current prompt as the final user turn
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
                "topP": 0.9,
            },
        }
        result = _post(url, payload, "")
        try:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Gemini response parse error: {result}") from exc


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
    if name == "none":
        return TemplateProvider()
    if name == "gemini":
        return GeminiProvider(settings.llm_api_key, settings.llm_model or "gemini-1.5-flash")
    if name not in {"local", "api"}:
        return TemplateProvider()
    return HttpProvider(name, settings.llm_base_url, settings.llm_model, settings.llm_api_key)
