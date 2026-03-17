from __future__ import annotations

from base64 import b64encode
from datetime import UTC, datetime
from typing import Final
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET

import feedparser
import httpx
from langchain_ollama import ChatOllama

from .config import RedditConfig, Settings
from .models import CollectedItem

ARXIV_API_URL: Final[str] = "https://export.arxiv.org/api/query"
HN_BASE_URL: Final[str] = "https://hacker-news.firebaseio.com/v0"
HATENA_TECH_RSS: Final[str] = "https://b.hatena.ne.jp/hotentry/it.rss"
REDDIT_TOKEN_URL: Final[str] = "https://www.reddit.com/api/v1/access_token"
REDDIT_OAUTH_URL: Final[str] = "https://oauth.reddit.com"


class SourceClient:
    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self._client = httpx.Client(timeout=timeout_seconds, follow_redirects=True)

    def close(self) -> None:
        self._client.close()

    def arxiv_recent(self, query: str, limit: int) -> list[CollectedItem]:
        response = self._client.get(
            ARXIV_API_URL,
            params={
                "search_query": query,
                "start": 0,
                "max_results": limit,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
            headers={"User-Agent": "daily-report-agent/0.1"},
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        items: list[CollectedItem] = []
        for entry in root.findall("atom:entry", namespace):
            title = (entry.findtext("atom:title", default="", namespaces=namespace) or "").strip()
            summary = (entry.findtext("atom:summary", default="", namespaces=namespace) or "").strip()
            url = (entry.findtext("atom:id", default="", namespaces=namespace) or "").strip()
            published = (entry.findtext("atom:published", default="", namespaces=namespace) or "").strip()
            categories = [
                category.attrib.get("term", "")
                for category in entry.findall("atom:category", namespace)
                if category.attrib.get("term", "")
            ]
            items.append(
                CollectedItem(
                    source="arXiv",
                    title=title,
                    url=url,
                    summary=summary,
                    created_at=published,
                    tags=categories,
                )
            )
        return items

    def hackernews_top(self, limit: int) -> list[CollectedItem]:
        ids_response = self._client.get(f"{HN_BASE_URL}/topstories.json")
        ids_response.raise_for_status()
        story_ids = ids_response.json()
        items: list[CollectedItem] = []
        for story_id in story_ids[:limit]:
            item_response = self._client.get(f"{HN_BASE_URL}/item/{story_id}.json")
            item_response.raise_for_status()
            data = item_response.json()
            if not isinstance(data, dict):
                continue
            url = str(data.get("url") or f"https://news.ycombinator.com/item?id={story_id}")
            title = str(data.get("title") or "")
            if not title:
                continue
            score_value = data.get("score")
            score = int(score_value) if isinstance(score_value, int) else None
            unix_time = data.get("time")
            created_at = None
            if isinstance(unix_time, int):
                created_at = datetime.fromtimestamp(unix_time, tz=UTC).isoformat()
            items.append(
                CollectedItem(
                    source="Hacker News",
                    title=title,
                    url=url,
                    score=score,
                    created_at=created_at,
                )
            )
        return items

    def hatena_hotentry_it(self, limit: int) -> list[CollectedItem]:
        parsed = feedparser.parse(HATENA_TECH_RSS)
        items: list[CollectedItem] = []
        for entry in parsed.entries[:limit]:
            title = str(getattr(entry, "title", "")).strip()
            url = str(getattr(entry, "link", "")).strip()
            summary = str(getattr(entry, "summary", "")).strip()
            published = str(getattr(entry, "published", "")).strip() or None
            tags = [str(tag.term) for tag in getattr(entry, "tags", []) if hasattr(tag, "term")]
            if not title or not url:
                continue
            items.append(
                CollectedItem(
                    source="Hatena Bookmark",
                    title=title,
                    url=url,
                    summary=summary,
                    created_at=published,
                    tags=tags,
                )
            )
        return items

    def reddit_best(self, config: RedditConfig, subreddit: str, limit: int) -> list[CollectedItem]:
        token = self._reddit_access_token(config)
        response = self._client.get(
            f"{REDDIT_OAUTH_URL}/r/{subreddit}/best",
            params={"limit": limit},
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": config.user_agent,
            },
        )
        response.raise_for_status()
        data = response.json()
        items: list[CollectedItem] = []
        payload = data.get("data")
        children = payload.get("children") if isinstance(payload, dict) else None
        if not isinstance(children, list):
            return items
        for child in children:
            child_data = child.get("data") if isinstance(child, dict) else None
            if not isinstance(child_data, dict):
                continue
            title = child_data.get("title")
            permalink = child_data.get("permalink")
            if not isinstance(title, str) or not isinstance(permalink, str):
                continue
            score_value = child_data.get("score")
            score = int(score_value) if isinstance(score_value, int) else None
            created_utc = child_data.get("created_utc")
            created_at = (
                datetime.fromtimestamp(created_utc, tz=UTC).isoformat()
                if isinstance(created_utc, int | float)
                else None
            )
            summary = child_data.get("selftext")
            items.append(
                CollectedItem(
                    source=f"Reddit:r/{subreddit}",
                    title=title,
                    url=f"https://www.reddit.com{permalink}",
                    summary=summary if isinstance(summary, str) else "",
                    score=score,
                    created_at=created_at,
                    tags=[subreddit],
                )
            )
        return items

    def _reddit_access_token(self, config: RedditConfig) -> str:
        basic_auth = b64encode(f"{config.client_id}:{config.client_secret}".encode("utf-8")).decode("ascii")
        response = self._client.post(
            REDDIT_TOKEN_URL,
            content=f"grant_type=client_credentials",
            headers={
                "Authorization": f"Basic {basic_auth}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": config.user_agent,
            },
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Reddit access token was not returned")
        return token


def build_small_llm(settings: Settings) -> ChatOllama:
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_small_model,
        temperature=0.1,
    )


def build_main_llm(settings: Settings) -> ChatOllama:
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_main_model,
        temperature=0.2,
    )


def default_arxiv_query() -> str:
    terms = [
        "cat:cs.AI",
        "cat:cs.LG",
        "cat:cs.CL",
        "cat:cs.SE",
    ]
    return quote_plus(" OR ".join(terms)).replace("%3A", ":")
