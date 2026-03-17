from __future__ import annotations

from importlib import resources


def load_skill(name: str) -> str:
    return resources.files("daily_report_agent.skills").joinpath(name).read_text(encoding="utf-8")
