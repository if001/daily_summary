from __future__ import annotations

from datetime import date
from pathlib import Path

from .models import RawCollection, ReportOutput, SummaryOutput, TagOutput


def report_directory(root: Path, run_date: date) -> Path:
    directory = root / run_date.strftime("%Y-%m")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_outputs(
    root: Path,
    run_date: date,
    raw: RawCollection,
    summary: SummaryOutput,
    tags: TagOutput,
    report: ReportOutput,
) -> dict[str, Path]:
    directory = report_directory(root, run_date)
    stem = run_date.isoformat()

    raw_path = directory / f"{stem}.raw.json"
    summary_path = directory / f"{stem}.summary.md"
    tags_path = directory / f"{stem}.tags.json"
    report_path = directory / f"{stem}.report.md"

    raw_path.write_text(raw.model_dump_json(indent=2), encoding="utf-8")
    summary_path.write_text("\n".join(f"- {line}" for line in summary.bullets) + "\n", encoding="utf-8")
    tags_path.write_text(tags.model_dump_json(indent=2), encoding="utf-8")
    report_path.write_text(f"# {report.title}\n\n{report.body_markdown}\n", encoding="utf-8")

    return {
        "raw": raw_path,
        "summary": summary_path,
        "tags": tags_path,
        "report": report_path,
    }
