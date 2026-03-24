from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .gui import launch_gui
from .pipeline import build_pipeline, write_run_artifacts
from .settings import load_environment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="future-news",
        description="Forecast calendar-driven news headlines and leads for scheduled events.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Collect events and generate forecast candidates.")
    run_parser.add_argument("--date", required=True, help="Target date in ISO format, e.g. 2026-04-02")
    run_parser.add_argument("--limit", type=int, default=5, help="Number of final candidates to keep.")
    run_parser.add_argument("--outlet", default="Reuters", help="Outlet style to emulate.")
    run_parser.add_argument(
        "--provider",
        choices=["auto", "mock", "openai"],
        default="auto",
        help="Generator provider.",
    )
    run_parser.add_argument(
        "--model",
        default="gpt-5-mini",
        help="OpenAI model for structured outputs when provider resolves to OpenAI.",
    )
    run_parser.add_argument(
        "--archive-dir",
        type=Path,
        default=Path("data/archives"),
        help="Directory with outlet archive JSONL files.",
    )
    run_parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("results") / "latest",
        help="Directory where run artifacts will be written.",
    )
    run_parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip live collectors and use bundled sample events only.",
    )
    run_parser.add_argument(
        "--no-web-search",
        action="store_true",
        help="Disable OpenAI web search tool. Ignored for mock provider.",
    )

    subparsers.add_parser("gui", help="Open a simple desktop interface for key entry and runs.")

    return parser


def main(argv: list[str] | None = None) -> int:
    load_environment()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        target_date = date.fromisoformat(args.date)
        pipeline = build_pipeline(
            outlet=args.outlet,
            provider=args.provider,
            model=args.model,
            archive_dir=args.archive_dir,
            web_search_enabled=not args.no_web_search,
        )
        run = pipeline.run(target_date=target_date, limit=args.limit, offline=args.offline)
        write_run_artifacts(run, args.out_dir)
        print(
            f"Wrote forecast run to {args.out_dir} "
            f"({len(run.candidates)} candidates, provider={run.provider}, collected={len(run.collected_events)})."
        )
        return 0

    if args.command == "gui":
        launch_gui()
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2
