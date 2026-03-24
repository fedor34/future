from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from future_news_forecaster.collectors.base import BaseCollector
from future_news_forecaster.collectors.sample import SampleCollector
from future_news_forecaster.generation import MockGenerator
from future_news_forecaster.models import Event, EventSource
from future_news_forecaster.pipeline import ForecastPipeline, build_pipeline, write_run_artifacts
from future_news_forecaster.retrieval import ArchiveStore


class OfflineSmokeTest(unittest.TestCase):
    def test_offline_run_produces_candidates(self) -> None:
        pipeline = build_pipeline(
            outlet="Reuters",
            provider="mock",
            model="gpt-5-mini",
            archive_dir=Path("data/archives"),
        )
        run = pipeline.run(target_date=date(2026, 4, 2), limit=3, offline=True)
        self.assertGreaterEqual(len(run.collected_events), 3)
        self.assertGreaterEqual(len(run.candidates), 1)

        with TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            write_run_artifacts(run, out_dir)
            self.assertTrue((out_dir / "forecast_run.json").exists())
            self.assertTrue((out_dir / "forecast_run.md").exists())
            self.assertTrue((out_dir / "editorial_filter.md").exists())

    def test_missing_archive_does_not_crash_for_new_outlet(self) -> None:
        pipeline = build_pipeline(
            outlet="медуза",
            provider="mock",
            model="gpt-5-mini",
            archive_dir=Path("data/archives"),
        )
        run = pipeline.run(target_date=date(2026, 4, 2), limit=3, offline=True)
        self.assertGreaterEqual(len(run.candidates), 1)
        self.assertLess(len(run.candidates), len(run.collected_events))
        self.assertTrue(any("No local archive for outlet" in warning for warning in run.warnings))
        self.assertTrue(any("Skipped" in warning for warning in run.warnings))

    def test_live_recovery_can_restore_relevant_sample_event(self) -> None:
        class LowFitCollector(BaseCollector):
            name = "low_fit_live"

            def collect(self, target_date: date):
                return [
                    Event(
                        event_id="live-low-fit",
                        title="Funded occupational pension schemes in the UK: April to September 2025",
                        date=target_date,
                        time_label="09:30",
                        timezone="Europe/London",
                        status="confirmed",
                        category="official_release",
                        source=EventSource(
                            name="Office for National Statistics",
                            collector=self.name,
                            url="https://example.com/ons",
                        ),
                        tags=["official_release", "ons", "pensions", "uk"],
                    )
                ]

        class FailingCollector(BaseCollector):
            name = "failing_live"

            def collect(self, target_date: date):
                raise RuntimeError("simulated live failure")

        pipeline = ForecastPipeline(
            archive_store=ArchiveStore.empty(),
            generator=MockGenerator(),
            outlet="медуза",
            live_collectors=[LowFitCollector(), FailingCollector()],
            fallback_collectors=[SampleCollector()],
        )
        run = pipeline.run(target_date=date(2026, 4, 2), limit=3, offline=False)
        self.assertGreaterEqual(len(run.candidates), 1)
        self.assertTrue(any("trying bundled sample calendar" in warning for warning in run.warnings))
        self.assertTrue(any(candidate.event.title == "U.S. International Trade in Goods and Services" for candidate in run.candidates))


if __name__ == "__main__":
    unittest.main()
