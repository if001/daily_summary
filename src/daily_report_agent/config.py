from __future__ import annotations

from dataclasses import dataclass
from os import getenv
from pathlib import Path


@dataclass(frozen=True)
class RedditConfig:
    client_id: str
    client_secret: str
    user_agent: str


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str
    ollama_small_model: str
    ollama_main_model: str
    report_root: Path
    reddit: RedditConfig | None
    max_items_per_source: int


def load_settings() -> Settings:
    client_id = getenv("REDDIT_CLIENT_ID", "").strip()
    client_secret = getenv("REDDIT_CLIENT_SECRET", "").strip()
    user_agent = getenv("REDDIT_USER_AGENT", "").strip()

    reddit = (
        RedditConfig(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        if client_id and client_secret and user_agent
        else None
    )

    return Settings(
        ollama_base_url=getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_small_model=getenv("OLLAMA_SMALL_MODEL", "qwen3:4b"),
        ollama_main_model=getenv("OLLAMA_MAIN_MODEL", "qwen3:14b"),
        report_root=Path(getenv("REPORT_ROOT", "reports")),
        reddit=reddit,
        max_items_per_source=int(getenv("MAX_ITEMS_PER_SOURCE", "15")),
    )
