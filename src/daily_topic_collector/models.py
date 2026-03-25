from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from enum import StrEnum
import json
from pathlib import Path
from typing import Iterable


class SourceName(StrEnum):
    ARXIV = "arxiv"
    HACKER_NEWS = "hacker_news"
    REDDIT = "reddit"
    HATENA = "hatena"


@dataclass(frozen=True)
class CollectRequest:
    topic: str
    day: date
    source: SourceName
    data_dir: Path


@dataclass(frozen=True)
class QueryPlan:
    source: SourceName
    topic: str
    day: date
    queries: list[str]


@dataclass(frozen=True)
class NormalizedEntry:
    id: str
    source: SourceName
    topic: str
    url: str
    title: str
    summary: str
    tags: list[str]
    created_at: datetime
    collected_at: datetime
    dedupe_key: str

    def to_json(self) -> str:
        payload = {
            "id": self.id,
            "source": self.source.value,
            "topic": self.topic,
            "url": self.url,
            "title": self.title,
            "summary": self.summary,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "collected_at": self.collected_at.isoformat(),
            "dedupe_key": self.dedupe_key,
        }
        return json.dumps(payload, ensure_ascii=False)


@dataclass(frozen=True)
class Manifest:
    topic: str
    day: date
    source: SourceName
    started_at: datetime
    finished_at: datetime
    queries: list[str]
    fetched_count: int
    normalized_count: int
    deduped_count: int
    saved_count: int
    status: str
    error: str | None

    def to_json(self) -> str:
        payload = {
            "topic": self.topic,
            "day": self.day.isoformat(),
            "source": self.source.value,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "queries": self.queries,
            "fetched_count": self.fetched_count,
            "normalized_count": self.normalized_count,
            "deduped_count": self.deduped_count,
            "saved_count": self.saved_count,
            "status": self.status,
            "error": self.error,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)


def write_json_lines(path: Path, items: Iterable[NormalizedEntry]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(item.to_json())
            handle.write("\n")
