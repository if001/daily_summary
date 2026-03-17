from __future__ import annotations

from langchain.tools import tool

from .clients import SourceClient, default_arxiv_query
from .config import Settings
from .models import CollectedItem


class CollectionTools:
    def __init__(self, settings: Settings, client: SourceClient) -> None:
        self._settings = settings
        self._client = client

    @tool
    def collect_arxiv(self) -> list[dict[str, str | int | list[str] | None]]:
        """Collect recent arXiv papers in AI/ML/software-related categories."""
        items = self._client.arxiv_recent(default_arxiv_query(), self._settings.max_items_per_source)
        return [self._item_to_tool_payload(item) for item in items]

    @tool
    def collect_hackernews(self) -> list[dict[str, str | int | list[str] | None]]:
        """Collect top Hacker News stories."""
        items = self._client.hackernews_top(self._settings.max_items_per_source)
        return [self._item_to_tool_payload(item) for item in items]

    @tool
    def collect_hatena(self) -> list[dict[str, str | int | list[str] | None]]:
        """Collect Hatena Bookmark hot entries for technology."""
        items = self._client.hatena_hotentry_it(self._settings.max_items_per_source)
        return [self._item_to_tool_payload(item) for item in items]

    @tool
    def collect_reddit(self) -> list[dict[str, str | int | list[str] | None]]:
        """Collect Reddit best posts from r/MachineLearning and r/programming."""
        if self._settings.reddit is None:
            return []
        items: list[CollectedItem] = []
        items.extend(
            self._client.reddit_best(
                self._settings.reddit,
                subreddit="MachineLearning",
                limit=max(1, self._settings.max_items_per_source // 2),
            )
        )
        items.extend(
            self._client.reddit_best(
                self._settings.reddit,
                subreddit="programming",
                limit=max(1, self._settings.max_items_per_source // 2),
            )
        )
        return [self._item_to_tool_payload(item) for item in items]

    @staticmethod
    def _item_to_tool_payload(item: CollectedItem) -> dict[str, str | int | list[str] | None]:
        return {
            "source": item.source,
            "title": item.title,
            "url": item.url,
            "summary": item.summary,
            "score": item.score,
            "created_at": item.created_at,
            "tags": item.tags,
        }
