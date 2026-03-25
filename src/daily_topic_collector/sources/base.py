from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol, Sequence
from urllib.parse import urlparse, urlunparse

from ..models import CollectRequest, NormalizedEntry, QueryPlan, SourceName
from ..ollama import OllamaClient, fallback_queries, fallback_summary_and_tags
from ..storage import Storage


@dataclass(frozen=True)
class PipelineContext:
    request: CollectRequest
    collected_at: datetime
    storage: Storage
    ollama: OllamaClient | None


class SourcePipeline(Protocol):
    source: SourceName

    def run(self, context: PipelineContext) -> tuple[list[str], list[NormalizedEntry], int]:
        ...


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clean_url(url: str) -> str:
    parsed = urlparse(url)
    query_pairs = []
    for pair in parsed.query.split("&"):
        if not pair:
            continue
        if pair.startswith("utm_"):
            continue
        query_pairs.append(pair)
    cleaned_query = "&".join(query_pairs)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, cleaned_query, ""))


def build_queries(ollama: OllamaClient | None, source: str, topic: str, day: date) -> list[str]:
    if ollama is None:
        return fallback_queries(topic)
    try:
        queries = ollama.build_queries(source=source, topic=topic, day_iso=day.isoformat())
        return queries if queries else fallback_queries(topic)
    except Exception:
        return fallback_queries(topic)


def summarize_and_tag(ollama: OllamaClient | None, source: str, topic: str, title: str, text: str) -> tuple[str, list[str]]:
    if ollama is None:
        return fallback_summary_and_tags(title=title, text=text)
    try:
        return ollama.summarize_and_tag(source=source, topic=topic, title=title, text=text)
    except Exception:
        return fallback_summary_and_tags(title=title, text=text)


def dedupe_entries(entries: Sequence[NormalizedEntry], previous_keys: set[str]) -> tuple[list[NormalizedEntry], int]:
    seen: set[str] = set(previous_keys)
    result: list[NormalizedEntry] = []
    removed = 0
    for entry in entries:
        if entry.dedupe_key in seen:
            removed += 1
            continue
        seen.add(entry.dedupe_key)
        result.append(entry)
    return result, removed
