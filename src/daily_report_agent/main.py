from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
from dotenv import load_dotenv

from .config import load_settings
from .pipeline import DailyReportPipeline

load_dotenv()
def _parse_date(value: str | None) -> date:
    if value is None:
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="daily-report-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--date", dest="run_date", default=None, help="YYYY-MM-DD")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = load_settings()

    if args.command == "run":
        pipeline = DailyReportPipeline(settings)
        result = pipeline.run(_parse_date(args.run_date))
        written = result.get("written_paths", {})
        for key, value in written.items():
            print(f"{key}: {Path(value)}")


if __name__ == "__main__":
    main()
