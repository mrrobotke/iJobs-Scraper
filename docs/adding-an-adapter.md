# Adding an Adapter

This guide walks you through adding a new job portal adapter to `ijobs-scraper`. By the end, you'll have a working adapter that fetches job listings from your target portal, complete with tests.

## Overview

Each job portal in `ijobs-scraper` is represented by an **adapter** — a self-contained class that knows how to connect to a specific source and extract raw job listings. The adapter is only responsible for fetching data; enrichment, deduplication, and persistence are handled by the engine.

The adapter system has three base classes, each tailored to a different access method:

| Base Class | When to Use | I/O Method | Core Dep |
|-----------|-------------|-----------|----------|
| `APIAdapter` | Portal exposes a REST/JSON API | `httpx` async HTTP client | Core |
| `HTMLAdapter` | Portal serves server-rendered HTML | `beautifulsoup4` + `lxml` | Core |
| `BrowserAdapter` | Portal requires JavaScript to render content | `playwright` | Optional `[browser]` extra |

**Rule of thumb:** Always prefer `APIAdapter` if an API exists. Fall back to `HTMLAdapter` for server-rendered pages. Use `BrowserAdapter` only when JavaScript rendering is required (e.g., Workday, single-page apps).

## Adapter File Structure

Place your adapter in the correct subdirectory based on its type:

```
src/ijobs_scraper/adapters/
├── __init__.py
├── base.py                 # BaseAdapter, APIAdapter, HTMLAdapter, BrowserAdapter
├── api/
│   ├── __init__.py
│   ├── kenya_airways.py    # Example: direct REST API
│   ├── greenhouse.py       # Example: reusable platform adapter
│   └── your_adapter.py
├── html/
│   ├── __init__.py
│   ├── brightermonday.py   # Example: Laravel site with CSRF
│   └── your_adapter.py
└── browser/
    ├── __init__.py
    ├── workday.py           # Example: reusable Workday adapter
    └── your_adapter.py
```

## Step 1: Research the Portal

Before writing code, understand how the portal serves job data:

1. **Check for APIs first.** Open browser DevTools (Network tab), navigate to the jobs page, and look for XHR/fetch requests returning JSON. Many portals have undocumented APIs.
2. **Identify the data format.** What fields are available? How is pagination handled? Are there query parameters for filtering?
3. **Check for anti-scraping measures.** Does the site use Cloudflare, CSRF tokens, session cookies, or rate limiting?
4. **Check the [API Discovery Report](scraper-api-discovery-report-v1_3.md)** for existing research on Kenyan portals.

## Step 2: Create the Adapter

### API Adapter Example

For portals with a REST/JSON API. This is the simplest and most reliable adapter type.

```python
# src/ijobs_scraper/adapters/api/my_portal.py
from __future__ import annotations

from ijobs_scraper.adapters.base import APIAdapter
from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.models import RawListing, SourceConfig


@AdapterRegistry.register("my_portal")
class MyPortalAdapter(APIAdapter):
    """Scrapes jobs from My Portal's public REST API.

    Config:
        base_url: API base URL (e.g., "https://api.myportal.com").
        config: No additional config required.

    API docs: https://myportal.com/developers
    """

    async def fetch_listings(self, config: SourceConfig):
        """Fetch all job listings, handling pagination."""
        page = 1
        while True:
            data = await self._get(
                f"{config.base_url}/api/jobs",
                params={"page": page, "per_page": 50},
            )
            jobs = data.get("results", [])
            if not jobs:
                break

            for item in jobs:
                yield RawListing(
                    external_id=str(item["id"]),
                    external_url=item["url"],
                    title=item.get("title"),
                    raw_json=item,
                    company_name=config.name,
                )

            # Stop if no more pages
            if page >= data.get("total_pages", 1):
                break
            page += 1

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Optionally fetch full job details for richer enrichment.

        Override this if the list endpoint returns minimal data and a
        detail endpoint provides the full description.
        """
        if listing.external_id:
            detail = await self._get(f"{config.base_url}/api/jobs/{listing.external_id}")
            listing.raw_json = detail
        return listing

    def can_handle_url(self, url: str) -> bool:
        """Enable manual scraping — auto-detect this adapter from a URL."""
        return "myportal.com" in url
```

