# Future News Forecaster

<p align="center">
  <img src="docs/assets/cover.svg" alt="Future News Forecaster cover" width="100%">
</p>

<p align="center">
  <strong>Pet project</strong> about forecasting how a concrete newsroom might cover a scheduled event.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-0F766E?style=flat-square" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/gui-Tkinter-D7EFE8?style=flat-square" alt="Tkinter GUI">
  <img src="https://img.shields.io/badge/openai-Responses%20API-115E59?style=flat-square" alt="OpenAI Responses API">
  <img src="https://img.shields.io/badge/status-pet%20project-C97B63?style=flat-square" alt="Pet project">
</p>

Future News Forecaster does not try to "predict the future" in a general sense.  
It starts from **scheduled, high-certainty events** and builds a conservative forecast of how a chosen outlet could turn that event into a **headline + lead**.

The current product is strongest on **calendar-driven macro and statistics coverage** and is intentionally honest about where it does not fit.

## Why This Exists

This repository is a small newsroom-flavored experiment around three ideas:

- a news forecast should start from a real upcoming event, not from free-form guessing
- outlet fit matters as much as writing style
- a good system should be allowed to say "this outlet probably would not cover this"

That is why the project has an explicit `editorial fit` layer before generation and can return zero candidates as a valid outcome.

## What It Does

- collects upcoming events from connected release calendars
- scores event predictability and outlet relevance
- retrieves style anchors from a local archive when available
- generates restrained scenarios first, then writes headline + lead
- reranks results and exports them to JSON/Markdown
- shows the forecast, warnings, and filtering logic directly in a desktop GUI

## Workflow

<p align="center">
  <img src="docs/assets/workflow.svg" alt="Workflow diagram" width="100%">
</p>

## Current Event Universe

Right now the live inputs are intentionally narrow:

- [ONS release calendar](https://www.ons.gov.uk/releasecalendar?page=4&release-type=type-upcoming)
- [U.S. Census economic indicators calendar](https://www.census.gov/economic-indicators/calendar-listview.html)
- a bundled sample fallback collector for stable offline demos

This means the project currently works best on:

- Reuters / Bloomberg / Financial Times style use cases
- macro releases, trade, surveys, official statistics
- scheduled, explainable, high-certainty newsroom events

## Honest Limitations

This repo is not trying to fake universality. Current limitations are part of the product definition:

- the live event universe is mostly UK/US macro and statistical releases
- web search improves context, but it does not replace the upstream event universe
- not every outlet writes about these calendars, so some runs should end with zero candidates
- outlet style matching is much stronger when a local archive like `data/archives/<outlet>_sample.jsonl` exists
- breaking news, local city coverage, lifestyle, culture, and sports-heavy newsrooms are weak fits today

For selective outlets such as Meduza, routine UK releases are often filtered out. That is expected behavior, not a bug.

## Example Fits

Examples the current product can realistically support:

- Reuters / Bloomberg / Financial Times: `U.S. International Trade in Goods and Services`
- Reuters: `Economic activity and social change in the UK, real-time indicators`
- Reuters: `Business insights and impact on the UK economy`
- Meduza: broader economic or geopolitical angles are more realistic than routine ONS statistics

## Desktop App

The repo includes a Tkinter desktop app with:

- API key entry and `.env` saving
- provider / date / outlet / limit controls
- in-app forecast view
- an `Editorial filter` tab explaining why topics were rejected
- a project-idea tab with concept notes and product limitations

## Quick Start

Install:

```bash
python -m pip install -e .
```

Run the GUI:

```bash
python -m future_news_forecaster gui
```

Offline demo:

```bash
python -m future_news_forecaster run --date 2026-04-02 --offline --provider mock --out-dir results/offline-demo
```

Live run with auto provider:

```bash
python -m future_news_forecaster run --date 2026-04-02 --provider auto --out-dir results/live-run
```

Force OpenAI:

```bash
set OPENAI_API_KEY=your_key_here
python -m future_news_forecaster run --date 2026-04-02 --provider openai --model gpt-5-mini
```

Disable OpenAI web search:

```bash
python -m future_news_forecaster run --date 2026-04-02 --provider openai --no-web-search
```

## OpenAI Key

Two ways to provide the key:

1. via the GUI field and `Save key`
2. manually in the project root `.env`

```bash
OPENAI_API_KEY=your_key_here
```

## Output Artifacts

Each run writes:

- `collected_events.json`
- `forecast_run.json`
- `forecast_run.md`
- `editorial_filter.md`

## Project Layout

```text
src/future_news_forecaster/
  collectors/         calendar collectors
  generation.py       mock + OpenAI generation
  retrieval.py        archive retrieval
  scoring.py          predictability + editorial fit scoring
  pipeline.py         end-to-end orchestration
  gui.py              desktop app
  cli.py              CLI entrypoint
data/archives/
  reuters_sample.jsonl
docs/project-concept/
  README.md
  principles.md
docs/assets/
  cover.svg
  workflow.svg
```

## Tech Notes

- `mock` mode gives deterministic local runs for demos and tests
- OpenAI mode uses Structured Outputs through the Responses API
- optional OpenAI web search is used to verify phrasing and event context
- `provider=auto` falls back to `mock` if OpenAI is unavailable

## Roadmap

- add more event calendars beyond ONS and Census
- expand outlet-specific local archives
- improve outlet coverage modeling, not just outlet style
- add richer retrieval over larger article sets
- make the GUI more newsroom-like and demo-friendly

## Related Docs

- concept notes: [`docs/project-concept/README.md`](docs/project-concept/README.md)
- operating principles: [`docs/project-concept/principles.md`](docs/project-concept/principles.md)

