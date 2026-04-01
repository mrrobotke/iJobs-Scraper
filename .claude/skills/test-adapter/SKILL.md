---
name: test-adapter
description: Run a specific adapter against its live endpoint for integration testing. Usage — /test-adapter adapter_name (e.g., /test-adapter greenhouse)
disable-model-invocation: true
---

Run a live integration test for a specific adapter.

**Arguments:** `$ARGUMENTS` — adapter name (e.g., `greenhouse`, `kenya_airways`, `careerjet`)

## Steps

1. Read the adapter source in `src/ijobs_scraper/adapters/` to understand its config requirements
2. Read `@docs/scraper-api-discovery-report-v1_3.md` for the portal's live endpoint and known config values
3. Write a temporary script `_test_live_adapter.py` that:
   - Creates a `SourceConfig` with the adapter's known config from the spec
   - Instantiates the adapter directly
   - Calls `fetch_listings()` with `asyncio.run()`
   - Collects up to 5 listings (break after 5)
   - For each listing, prints:
     - `external_url`
     - `title` (if present)
     - `external_id` (if present)
     - First 300 chars of `raw_html` or `raw_json`
   - Reports: total found, which fields are populated, any errors

4. Run the script: `python _test_live_adapter.py`
5. Delete the temporary script

**Important:** Respect rate limits. The base adapter classes include delays — do not bypass them.
