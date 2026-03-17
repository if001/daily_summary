from __future__ import annotations

from datetime import date
from pydantic import BaseModel, Field


class CollectedItem(BaseModel):
    source: str
    title: str
    url: str
    summary: str = ""
    score: int | None = None
    created_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class RawCollection(BaseModel):
    run_date: date
    items: list[CollectedItem]


class SummaryOutput(BaseModel):
    bullets: list[str] = Field(min_length=3, max_length=10)


class TagOutput(BaseModel):
    tags: list[str] = Field(min_length=3, max_length=20)


class ReportOutput(BaseModel):
    title: str
    body_markdown: str