**Key points:**
- `fetch_listings()` is an async generator that yields `RawListing` objects
- `fetch_detail()` is optional — override it when the list endpoint lacks full job descriptions
- `can_handle_url()` enables the manual scraper to auto-detect your adapter from a pasted URL
- `self._get()` and `self._post()` are provided by `APIAdapter` with built-in rate limiting

### HTML Adapter Example

For portals that serve server-rendered HTML without a JSON API.

```python
# src/ijobs_scraper/adapters/html/my_portal.py
from __future__ import annotations

from ijobs_scraper.adapters.base import HTMLAdapter
from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.models import RawListing, SourceConfig


@AdapterRegistry.register("my_html_portal")
class MyHTMLPortalAdapter(HTMLAdapter):
    """Scrapes jobs from My HTML Portal.

    This portal uses server-rendered HTML with standard pagination.
    No JavaScript rendering required.

    Config:
        base_url: Portal URL (e.g., "https://careers.myportal.com").
    """

    async def fetch_listings(self, config: SourceConfig):
        """Parse job listings from HTML pages."""
        page = 1
        while True:
            soup = await self._fetch_page(
                f"{config.base_url}/jobs",
                params={"page": page},
            )
            job_cards = soup.select("div.job-listing")
            if not job_cards:
                break

            for card in job_cards:
                link = card.select_one("a.job-title")
                if not link:
                    continue

                yield RawListing(
                    external_url=f"{config.base_url}{link['href']}",
                    title=link.get_text(strip=True),
                    company_name=config.name,
                )

            # Check for next page
            if not soup.select_one("a.next-page"):
                break
            page += 1

    async def fetch_detail(self, listing: RawListing, config: SourceConfig) -> RawListing:
        """Fetch the full job page for enrichment."""
        soup = await self._fetch_page(listing.external_url)
        content = soup.select_one("div.job-description")
        if content:
            listing.raw_html = str(content)
        return listing

    def can_handle_url(self, url: str) -> bool:
        return "myportal.com" in url
```

**Key points:**
- `self._fetch_page()` returns a BeautifulSoup object with built-in rate limiting
- Always implement `fetch_detail()` for HTML adapters — list pages rarely contain full descriptions
- Use CSS selectors (`soup.select()`) for robust element targeting

### Browser Adapter Example

For portals that require JavaScript rendering (Workday, SPAs, etc.).

```python
# src/ijobs_scraper/adapters/browser/my_portal.py
from __future__ import annotations

from ijobs_scraper.adapters.base import BrowserAdapter
from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.models import RawListing, SourceConfig


@AdapterRegistry.register("my_browser_portal")
class MyBrowserPortalAdapter(BrowserAdapter):
    """Scrapes jobs from My Browser Portal.

    This portal is a single-page app that requires JavaScript rendering.
    Uses Playwright for browser automation.

    Requires: pip install ijobs-scraper[browser]

    Config:
        base_url: Portal URL.
    """

    async def fetch_listings(self, config: SourceConfig):
        """Navigate the portal and extract job listings."""
        page = await self._launch_browser()
        try:
            await page.goto(f"{config.base_url}/careers", wait_until="networkidle")

            while True:
                # Wait for job cards to render
                await page.wait_for_selector("div.job-card", timeout=10000)
                cards = await page.query_selector_all("div.job-card")

                for card in cards:
                    title_el = await card.query_selector("h3.title")
                    link_el = await card.query_selector("a")

                    title = await title_el.inner_text() if title_el else None
                    href = await link_el.get_attribute("href") if link_el else None

                    if href:
                        yield RawListing(
                            external_url=href if href.startswith("http") else f"{config.base_url}{href}",
                            title=title,
                            company_name=config.name,
                        )

                # Try to click "Load More" or next page
                next_btn = await page.query_selector("button.load-more")
                if not next_btn or not await next_btn.is_enabled():
                    break
                await next_btn.click()
                await page.wait_for_load_state("networkidle")
        finally:
            await page.context.browser.close()

    def can_handle_url(self, url: str) -> bool:
        return "mybrowserportal.com" in url
```

