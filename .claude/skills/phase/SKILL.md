---
name: phase
description: Show implementation progress against the 6-phase roadmap from the spec. Use to track what's done and what's next.
---

Check implementation progress against the roadmap in `@docs/scraper-engine.md` §14.

## Phase Checklist

### Phase 1: Package Foundation (Week 1–2)
- [ ] `pyproject.toml` with hatchling build backend and all deps
- [ ] `src/ijobs_scraper/models.py` — SourceConfig, RawListing, EnrichedJob, ScrapeResult, JobRequirements
- [ ] `src/ijobs_scraper/protocols.py` — AIProvider, StorageBackend, JobCallback
- [ ] `src/ijobs_scraper/exceptions.py` — ScraperError, AdapterError, EnrichmentError, DuplicateJobError, RateLimitError
- [ ] `src/ijobs_scraper/engine.py` — ScraperEngine (scrape_source, parse_url, scrape_all, register_adapter)
- [ ] `src/ijobs_scraper/enrichment.py` — OpenAI structured output pipeline with EXTRACTION_SCHEMA
- [ ] `src/ijobs_scraper/dedup.py` — compute_content_hash, Layer 1 + Layer 2 logic
- [ ] `src/ijobs_scraper/adapters/base.py` — BaseAdapter, APIAdapter, HTMLAdapter, BrowserAdapter
- [ ] `src/ijobs_scraper/_registry.py` — AdapterRegistry with register decorator + detect_from_url
- [ ] `src/ijobs_scraper/scheduler.py` — get_due_sources
- [ ] `src/ijobs_scraper/__init__.py` — public API exports
- [ ] Unit tests with mock AI provider (tests/test_engine.py, test_enrichment.py, test_dedup.py)

### Phase 2: API Adapters (Week 2–3)
- [ ] kenya_airways adapter + tests
- [ ] greenhouse adapter + tests (tested with One Acre Fund board_token)
- [ ] smartrecruiters adapter + tests (tested with AmrefHealthAfrica4)
- [ ] careerjet adapter + tests
- [ ] reliefweb adapter + tests
- [ ] Integration tests against live APIs

### Phase 3: HTML Scrapers (Week 3–4)
- [ ] brightermonday adapter + tests (Laravel, CSRF handling)
- [ ] myjobmag adapter + tests (PHP, simple HTML)
- [ ] mygov adapter + tests (/job-adverts, HTML tables)
- [ ] fuzu adapter + tests (Rails, server-rendered)
- [ ] kcb adapter + tests (PHP proprietary)

### Phase 4: Browser Scrapers (Week 4–5)
- [ ] workday adapter + tests (reusable for Absa, NCBA)
- [ ] impactpool adapter + tests
- [ ] world_vision adapter + tests (Rails + Hotwire Turbo)

### Phase 5: iJobs Integration (Week 5–6) — separate repo
### Phase 6: Polish & Launch (Week 6–8)

## Steps

1. Check which source files exist in `src/ijobs_scraper/`
2. Check which test files exist in `tests/`
3. Run `pytest --co -q` to list collected tests (if any)
4. Mark items as done/not done based on file existence and test results
5. Identify current phase and next priority items
