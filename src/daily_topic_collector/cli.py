from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .models import CollectRequest, SourceName
from .runner import CollectorRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect topic-filtered daily items for one source")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--day", required=True, help="YYYY-MM-DD")
    parser.add_argument("--source", required=True, choices=[source.value for source in SourceName])
    parser.add_argument("--data-dir", default="./data")
    args = parser.parse_args()

    request = CollectRequest(
        topic=args.topic,
        day=date.fromisoformat(args.day),
        source=SourceName(args.source),
        data_dir=Path(args.data_dir),
    )
    result = CollectorRunner().run(request)
    print(f"saved={result.manifest.saved_count} source={result.manifest.source.value} day={result.manifest.day.isoformat()}")


if __name__ == "__main__":
    main()
