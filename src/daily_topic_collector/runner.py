from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .http import HttpClient
from .models import CollectRequest, Manifest, NormalizedEntry, SourceName
from .ollama import OllamaClient, OllamaConfig
from .storage import Storage
from .sources import ArxivPipeline, HackerNewsPipeline, HatenaPipeline, RedditConfig, RedditPipeline
from .sources.base import PipelineContext, SourcePipeline


@dataclass(frozen=True)
class RunResult:
    queries: list[str]
    items: list[NormalizedEntry]
    manifest: Manifest


class CollectorRunner:
    def __init__(self, http: HttpClient | None = None) -> None:
        self._http = http or HttpClient()

    def run(self, request: CollectRequest) -> RunResult:
        storage = Storage(request.data_dir)
        storage.write_request(request)
        started_at = datetime.now(timezone.utc)
        collected_at = started_at
        pipeline = self._pipeline_for(request.source)
        context = PipelineContext(
            request=request,
            collected_at=collected_at,
            storage=storage,
            ollama=OllamaClient(self._http, OllamaConfig.from_env()),
        )
        try:
            queries, items, deduped_count = pipeline.run(context)
            storage.write_queries(request.day, request.source, queries)
            storage.write_items(request.day, request.source, items)
            finished_at = datetime.now(timezone.utc)
            manifest = Manifest(
                topic=request.topic,
                day=request.day,
                source=request.source,
                started_at=started_at,
                finished_at=finished_at,
                queries=queries,
                fetched_count=len(items) + deduped_count,
                normalized_count=len(items) + deduped_count,
                deduped_count=deduped_count,
                saved_count=len(items),
                status="success",
                error=None,
            )
            storage.write_manifest(manifest)
            return RunResult(queries=queries, items=items, manifest=manifest)
        except Exception as exc:
            finished_at = datetime.now(timezone.utc)
            manifest = Manifest(
                topic=request.topic,
                day=request.day,
                source=request.source,
                started_at=started_at,
                finished_at=finished_at,
                queries=[],
                fetched_count=0,
                normalized_count=0,
                deduped_count=0,
                saved_count=0,
                status="failed",
                error=str(exc),
            )
            storage.write_manifest(manifest)
            raise

    def _pipeline_for(self, source: SourceName) -> SourcePipeline:
        if source is SourceName.ARXIV:
            return ArxivPipeline(http=self._http)
        if source is SourceName.HACKER_NEWS:
            return HackerNewsPipeline(http=self._http)
        if source is SourceName.REDDIT:
            return RedditPipeline(http=self._http, config=RedditConfig.from_env())
        if source is SourceName.HATENA:
            return HatenaPipeline(http=self._http)
        raise ValueError(f"Unsupported source: {source}")
