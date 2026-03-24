from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
import json

from .collectors import CensusCollector, ONSCollector, SampleCollector
from .generation import BaseGenerator, build_generator
from .models import Event, FilteredEventDecision, ForecastCandidate, ForecastRun
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

    @staticmethod
    def _event_identity(event: Event) -> tuple[str, str, str]:
        return (
            event.title.strip().lower(),
            event.date.isoformat(),
            (event.time_label or "").strip(),
        )

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
        identity_seen: set[tuple[str, str, str]] = set()
        for event in events:
            identity = self._event_identity(event)
            if identity in identity_seen:
                continue
            deduped.setdefault(event.event_id, event)
            identity_seen.add(identity)
        return list(deduped.values()), warnings

    def _generate_candidates_for_events(
        self,
        events: list[Event],
        warnings: list[str],
        filtered_events: list[FilteredEventDecision],
    ) -> list[ForecastCandidate]:
        best_per_event: list[ForecastCandidate] = []

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
                filtered_events.append(
                    FilteredEventDecision(
                        event_id=event.event_id,
                        title=event.title,
                        source_name=event.source.name,
                        editorial_fit=editorial_fit,
                        threshold=editorial_threshold,
                        reasons=editorial_reasons,
                    )
                )
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

        return best_per_event

    def _load_fallback_events(
        self,
        target_date: date,
        known_ids: set[str],
        known_identities: set[tuple[str, str, str]],
    ) -> tuple[list[Event], list[str]]:
        warnings: list[str] = []
        recovered: list[Event] = []
        for collector in self.fallback_collectors:
            try:
                for event in collector.collect(target_date):
                    if event.event_id not in known_ids and self._event_identity(event) not in known_identities:
                        recovered.append(event)
            except Exception as exc:
                warnings.append(f"{collector.name} failed during fallback recovery: {exc}")
        return recovered, warnings

    def run(self, target_date: date, limit: int = 5, offline: bool = False) -> ForecastRun:
        events, warnings = self.collect_events(target_date=target_date, offline=offline)
        warnings = [*self.initial_warnings, *warnings]
        filtered_events: list[FilteredEventDecision] = []
        best_per_event = self._generate_candidates_for_events(
            events=events,
            warnings=warnings,
            filtered_events=filtered_events,
        )

        if not offline and not best_per_event:
            recovered_events, recovery_warnings = self._load_fallback_events(
                target_date=target_date,
                known_ids={event.event_id for event in events},
                known_identities={self._event_identity(event) for event in events},
            )
            warnings.extend(recovery_warnings)
            if recovered_events:
                warnings.append(
                    "No live event cleared the outlet filter; trying bundled sample calendar to recover missing event types."
                )
                events.extend(recovered_events)
                best_per_event.extend(
                    self._generate_candidates_for_events(
                        events=recovered_events,
                        warnings=warnings,
                        filtered_events=filtered_events,
                    )
                )

        if filtered_events and not best_per_event:
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
            filtered_events=filtered_events,
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
    filter_path = out_dir / "editorial_filter.md"
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
    filter_path.write_text(render_editorial_report(run), encoding="utf-8")


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

    if run.filtered_events:
        lines.append("## Editorial filter")
        lines.append("")
        for item in run.filtered_events:
            lines.append(
                f"- {item.title}: fit {item.editorial_fit:.3f} below threshold {item.threshold:.3f}"
            )
        lines.append("")

    if not run.candidates:
        lines.extend(
            [
                "## Predictions",
                "",
                "No suitable forecast candidates were found for this outlet on the selected date.",
                "",
                "Try one of these:",
                "- choose another date",
                "- switch to offline mode if a live source failed",
                "- use a broader outlet or add a local archive for this outlet",
                "",
            ]
        )
        return "\n".join(lines).strip() + "\n"

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


def render_editorial_report(run: ForecastRun) -> str:
    lines = [
        f"# Editorial filter for {run.outlet}",
        "",
        f"- Date: {run.target_date.isoformat()}",
        f"- Filtered events: {len(run.filtered_events)}",
        f"- Final candidates: {len(run.candidates)}",
        "",
    ]

    if not run.filtered_events:
        lines.append("No events were filtered out by the outlet-fit system.")
        return "\n".join(lines).strip() + "\n"

    for index, item in enumerate(run.filtered_events, start=1):
        lines.extend(
            [
                f"## {index}. {item.title}",
                "",
                f"- Source: {item.source_name}",
                f"- Editorial fit: {item.editorial_fit:.3f}",
                f"- Threshold: {item.threshold:.3f}",
            ]
        )
        if item.reasons:
            lines.append("- Reasons:")
            for reason in item.reasons:
                lines.append(f"- {reason}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