**Key points:**
- `self._launch_browser()` returns a Playwright `Page` with sensible defaults
- Always close the browser in a `finally` block
- Use `wait_until="networkidle"` to ensure JS has finished rendering
- Browser adapters require the optional `[browser]` extra: `pip install ijobs-scraper[browser]`

## Step 3: Register the Adapter

The `@AdapterRegistry.register("name")` decorator handles registration. Ensure the module is imported by adding it to the appropriate `__init__.py`:

```python
# src/ijobs_scraper/adapters/api/__init__.py
from ijobs_scraper.adapters.api.my_portal import MyPortalAdapter  # noqa: F401
```

The adapter name you pass to `register()` is the value used in `SourceConfig.adapter`.

## Step 4: Write Tests

### Unit tests (required)

Every adapter must have unit tests with mocked HTTP responses. These run in CI on every PR.

```python
# tests/adapters/test_my_portal.py
import pytest
from ijobs_scraper.adapters.api.my_portal import MyPortalAdapter
from ijobs_scraper.models import SourceConfig, SourceType


@pytest.fixture
def config():
    return SourceConfig(
        name="My Portal",
        slug="my-portal",
        adapter="my_portal",
        source_type=SourceType.API,
        base_url="https://api.myportal.com",
    )


@pytest.fixture
def sample_response():
    """Mock response matching the portal's actual JSON format.

    Capture a real response and sanitize sensitive data.
    """
    return {
        "results": [
            {
                "id": 1001,
                "url": "https://myportal.com/jobs/1001",
                "title": "Software Engineer",
            },
            {
                "id": 1002,
                "url": "https://myportal.com/jobs/1002",
                "title": "Data Analyst",
            },
        ],
        "total_pages": 1,
    }


async def test_fetch_listings(config, sample_response, respx_mock):
    """Test that listings are correctly parsed from the API response."""
    respx_mock.get("https://api.myportal.com/api/jobs").respond(json=sample_response)

    adapter = MyPortalAdapter()
    listings = [listing async for listing in adapter.fetch_listings(config)]

    assert len(listings) == 2
    assert listings[0].title == "Software Engineer"
    assert listings[0].external_id == "1001"
    assert listings[0].external_url == "https://myportal.com/jobs/1001"
    assert listings[0].company_name == "My Portal"


async def test_fetch_listings_empty_response(config, respx_mock):
    """Test graceful handling of empty results."""
    respx_mock.get("https://api.myportal.com/api/jobs").respond(json={"results": [], "total_pages": 0})

    adapter = MyPortalAdapter()
    listings = [listing async for listing in adapter.fetch_listings(config)]

    assert len(listings) == 0


async def test_fetch_listings_pagination(config, respx_mock):
    """Test that pagination fetches all pages."""
    page1 = {"results": [{"id": 1, "url": "https://myportal.com/jobs/1", "title": "Job 1"}], "total_pages": 2}
    page2 = {"results": [{"id": 2, "url": "https://myportal.com/jobs/2", "title": "Job 2"}], "total_pages": 2}

    respx_mock.get("https://api.myportal.com/api/jobs", params={"page": 1, "per_page": 50}).respond(json=page1)
    respx_mock.get("https://api.myportal.com/api/jobs", params={"page": 2, "per_page": 50}).respond(json=page2)

    adapter = MyPortalAdapter()
    listings = [listing async for listing in adapter.fetch_listings(config)]

    assert len(listings) == 2


async def test_can_handle_url():
    """Test URL detection for the manual scraper."""
    adapter = MyPortalAdapter()
    assert adapter.can_handle_url("https://myportal.com/jobs/123") is True
    assert adapter.can_handle_url("https://other-site.com/jobs") is False
```

