from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from .models import CollectRequest, Manifest, NormalizedEntry, SourceName, write_json_lines


class Storage:
    def __init__(self, root: Path) -> None:
        self._root = root

    def run_dir(self, day: date, source: SourceName) -> Path:
        return self._root / "runs" / day.strftime("%Y-%m") / day.isoformat() / source.value

    def ensure_run_dir(self, day: date, source: SourceName) -> Path:
        path = self.run_dir(day, source)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_request(self, request: CollectRequest) -> None:
        run_dir = self.ensure_run_dir(request.day, request.source)
        payload = {
            "topic": request.topic,
            "day": request.day.isoformat(),
            "source": request.source.value,
            "data_dir": str(request.data_dir),
        }
        (run_dir / "request.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_queries(self, day: date, source: SourceName, queries: list[str]) -> None:
        run_dir = self.ensure_run_dir(day, source)
        payload = {"queries": queries}
        (run_dir / "queries.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_items(self, day: date, source: SourceName, items: list[NormalizedEntry]) -> None:
        run_dir = self.ensure_run_dir(day, source)
        write_json_lines(run_dir / "items.jsonl", items)

    def write_manifest(self, manifest: Manifest) -> None:
        run_dir = self.ensure_run_dir(manifest.day, manifest.source)
        (run_dir / "manifest.json").write_text(manifest.to_json(), encoding="utf-8")

    def load_previous_dedupe_keys(self, day: date, source: SourceName) -> set[str]:
        previous_day = date.fromordinal(day.toordinal() - 1)
        path = self.run_dir(previous_day, source) / "items.jsonl"
        if not path.exists():
            return set()
        keys: set[str] = set()
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                parsed = json.loads(stripped)
                value = parsed.get("dedupe_key")
                if isinstance(value, str):
                    keys.add(value)
        return keys
