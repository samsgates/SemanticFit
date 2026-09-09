from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.config import settings


SYSTEM_PROMPT = """You extract shopping intent for a fashion semantic search system.
Return ONLY valid JSON. Never invent constraints the user did not provide.
Schema: {semantic_query:string, occasion:string[], season:string[], weather:string[], style:string[], materials:string[], colors:string[], min_price:number|null, max_price:number|null, min_rating:number|null, exclude:string[]}.
Keep semantic_query concise and faithful to the user."""


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


class LLMProvider(ABC):
    @abstractmethod
    def parse_intent(self, query: str) -> dict[str, Any]: ...


class OpenAICompatibleProvider(LLMProvider):
    def parse_intent(self, query: str) -> dict[str, Any]:
        base = settings.llm_base_url.rstrip("/") or "https://api.openai.com/v1"
        headers = {"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"}
        payload = {
            "model": settings.llm_model or "gpt-4.1-mini",
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            "response_format": {"type": "json_object"},
        }
        response = httpx.post(f"{base}/chat/completions", headers=headers, json=payload, timeout=settings.llm_timeout_seconds)
        response.raise_for_status()
        return _extract_json(response.json()["choices"][0]["message"]["content"])


class GeminiProvider(LLMProvider):
    def parse_intent(self, query: str) -> dict[str, Any]:
        model = settings.llm_model or "gemini-2.5-flash"
        base = settings.llm_base_url.rstrip("/") or "https://generativelanguage.googleapis.com/v1beta"
        url = f"{base}/models/{model}:generateContent?key={settings.llm_api_key}"
        payload = {
            "contents": [{"parts": [{"text": SYSTEM_PROMPT + "\nUSER: " + query}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        response = httpx.post(url, json=payload, timeout=settings.llm_timeout_seconds)
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return _extract_json(text)


class AnthropicProvider(LLMProvider):
    def parse_intent(self, query: str) -> dict[str, Any]:
        base = settings.llm_base_url.rstrip("/") or "https://api.anthropic.com/v1"
        headers = {
            "x-api-key": settings.llm_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": settings.llm_model or "claude-sonnet-4-5",
            "max_tokens": 500,
            "temperature": 0,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": query}],
        }
        response = httpx.post(f"{base}/messages", headers=headers, json=payload, timeout=settings.llm_timeout_seconds)
        response.raise_for_status()
        return _extract_json(response.json()["content"][0]["text"])


class OllamaProvider(LLMProvider):
    def parse_intent(self, query: str) -> dict[str, Any]:
        base = settings.llm_base_url.rstrip("/") or "http://localhost:11434"
        payload = {
            "model": settings.llm_model or "qwen3:8b",
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
        }
        response = httpx.post(f"{base}/api/chat", json=payload, timeout=settings.llm_timeout_seconds)
        response.raise_for_status()
        return _extract_json(response.json()["message"]["content"])


def provider() -> LLMProvider | None:
    if not settings.llm_enabled:
        return None
    name = settings.llm_provider.lower().strip()
    if name in {"openai", "openai_compatible"}:
        return OpenAICompatibleProvider()
    if name == "gemini":
        return GeminiProvider()
    if name in {"anthropic", "claude"}:
        return AnthropicProvider()
    if name == "ollama":
        return OllamaProvider()
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
