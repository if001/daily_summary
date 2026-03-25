from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import html

from ..http import HttpClient
from ..models import NormalizedEntry, SourceName
from .base import PipelineContext, build_queries, clean_url, dedupe_entries, summarize_and_tag


@dataclass(frozen=True)
class HackerNewsPipeline:
    http: HttpClient
    max_story_scan: int = 120
    source: SourceName = SourceName.HACKER_NEWS

    def run(self, context: PipelineContext) -> tuple[list[str], list[NormalizedEntry], int]:
        queries = build_queries(context.ollama, self.source.value, context.request.topic, context.request.day)
        story_ids = self._candidate_story_ids()
        normalized: list[NormalizedEntry] = []
        for story_id in story_ids[: self.max_story_scan]:
            item = self._fetch_item(story_id)
            created_at = self._item_datetime(item)
            if created_at.date() != context.request.day:
                continue
            if not self._matches(item, queries):
                continue
            normalized.append(self._normalize(item, context))
        previous_keys = context.storage.load_previous_dedupe_keys(context.request.day, self.source)
        deduped, removed = dedupe_entries(normalized, previous_keys)
        return queries, deduped, removed

    def _candidate_story_ids(self) -> list[int]:
        top = self.http.get("https://hacker-news.firebaseio.com/v0/topstories.json").json_value()
        new = self.http.get("https://hacker-news.firebaseio.com/v0/newstories.json").json_value()
        values: list[int] = []
        for group in (top, new):
            if isinstance(group, list):
                for item in group:
                    if isinstance(item, int) and item not in values:
                        values.append(item)
        return values

    def _fetch_item(self, item_id: int) -> dict[str, object]:
        payload = self.http.get(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json").json_dict()
        return payload

    def _item_datetime(self, item: dict[str, object]) -> datetime:
        timestamp = item.get("time")
        if not isinstance(timestamp, int):
            return datetime.fromtimestamp(0, tz=timezone.utc)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    def _matches(self, item: dict[str, object], queries: list[str]) -> bool:
        title = item.get("title")
        text = item.get("text")
        url = item.get("url")
        searchable = " ".join(
            value for value in [title, text, url] if isinstance(value, str)
        ).lower()
        return any(query.lower() in searchable for query in queries)

    def _normalize(self, item: dict[str, object], context: PipelineContext) -> NormalizedEntry:
        item_id = item.get("id")
        if not isinstance(item_id, int):
            raise ValueError("Hacker News item is missing id")
        title = item.get("title")
        title_text = title if isinstance(title, str) else f"HN item {item_id}"
        body = item.get("text")
        text_body = html.unescape(body) if isinstance(body, str) else ""
        url = item.get("url")
        target_url = clean_url(url) if isinstance(url, str) and url else f"https://news.ycombinator.com/item?id={item_id}"
        summary, tags = summarize_and_tag(
            context.ollama,
            self.source.value,
            context.request.topic,
            title_text,
            text_body or target_url,
        )
        created_at = self._item_datetime(item)
        return NormalizedEntry(
            id=f"hn:{item_id}",
            source=self.source,
            topic=context.request.topic,
            url=target_url,
            title=title_text,
            summary=summary,
            tags=tags,
            created_at=created_at,
            collected_at=context.collected_at,
            dedupe_key=f"hn:{item_id}",
        )
