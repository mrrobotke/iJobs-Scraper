# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`ijobs-scraper` is a standalone, framework-agnostic PyPI package for job scraping, AI enrichment, and deduplication targeting the African (Kenyan) job market. Python >=3.12.

## Architecture Reference

For full architecture, models, protocols, and adapter specifications:
- @docs/scraper-engine.md
- @docs/scraper-api-discovery-report-v1_3.md

## Critical Constraints

- **Zero framework coupling** — NEVER import FastAPI, SQLAlchemy, Django, Flask, or any web/ORM framework inside `src/ijobs_scraper/`. This package must remain standalone.
- **Async-first** — all I/O uses `async`/`await`. Use `httpx` (not `requests`), `playwright` (not `selenium`).
- **Protocol-based interfaces** — host-facing interfaces (`AIProvider`, `StorageBackend`, `JobCallback`) use Python `Protocol` for structural subtyping. No ABC inheritance for these.
- **Pydantic v2 strict** — all data models use Pydantic v2. Use `model_validator` not `@validator`. Must pass `mypy --strict`.
- **Per-job error isolation** — a single failed listing must never stop the batch. Catch per-listing, log, increment `jobs_failed`, continue.

## Coding Patterns

- Adapter registry uses decorator: `@AdapterRegistry.register("name")`
- Adapters return `AsyncIterator[RawListing]` from `fetch_listings()`
- Content hash: SHA-256 of `normalized(title|company|location)` — see spec §8.2
- Rate limiting built into adapter base classes (configurable delays + jitter)
- Exception hierarchy: `ScraperError > AdapterError > RateLimitError`, `EnrichmentError`, `DuplicateJobError`
- Optional deps gated by extras: `[browser]` for playwright, `[careerjet]` for careerjet-api, `[pdf]` for pdfplumber

## Build & Quality

- Build backend: hatchling
- Formatter + linter: `ruff format . && ruff check .`
- Type checker: `mypy --strict src/`
- Tests: `pytest`
- Full verify: `ruff check . && ruff format --check . && mypy --strict src/ && pytest`

## Adapter Development

When creating a new adapter:
1. Inherit from the correct base: `APIAdapter`, `HTMLAdapter`, or `BrowserAdapter`
2. Implement `fetch_listings()` → `AsyncIterator[RawListing]`
3. Implement `can_handle_url()` for manual scraper support
4. Register with `@AdapterRegistry.register("adapter_name")`
5. Add corresponding test in `tests/adapters/`
6. Check portal details in @docs/scraper-api-discovery-report-v1_3.md
