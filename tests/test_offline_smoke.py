from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from future_news_forecaster.pipeline import build_pipeline, write_run_artifacts


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


if __name__ == "__main__":
    unittest.main()