### Live tests (optional but encouraged)

Live tests hit the real portal API. They're excluded from default CI and run weekly to catch portal-side breaking changes.

```python
@pytest.mark.live
async def test_fetch_listings_live(config):
    """Live test — hits the real API. Run with: make test-live"""
    adapter = MyPortalAdapter()
    listings = [listing async for listing in adapter.fetch_listings(config)]

    assert len(listings) > 0
    for listing in listings:
        assert listing.external_url.startswith("http")
        assert listing.company_name == "My Portal"
```

Run live tests with:

```bash
make test-live
# or: pytest tests/ -v -m live
```

## Handling Common Challenges

### Pagination

Most portals paginate results. Handle this in `fetch_listings()`:

- **Offset-based:** Increment a `page` or `offset` parameter until results are empty
- **Cursor-based:** Follow a `next_cursor` or `next_url` from the response
- **Load More button:** For browser adapters, click the button and wait for new content

Always include a safety limit to prevent infinite loops:

```python
MAX_PAGES = 100

async def fetch_listings(self, config: SourceConfig):
    for page in range(1, MAX_PAGES + 1):
        data = await self._get(url, params={"page": page})
        if not data.get("results"):
            break
        for item in data["results"]:
            yield RawListing(...)
```

### Rate Limiting

The base adapter classes include configurable rate limiting. If a portal requires specific limits:

```python
class MyPortalAdapter(APIAdapter):
    # Override default delay between requests (seconds)
    request_delay: float = 2.0
    request_jitter: float = 0.5  # Random jitter added to delay
```

If you receive an HTTP 429 response, the adapter should raise `RateLimitError`:

```python
from ijobs_scraper.exceptions import RateLimitError

# In your adapter, if you need custom rate limit handling:
if response.status_code == 429:
    retry_after = int(response.headers.get("Retry-After", 60))
    raise RateLimitError(adapter="my_portal", retry_after=retry_after)
```

### Anti-Scraping Measures

Some portals use Cloudflare, CSRF tokens, or session cookies:

- **CSRF tokens:** Fetch the page first to extract the token, then include it in subsequent requests
- **Session cookies:** Use `self._get()` which shares an httpx session across requests within a scrape run
- **Cloudflare:** For basic Cloudflare protection, standard headers usually suffice. For advanced protection, use a `BrowserAdapter`
- **User-Agent:** The base classes set a reasonable User-Agent header. Override if needed.

### Missing Fields

Not all portals provide every field. That's fine — yield what you have:

```python
yield RawListing(
    external_url=item["url"],           # Required
    title=item.get("title"),            # Optional — AI enrichment can infer
    raw_json=item,                      # Include the full raw data
    company_name=config.name,           # From SourceConfig
    # external_id, raw_html, raw_text   # All optional
)
```

The AI enrichment pipeline extracts structured data from whatever raw content is available.

## Checklist

Before submitting your adapter PR:

- [ ] Adapter is in the correct directory (`api/`, `html/`, or `browser/`)
- [ ] Registered with `@AdapterRegistry.register("name")`
- [ ] Imported in the subdirectory's `__init__.py`
- [ ] `fetch_listings()` yields `RawListing` objects
- [ ] `can_handle_url()` implemented for manual scraper support
- [ ] Unit tests with mocked responses pass
- [ ] Live test added (marked with `@pytest.mark.live`)
- [ ] `make lint` passes
- [ ] Added to the Supported Sources table in `README.md`
- [ ] `CHANGELOG.md` entry added
