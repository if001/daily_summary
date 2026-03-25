from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Sequence

from .http import HttpClient


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str
    small_model: str

    @classmethod
    def from_env(cls) -> "OllamaConfig":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        small_model = os.environ.get("OLLAMA_SMALL_MODEL", "qwen2.5:3b")
        return cls(base_url=base_url.rstrip("/"), small_model=small_model)


class OllamaClient:
    def __init__(self, http: HttpClient, config: OllamaConfig) -> None:
        self._http = http
        self._config = config

    def build_queries(self, source: str, topic: str, day_iso: str, limit: int = 5) -> list[str]:
        prompt = (
            "Return strict JSON with one key 'queries' whose value is a list of short search phrases. "
            "Make phrases useful for the source. Use the user's topic and date only as hints. "
            "No prose. No markdown. Keep each phrase short. "
            f"source={source}; day={day_iso}; topic={topic}; limit={limit}"
        )
        payload = {
            "model": self._config.small_model,
            "prompt": prompt,
            "stream": False,
            "format": {
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                    }
                },
                "required": ["queries"],
            },
        }
        response = self._http.post_json(f"{self._config.base_url}/api/generate", payload).json_dict()
        value = response.get("response")
        if not isinstance(value, str):
            return [topic]
        parsed = json.loads(value)
        queries = parsed.get("queries")
        if not isinstance(queries, list):
            return [topic]
        result: list[str] = []
        for item in queries:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    result.append(stripped)
        return result[:limit] if result else [topic]

    def summarize_and_tag(self, source: str, topic: str, title: str, text: str, max_tags: int = 5) -> tuple[str, list[str]]:
        prompt = (
            "Return strict JSON with keys 'summary' and 'tags'. "
            "summary must be one short Japanese sentence. tags must be short lowercase or Japanese tags. "
            "Do not include markdown. "
            f"source={source}; topic={topic}; title={title}; text={text[:4000]}; max_tags={max_tags}"
        )
        payload = {
            "model": self._config.small_model,
            "prompt": prompt,
            "stream": False,
            "format": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["summary", "tags"],
            },
        }
        response = self._http.post_json(f"{self._config.base_url}/api/generate", payload).json_dict()
        value = response.get("response")
        if not isinstance(value, str):
            return title, []
        parsed = json.loads(value)
        summary_raw = parsed.get("summary")
        tags_raw = parsed.get("tags")
        summary = title if not isinstance(summary_raw, str) or not summary_raw.strip() else summary_raw.strip()
        tags: list[str] = []
        if isinstance(tags_raw, list):
            for item in tags_raw:
                if isinstance(item, str):
                    stripped = item.strip()
                    if stripped:
                        tags.append(stripped)
        return summary, tags[:max_tags]


def fallback_queries(topic: str) -> list[str]:
    parts = [part.strip() for part in topic.replace("/", " ").replace("-", " ").split() if part.strip()]
    if not parts:
        return [topic]
    merged = " ".join(parts)
    unique: list[str] = [merged]
    if len(parts) > 1:
        unique.extend(parts)
    deduped: list[str] = []
    for item in unique:
        if item not in deduped:
            deduped.append(item)
    return deduped[:5]


def fallback_summary_and_tags(title: str, text: str) -> tuple[str, list[str]]:
    tokens = [part.strip(" ,./()[]{}") for part in f"{title} {text}".split()]
    tags: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if len(lowered) < 3:
            continue
        if lowered not in tags:
            tags.append(lowered)
        if len(tags) >= 5:
            break
    return title, tags
