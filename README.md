# Future News Forecaster

`future-news-forecaster` is a small MVP that implements the pipeline described in the shared conversation:

`collect -> score -> select -> retrieve -> draft -> rerank -> export`

The core idea is the same as in the link: do not "guess the future in general", but select **scheduled, high-certainty events** and forecast how a concrete outlet will turn them into a headline and a lead.

## What is implemented

- Live collectors for:
  - [ONS release calendar](https://www.ons.gov.uk/releasecalendar?page=4&release-type=type-upcoming)
  - [U.S. Census economic indicators calendar](https://www.census.gov/economic-indicators/calendar-listview.html)
- Offline fallback collector with bundled sample events for `2026-04-02`
- Retrieval over a small local archive (`data/archives/reuters_sample.jsonl`)
- Predictability scoring for scheduled slots
- Two-stage generation API:
  - stage A: structured scenarios
  - stage B: headline + lead
- `mock` generator for deterministic local runs
- Optional OpenAI generator using Structured Outputs via the current `responses.parse(...)` flow from the official docs:
  - [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs/)
- Optional OpenAI web search integration via the official Responses API `web_search` tool
- Artifact export to JSON and Markdown
- Desktop GUI that shows forecasts directly in the app
- Separate concept folder: `docs/project-concept/`

## Install

```bash
python -m pip install -e .
```

## Where to put the OpenAI key

Two options are supported:

1. In the GUI:
   - run `python -m future_news_forecaster gui`
   - paste the key into the `API key` field
   - click `Сохранить ключ`
2. Manually in the project root, in `.env`:

```bash
OPENAI_API_KEY=your_key_here
```

The GUI saves the key to `.env` automatically.

## Quick start

Offline run:

```bash
python -m future_news_forecaster run --date 2026-04-02 --offline --provider mock --out-dir results/offline-demo
```

Live collectors + auto provider:

```bash
python -m future_news_forecaster run --date 2026-04-02 --provider auto --out-dir results/live-run
```

Disable OpenAI web search if needed:

```bash
python -m future_news_forecaster run --date 2026-04-02 --provider openai --no-web-search
```

GUI:

```bash
python -m future_news_forecaster gui
```

The GUI now shows:

- status and log
- generated forecasts directly in the app
- a built-in tab with the project idea and its operating principles
- a checkbox for OpenAI web search

Force OpenAI provider:

```bash
set OPENAI_API_KEY=your_key_here
python -m future_news_forecaster run --date 2026-04-02 --provider openai --model gpt-5-mini
```

## Output

Each run writes:

- `collected_events.json`
- `forecast_run.json`
- `forecast_run.md`

## Project layout

```text
src/future_news_forecaster/
  collectors/         # calendar collectors
  generation.py       # mock + OpenAI scenario/story generation
  retrieval.py        # lightweight archive retrieval
  scoring.py          # slot and candidate scoring
  pipeline.py         # end-to-end orchestration
  cli.py              # command line entrypoint
data/archives/
  reuters_sample.jsonl
docs/project-concept/
  README.md
  principles.md
```

## Notes

- The bundled archive is synthetic and exists only to provide a stable style-retrieval baseline.
- The live collectors are intentionally lightweight and HTML-structure-dependent; for production use, move them behind richer parsers and fixture-backed tests.
- If OpenAI is unavailable or `OPENAI_API_KEY` is missing, `provider=auto` falls back to the deterministic `mock` generator.
