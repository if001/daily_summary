from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from ..http import HttpClient
from ..models import NormalizedEntry, SourceName
from .base import PipelineContext, build_queries, clean_url, dedupe_entries, summarize_and_tag


@dataclass(frozen=True)
class HatenaPipeline:
    http: HttpClient
    feeds: tuple[str, ...] = (
        "https://b.hatena.ne.jp/hotentry/it.rss",
        "https://b.hatena.ne.jp/hotentry.rss",
    )
    source: SourceName = SourceName.HATENA

    def run(self, context: PipelineContext) -> tuple[list[str], list[NormalizedEntry], int]:
        queries = build_queries(context.ollama, self.source.value, context.request.topic, context.request.day)
        raw_items: list[ElementTree.Element] = []
        for feed in self.feeds:
            raw_items.extend(self._fetch(feed))
        normalized: list[NormalizedEntry] = []
        for item in raw_items:
            created_at = self._pub_date(item)
            if created_at.date() != context.request.day:
                continue
            if not self._matches(item, queries):
                continue
            normalized.append(self._normalize(item, context))
        previous_keys = context.storage.load_previous_dedupe_keys(context.request.day, self.source)
        deduped, removed = dedupe_entries(normalized, previous_keys)
        return queries, deduped, removed

    def _fetch(self, feed_url: str) -> list[ElementTree.Element]:
        response = self.http.get(feed_url)
        root = ElementTree.fromstring(response.text)
        channel = root.find("channel")
        if channel is None:
            return []
        return list(channel.findall("item"))

    def _matches(self, item: ElementTree.Element, queries: list[str]) -> bool:
        searchable = " ".join(
            value for value in [self._text(item, "title"), self._text(item, "description"), self._text(item, "link")] if value
        ).lower()
        return any(query.lower() in searchable for query in queries)

    def _normalize(self, item: ElementTree.Element, context: PipelineContext) -> NormalizedEntry:
        title = self._text(item, "title") or "hatena"
        link = clean_url(self._text(item, "link"))
        description = self._text(item, "description")
        guid = self._text(item, "guid") or link
        summary, tags = summarize_and_tag(
            context.ollama,
            self.source.value,
            context.request.topic,
            title,
            description or link,
        )
        return NormalizedEntry(
            id=f"hatena:{guid}",
            source=self.source,
            topic=context.request.topic,
            url=link,
            title=title,
            summary=summary,
            tags=tags,
            created_at=self._pub_date(item),
            collected_at=context.collected_at,
            dedupe_key=f"hatena:{link}",
        )

    def _pub_date(self, item: ElementTree.Element) -> datetime:
        value = self._text(item, "pubDate")
        if not value:
            return datetime.fromtimestamp(0, tz=timezone.utc)
        parsed = parsedate_to_datetime(value)
        return parsed.astimezone(timezone.utc)

    def _text(self, item: ElementTree.Element, key: str) -> str:
        found = item.find(key)
        if found is None or found.text is None:
            return ""
        return found.text.strip()
