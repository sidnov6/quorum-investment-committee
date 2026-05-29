"""Pluggable LLM router with a deterministic fallback.

Goal: the committee ALWAYS runs. If a provider key exists (Gemini/Groq/OpenAI/
Anthropic), agents reason with a real LLM. If none exist, callers fall back to the
deterministic agent logic (see committee.agents). This module only handles the
"call an LLM" path and a failover chain; it raises NoLLMAvailable when there is no
provider, which the agents catch to switch to deterministic mode.
"""
from __future__ import annotations

import json
from typing import Optional

import httpx

from quorum.config import settings


class NoLLMAvailable(Exception):
    pass


def available_providers() -> list[str]:
    chain = []
    if settings.GEMINI_API_KEY:
        chain.append("gemini")
    if settings.GROQ_API_KEY:
        chain.append("groq")
    if settings.OPENAI_API_KEY:
        chain.append("openai")
    if settings.ANTHROPIC_API_KEY:
        chain.append("anthropic")
    if settings.LLM_PROVIDER != "auto" and settings.LLM_PROVIDER in chain:
        # honour explicit preference first
        chain.remove(settings.LLM_PROVIDER)
        chain.insert(0, settings.LLM_PROVIDER)
    return chain


def llm_enabled() -> bool:
    return len(available_providers()) > 0


def _call_gemini(system: str, prompt: str, json_mode: bool) -> str:
    model = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4},
    }
    if json_mode:
        body["generationConfig"]["response_mime_type"] = "application/json"
    r = httpx.post(
        url, params={"key": settings.GEMINI_API_KEY}, json=body, timeout=settings.LLM_TIMEOUT
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call_openai_compatible(base: str, key: str, model: str, system: str, prompt: str, json_mode: bool) -> str:
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "temperature": 0.4,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json=body,
        timeout=settings.LLM_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _call_anthropic(system: str, prompt: str) -> str:
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 2048,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=settings.LLM_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"]


def complete(system: str, prompt: str, json_mode: bool = False) -> tuple[str, str]:
    """Return (text, model_name). Fails over across providers. Raises NoLLMAvailable."""
    chain = available_providers()
    if not chain:
        raise NoLLMAvailable()
    last_err: Optional[Exception] = None
    for provider in chain:
        try:
            if provider == "gemini":
                return _call_gemini(system, prompt, json_mode), "gemini-1.5-flash"
            if provider == "groq":
                return (
                    _call_openai_compatible(
                        "https://api.groq.com/openai/v1", settings.GROQ_API_KEY,
                        "llama-3.3-70b-versatile", system, prompt, json_mode,
                    ),
                    "groq/llama-3.3-70b",
                )
            if provider == "openai":
                return (
                    _call_openai_compatible(
                        "https://api.openai.com/v1", settings.OPENAI_API_KEY,
                        "gpt-4o-mini", system, prompt, json_mode,
                    ),
                    "openai/gpt-4o-mini",
                )
            if provider == "anthropic":
                return _call_anthropic(system, prompt), "anthropic/claude-haiku-4-5"
        except Exception as e:  # failover to next provider
            last_err = e
            continue
    raise NoLLMAvailable(str(last_err) if last_err else "all providers failed")


def complete_json(system: str, prompt: str, fallback: dict) -> tuple[dict, str]:
    """LLM JSON call with safe parsing; returns (dict, model). Caller handles NoLLMAvailable."""
    text, model = complete(system, prompt, json_mode=True)
    try:
        start = text.find("{")
        end = text.rfind("}")
        return json.loads(text[start : end + 1]), model
    except Exception:
        return fallback, model
