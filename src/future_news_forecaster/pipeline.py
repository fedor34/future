from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
import json

from .collectors import CensusCollector, ONSCollector, SampleCollector
from .generation import BaseGenerator, build_generator
from .models import Event, ForecastCandidate, ForecastRun
from .retrieval import ArchiveStore, load_archive_store
from .scoring import score_candidate, score_editorial_fit, score_event, select_portfolio


class ForecastPipeline:
    def __init__(
        self,
        archive_store: ArchiveStore,
        generator: BaseGenerator,
        outlet: str,
        live_collectors: list | None = None,
        fallback_collectors: list | None = None,
        initial_warnings: list[str] | None = None,
    ) -> None:
        self.archive_store = archive_store
        self.generator = generator
        self.outlet = outlet
        self.live_collectors = live_collectors or [ONSCollector(), CensusCollector()]
        self.fallback_collectors = fallback_collectors or [SampleCollector()]
        self.initial_warnings = initial_warnings or []

    def collect_events(self, target_date: date, offline: bool = False) -> tuple[list[Event], list[str]]:
        warnings: list[str] = []
        collectors = self.fallback_collectors if offline else self.live_collectors
        events: list[Event] = []

        for collector in collectors:
            try:
                events.extend(collector.collect(target_date))
            except Exception as exc:
                warnings.append(f"{collector.name} failed: {exc}")

        if not events and not offline:
            warnings.append("No live events collected; falling back to bundled sample calendar.")
            for collector in self.fallback_collectors:
                events.extend(collector.collect(target_date))

        deduped: dict[str, Event] = {}
        for event in events:
            deduped.setdefault(event.event_id, event)
        return list(deduped.values()), warnings

    def run(self, target_date: date, limit: int = 5, offline: bool = False) -> ForecastRun:
        events, warnings = self.collect_events(target_date=target_date, offline=offline)
        warnings = [*self.initial_warnings, *warnings]
        best_per_event: list[ForecastCandidate] = []
        filtered_out_events = 0

        for event in events:
            retrieved = self.archive_store.search(event, outlet=self.outlet, limit=5)
            editorial_fit, editorial_reasons, editorial_threshold = score_editorial_fit(
                event=event,
                outlet=self.outlet,
                retrieved_examples=retrieved,
            )
            event.metadata["editorial_fit_score"] = editorial_fit
            event.metadata["editorial_fit_reasons"] = editorial_reasons
            event.metadata["editorial_fit_threshold"] = editorial_threshold

            if editorial_fit < editorial_threshold:
                filtered_out_events += 1
                warnings.append(
                    f"Skipped '{event.title}' for outlet '{self.outlet}': "
                    f"editorial fit {editorial_fit:.3f} is below threshold {editorial_threshold:.3f}."
                )
                continue

            event.predictability_score = score_event(event, len(retrieved))
            dossier = self.generator.build_dossier(event=event, outlet=self.outlet, retrieved_examples=retrieved)
            scenarios = self.generator.generate_scenarios(dossier)

            candidates: list[ForecastCandidate] = []
            for scenario in scenarios:
                draft = self.generator.generate_story(dossier, scenario)
                breakdown = score_candidate(event, dossier, scenario, draft)
                candidates.append(
                    ForecastCandidate(
                        event=event,
                        dossier=dossier,
                        scenario=scenario,
                        draft=draft,
                        score=breakdown,
                    )
                )

            if candidates:
                best_per_event.append(max(candidates, key=lambda item: item.score.total))

        if filtered_out_events and not best_per_event:
            warnings.append(
                f"No events cleared the editorial-fit filter for outlet '{self.outlet}' on {target_date.isoformat()}."
            )

        selected = select_portfolio(best_per_event, limit=limit)
        return ForecastRun(
            target_date=target_date,
            outlet=self.outlet,
            provider=self.generator.provider_name,
            model=getattr(self.generator, "model", None),
            created_at=datetime.now(UTC),
            collected_events=events,
            candidates=selected,
            warnings=warnings,
        )


def build_pipeline(
    outlet: str,
    provider: str,
    model: str,
    archive_dir: Path,
    web_search_enabled: bool = True,
) -> ForecastPipeline:
    archive_store, archive_warnings = load_archive_store(outlet=outlet, archive_dir=archive_dir)
    generator = build_generator(
        provider=provider,
        model=model,
        web_search_enabled=web_search_enabled,
    )
    return ForecastPipeline(
        archive_store=archive_store,
        generator=generator,
        outlet=outlet,
        initial_warnings=archive_warnings,
    )


def write_run_artifacts(run: ForecastRun, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "forecast_run.json"
    markdown_path = out_dir / "forecast_run.md"
    events_path = out_dir / "collected_events.json"

    events_path.write_text(
        json.dumps([event.model_dump(mode="json") for event in run.collected_events], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps(run.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(run), encoding="utf-8")


def render_markdown(run: ForecastRun) -> str:
    lines = [
        f"# Forecast run for {run.target_date.isoformat()}",
        "",
        f"- Outlet: {run.outlet}",
        f"- Provider: {run.provider}",
        f"- Model: {run.model or 'n/a'}",
        f"- Collected events: {len(run.collected_events)}",
        f"- Final candidates: {len(run.candidates)}",
        "",
    ]

    if run.warnings:
        lines.append("## Warnings")
        lines.append("")
        for warning in run.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.append("## Predictions")
    lines.append("")
    for index, candidate in enumerate(run.candidates, start=1):
        lines.extend(
            [
                f"### {index}. {candidate.event.title}",
                "",
                f"- Source: {candidate.event.source.name}",
                f"- Slot: {candidate.event.date.isoformat()} {candidate.event.time_label or 'TBD'} {candidate.event.timezone or ''}".strip(),
                f"- Predictability score: {candidate.event.predictability_score:.3f}" if candidate.event.predictability_score is not None else "- Predictability score: n/a",
                f"- Editorial fit: {candidate.score.editorial_fit:.3f}",
                f"- Final score: {candidate.score.total:.3f}",
                f"- Headline: {candidate.draft.headline}",
                f"- Lead: {candidate.draft.lead}",
                f"- Angle: {candidate.scenario.angle}",
            ]
        )
        if candidate.score.reasons:
            lines.append("- Coverage rationale:")
            for reason in candidate.score.reasons[:3]:
                lines.append(f"- {reason}")
        if candidate.dossier.retrieved_examples:
            lines.extend(["", "Style anchors:"])
            for example in candidate.dossier.retrieved_examples[:3]:
                lines.append(f"- {example.article.title}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
