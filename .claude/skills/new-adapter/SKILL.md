---
name: new-adapter
description: Scaffold a new portal adapter with test file and registry entry. Usage — /new-adapter portal_name type (e.g., /new-adapter brightermonday html)
disable-model-invocation: true
---

Create a new adapter for the ijobs-scraper package.

**Arguments:** `$ARGUMENTS` — format: `portal_name adapter_type` (e.g., `brightermonday html`, `kenya_airways api`, `workday browser`)

## Steps

1. Read the portal details from `@docs/scraper-api-discovery-report-v1_3.md` for the specified portal
2. Read the architecture spec `@docs/scraper-engine.md` §6 (Adapter System) for base class patterns
3. Read existing adapters of the same type in `src/ijobs_scraper/adapters/{api,html,browser}/` for reference

4. Create the adapter file at:
   - API: `src/ijobs_scraper/adapters/api/{name}.py`
   - HTML: `src/ijobs_scraper/adapters/html/{name}.py`
   - Browser: `src/ijobs_scraper/adapters/browser/{name}.py`

5. The adapter MUST:
   - Inherit from the correct base (`APIAdapter`, `HTMLAdapter`, or `BrowserAdapter`)
   - Use `@AdapterRegistry.register("{name}")` decorator
   - Implement `async def fetch_listings(self, config: SourceConfig) -> AsyncIterator[RawListing]`
   - Implement `def can_handle_url(self, url: str) -> bool`
   - Include rate limiting appropriate to the portal
   - Use base class HTTP methods (`self._get`, `self._post`, `self._fetch_page`) — no raw httpx clients
   - NEVER import framework dependencies

6. Create test file at `tests/adapters/test_{name}.py` with:
   - Unit test with mocked HTTP responses (use `pytest-httpx` or `respx`)
   - Test for `can_handle_url` matching
   - Test for proper `RawListing` field population
   - Test for error handling (network failure, unexpected response shape)

7. Run `ruff check` and `mypy --strict` on the new files to verify
