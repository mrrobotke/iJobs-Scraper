---
paths:
  - "src/ijobs_scraper/adapters/**"
description: Conventions for portal adapter development
---

When working on adapters:

- Inherit from the correct base: `APIAdapter` (REST), `HTMLAdapter` (BeautifulSoup), `BrowserAdapter` (Playwright)
- Register with `@AdapterRegistry.register("adapter_name")` decorator
- `fetch_listings()` returns `AsyncIterator[RawListing]` — use `yield`, not `return list`
- `can_handle_url()` must match the portal's domain for manual scraper support
- Use base class HTTP methods (`self._get()`, `self._post()`, `self._fetch_page()`) — don't create raw httpx/aiohttp clients
- Rate limiting: use base class defaults or override with portal-specific delays
- NEVER import FastAPI, SQLAlchemy, Django, Flask, or `requests`
- Check portal details in @docs/scraper-api-discovery-report-v1_3.md before implementing
- Populate `RawListing.raw_json` for API sources, `RawListing.raw_html` for HTML/browser sources
- Always set `external_url` and `company_name` on every yielded `RawListing`
