---
name: adapter-status
description: Show implementation status of all 13 planned adapters — which exist, have tests, and pass. Use to check project progress.
---

Check the implementation status of all planned adapters from the spec.

## Expected Adapters (from docs/scraper-engine.md §6.5)

**API (5):** kenya_airways, greenhouse, smartrecruiters, careerjet, reliefweb
**HTML (5):** brightermonday, myjobmag, mygov, fuzu, kcb
**Browser (3):** workday, impactpool, world_vision

## Steps

1. Check which adapter files exist:
   - `src/ijobs_scraper/adapters/api/*.py`
   - `src/ijobs_scraper/adapters/html/*.py`
   - `src/ijobs_scraper/adapters/browser/*.py`

2. Check which test files exist in `tests/adapters/`

3. For existing adapters, verify they have:
   - `@AdapterRegistry.register()` decorator
   - `fetch_listings()` method
   - `can_handle_url()` method

4. Run `pytest tests/adapters/ -v --tb=short` to check which pass

## Output Format

| Adapter | Type | Implemented | Tested | Passing |
|---------|------|:-----------:|:------:|:-------:|

**Totals:** X/13 implemented, X/13 tested, X/13 passing
