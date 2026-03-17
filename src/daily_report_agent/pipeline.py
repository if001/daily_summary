from __future__ import annotations

from datetime import date
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from .clients import SourceClient, build_main_llm, build_small_llm
from .config import Settings
from .models import CollectedItem, RawCollection, ReportOutput, SummaryOutput, TagOutput
from .prompts import load_skill
from .save import save_outputs


class PipelineState(TypedDict, total=False):
    run_date: date
    items: list[CollectedItem]
    raw: RawCollection
    summary: SummaryOutput
    tags: TagOutput
    report: ReportOutput
    written_paths: dict[str, str]


class DailyReportPipeline:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._small_llm = build_small_llm(settings)
        self._main_llm = build_main_llm(settings)

    def compile(self):
        graph = StateGraph(PipelineState)
        graph.add_node("collect", self._collect)
        graph.add_node("summarize", self._summarize)
        graph.add_node("tag", self._tag)
        graph.add_node("report", self._report)
        graph.add_node("save", self._save)

        graph.add_edge(START, "collect")
        graph.add_edge("collect", "summarize")
        graph.add_edge("summarize", "tag")
        graph.add_edge("tag", "report")
        graph.add_edge("report", "save")
        graph.add_edge("save", END)
        return graph.compile()

    def run(self, run_date: date) -> PipelineState:
        graph = self.compile()
        return graph.invoke({"run_date": run_date})

    def _collect(self, state: PipelineState) -> PipelineState:
        run_date = state.get("run_date")
        client = SourceClient()
        try:
            items: list[CollectedItem] = []
            # items.extend(client.arxiv_recent("cat:cs.AI OR cat:cs.LG OR cat:cs.CL OR cat:cs.SE", self._settings.max_items_per_source))
            items.extend(client.hackernews_top(self._settings.max_items_per_source))
            items.extend(client.hatena_hotentry_it(self._settings.max_items_per_source))
            if self._settings.reddit is not None:
                items.extend(client.reddit_best(self._settings.reddit, "MachineLearning", max(1, self._settings.max_items_per_source // 2)))
                items.extend(client.reddit_best(self._settings.reddit, "programming", max(1, self._settings.max_items_per_source // 2)))
        finally:
            client.close()
        return {
            "items": items,
            "raw": RawCollection(run_date=run_date, items=items),
        }

    def _summarize(self, state: PipelineState) -> PipelineState:
        payload = _render_items(state.get("items", []))
        structured = self._small_llm.with_structured_output(SummaryOutput)
        result = structured.invoke(
            [
                SystemMessage(content=load_skill("summarize.md")),
                HumanMessage(content=payload),
            ]
        )
        return {"summary": result}

    def _tag(self, state: PipelineState) -> PipelineState:
        payload = _render_items(state.get("items", [])) + "\n\nSummary:\n" + "\n".join(state["summary"].bullets)
        structured = self._small_llm.with_structured_output(TagOutput)
        result = structured.invoke(
            [
                SystemMessage(content=load_skill("tagging.md")),
                HumanMessage(content=payload),
            ]
        )
        return {"tags": result}

    def _report(self, state: PipelineState) -> PipelineState:
        payload = "\n".join(
            [
                f"Run date: {state['run_date'].isoformat()}",
                "Summary:",
                *state["summary"].bullets,
                "",
                "Tags:",
                ", ".join(state["tags"].tags),
                "",
                "Items:",
                _render_items(state["items"]),
            ]
        )
        structured = self._main_llm.with_structured_output(ReportOutput)
        result = structured.invoke(
            [
                SystemMessage(content=load_skill("report.md")),
                HumanMessage(content=payload),
            ]
        )
        return {"report": result}

    def _save(self, state: PipelineState) -> PipelineState:
        written = save_outputs(
            root=self._settings.report_root,
            run_date=state["run_date"],
            raw=state["raw"],
            summary=state["summary"],
            tags=state["tags"],
            report=state["report"],
        )
        return {"written_paths": {key: str(path) for key, path in written.items()}}


def _render_items(items: list[CollectedItem]) -> str:
    blocks: list[str] = []
    for item in items:
        lines = [
            f"source: {item.source}",
            f"title: {item.title}",
            f"url: {item.url}",
        ]
        if item.score is not None:
            lines.append(f"score: {item.score}")
        if item.created_at is not None:
            lines.append(f"created_at: {item.created_at}")
        if item.tags:
            lines.append(f"tags: {', '.join(item.tags)}")
        if item.summary:
            lines.append(f"summary: {item.summary}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
