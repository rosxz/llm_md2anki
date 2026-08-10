"""LLM provider abstraction for the MVP.

Gemini via Google AI Studio is the default because it matches the user's
intended free-tier key flow.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class GenerationResult:
    text: str
    meta: dict[str, Any]


class Provider(Protocol):
    def generate(self, prompt: str) -> GenerationResult:
        ...


class GeminiProvider:
    def __init__(self, api_key: str | None = None, model: str = "gemini-2.0-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.model = model

    def generate(self, prompt: str) -> GenerationResult:
        if not self.api_key:
            raise RuntimeError(
                "Missing Gemini API key. Set GEMINI_API_KEY or GOOGLE_API_KEY, or pass --api-key."
            )

        try:
            from google import genai
        except Exception as exc:  # pragma: no cover - import error depends on environment
            raise RuntimeError(
                "google-genai is not installed. Install dependencies with 'pip install -r requirements.txt'."
            ) from exc

        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(model=self.model, contents=prompt)
        text = getattr(response, "text", None) or ""
        meta = {}
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            meta["usage"] = {
                "prompt_tokens": getattr(usage, "prompt_token_count", None),
                "completion_tokens": getattr(usage, "candidates_token_count", None),
                "total_tokens": getattr(usage, "total_token_count", None),
            }
        return GenerationResult(text=text.strip(), meta=meta)


class StaticProvider:
    """Provider used for tests and offline dry-runs."""

    def __init__(self, response: str):
        self.response = response

    def generate(self, prompt: str) -> GenerationResult:
        return GenerationResult(text=self.response, meta={"prompt": prompt})


class SequenceProvider:
    """Provider that returns a different response each call.

    Useful for tests that need to simulate retries or chunked processing.
    """

    def __init__(self, responses: list[str]):
        if not responses:
            raise ValueError("responses must not be empty")
        self.responses = responses
        self.index = 0

    def generate(self, prompt: str) -> GenerationResult:
        response = self.responses[min(self.index, len(self.responses) - 1)]
        self.index += 1
        return GenerationResult(text=response, meta={"prompt": prompt, "call_index": self.index})


def build_provider(name: str = "gemini", api_key: str | None = None, model: str = "gemini-2.0-flash") -> Provider:
    if name == "gemini":
        return GeminiProvider(api_key=api_key, model=model)
    raise ValueError(f"Unsupported provider: {name}")
