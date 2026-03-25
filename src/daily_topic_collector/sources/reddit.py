from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from datetime import date, datetime, timezone
import os

from ..http import HttpClient
from ..models import NormalizedEntry, SourceName
from .base import PipelineContext, build_queries, clean_url, dedupe_entries, summarize_and_tag


@dataclass(frozen=True)
class RedditConfig:
    client_id: str
    client_secret: str
    user_agent: str

    @classmethod
    def from_env(cls) -> "RedditConfig":
        client_id = os.environ["REDDIT_CLIENT_ID"]
        client_secret = os.environ["REDDIT_CLIENT_SECRET"]
        user_agent = os.environ["REDDIT_USER_AGENT"]
        return cls(client_id=client_id, client_secret=client_secret, user_agent=user_agent)


@dataclass(frozen=True)
class RedditPipeline:
    http: HttpClient
    config: RedditConfig
    source: SourceName = SourceName.REDDIT

    def run(self, context: PipelineContext) -> tuple[list[str], list[NormalizedEntry], int]:
        queries = build_queries(context.ollama, self.source.value, context.request.topic, context.request.day)
        token = self._access_token()
        raw_posts: list[dict[str, object]] = []
        for query in queries:
            raw_posts.extend(self._fetch(query, token))
        normalized = [self._normalize(post, context) for post in raw_posts if self._matches_day(post, context.request.day)]
        previous_keys = context.storage.load_previous_dedupe_keys(context.request.day, self.source)
        deduped, removed = dedupe_entries(normalized, previous_keys)
        return queries, deduped, removed

    def _access_token(self) -> str:
        raw = f"{self.config.client_id}:{self.config.client_secret}".encode("utf-8")
        auth = b64encode(raw).decode("ascii")
        response = self.http.post_form(
            "https://www.reddit.com/api/v1/access_token",
            form={"grant_type": "client_credentials"},
            headers={
                "Authorization": f"Basic {auth}",
                "User-Agent": self.config.user_agent,
            },
        ).json_dict()
        token = response.get("access_token")
        if not isinstance(token, str):
            raise RuntimeError("Reddit access token missing")
        return token

    def _fetch(self, query: str, token: str) -> list[dict[str, object]]:
        response = self.http.get(
            "https://oauth.reddit.com/search",
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": self.config.user_agent,
            },
            params={
                "q": query,
                "sort": "new",
                "t": "day",
                "type": "link",
                "limit": "50",
                "raw_json": "1",
            },
        ).json_dict()
        data = response.get("data")
        if not isinstance(data, dict):
            return []
        children = data.get("children")
        if not isinstance(children, list):
            return []
        posts: list[dict[str, object]] = []
        for child in children:
            if not isinstance(child, dict):
                continue
            child_data = child.get("data")
            if isinstance(child_data, dict):
                posts.append(child_data)
        return posts

    def _matches_day(self, post: dict[str, object], day: date) -> bool:
        created = post.get("created_utc")
        if not isinstance(created, (int, float)):
            return False
        created_at = datetime.fromtimestamp(float(created), tz=timezone.utc)
        return created_at.date() == day

    def _normalize(self, post: dict[str, object], context: PipelineContext) -> NormalizedEntry:
        post_id = post.get("id")
        if not isinstance(post_id, str):
            raise ValueError("Reddit post id missing")
        title = post.get("title")
        title_text = title if isinstance(title, str) else post_id
        body = post.get("selftext")
        selftext = body if isinstance(body, str) else ""
        permalink = post.get("permalink")
        url = post.get("url")
        if isinstance(url, str) and url:
            target_url = clean_url(url)
        elif isinstance(permalink, str):
            target_url = clean_url(f"https://www.reddit.com{permalink}")
        else:
            target_url = f"https://www.reddit.com/comments/{post_id}"
        summary, tags = summarize_and_tag(
            context.ollama,
            self.source.value,
            context.request.topic,
            title_text,
            selftext or target_url,
        )
        created_raw = post.get("created_utc")
        created_at = datetime.fromtimestamp(float(created_raw), tz=timezone.utc) if isinstance(created_raw, (int, float)) else context.collected_at
        return NormalizedEntry(
            id=f"reddit:t3_{post_id}",
            source=self.source,
            topic=context.request.topic,
            url=target_url,
            title=title_text,
            summary=summary,
            tags=tags,
            created_at=created_at,
            collected_at=context.collected_at,
            dedupe_key=f"reddit:t3_{post_id}",
        )
