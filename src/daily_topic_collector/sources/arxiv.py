from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from time import sleep
from xml.etree import ElementTree

from ..http import HttpClient
from ..models import NormalizedEntry, SourceName
from .base import PipelineContext, build_queries, clean_url, dedupe_entries, summarize_and_tag


ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


@dataclass(frozen=True)
class ArxivPipeline:
    http: HttpClient
    source: SourceName = SourceName.ARXIV

    def run(self, context: PipelineContext) -> tuple[list[str], list[NormalizedEntry], int]:
        queries = build_queries(context.ollama, self.source.value, context.request.topic, context.request.day)
        raw_entries: list[ElementTree.Element] = []
        for index, query in enumerate(queries):
            if index > 0:
                sleep(3)
            raw_entries.extend(self._fetch(query, context.request.day))
        normalized = [self._normalize(entry, context) for entry in raw_entries]
        previous_keys = context.storage.load_previous_dedupe_keys(context.request.day, self.source)
        deduped, removed = dedupe_entries(normalized, previous_keys)
        return queries, deduped, removed

    def _fetch(self, query: str, day: date) -> list[ElementTree.Element]:
        day_from = day.strftime("%Y%m%d0000")
        day_to = day.strftime("%Y%m%d2359")
        phrase = query.replace('"', '').strip()
        search_query = (
            f'(ti:"{phrase}" OR abs:"{phrase}" OR all:{phrase}) '
            f'AND submittedDate:[{day_from}+TO+{day_to}]'
        )
        response = self.http.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": search_query,
                "start": "0",
                "max_results": "50",
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
        )
        root = ElementTree.fromstring(response.text)
        return list(root.findall("atom:entry", ATOM_NS))

    def _normalize(self, entry: ElementTree.Element, context: PipelineContext) -> NormalizedEntry:
        id_text = self._text(entry, "atom:id")
        title = self._normalize_space(self._text(entry, "atom:title"))
        summary_text = self._normalize_space(self._text(entry, "atom:summary"))
        published_text = self._text(entry, "atom:published")
        published_at = datetime.fromisoformat(published_text.replace("Z", "+00:00"))
        url = clean_url(id_text.replace("http://", "https://"))
        arxiv_id = url.rsplit("/", 1)[-1]
        summary, tags = summarize_and_tag(
            context.ollama,
            self.source.value,
            context.request.topic,
            title,
            summary_text,
        )
        return NormalizedEntry(
            id=f"arxiv:{arxiv_id}",
            source=self.source,
            topic=context.request.topic,
            url=url,
            title=title,
            summary=summary,
            tags=tags,
            created_at=published_at,
            collected_at=context.collected_at,
            dedupe_key=f"arxiv:{arxiv_id}",
        )

    def _text(self, element: ElementTree.Element, path: str) -> str:
        found = element.find(path, ATOM_NS)
        if found is None or found.text is None:
            return ""
        return found.text

    def _normalize_space(self, text: str) -> str:
        return " ".join(text.split())
