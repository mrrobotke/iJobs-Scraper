# Contributing to ijobs-scraper

Thank you for your interest in contributing! Whether you're adding a new job portal adapter, fixing a bug, or improving documentation, your help is appreciated.

## Development Setup

```bash
git clone https://github.com/mrrobotke/ijobs-scraper.git
cd ijobs-scraper
make install    # or: pip install -e ".[dev,all]"
make test       # verify everything works
make lint       # check code style
```

**Requirements:** Python 3.12+ and [uv](https://docs.astral.sh/uv/) (recommended) or pip.

## Code Style

- **Linter/formatter:** [ruff](https://docs.astral.sh/ruff/) with `line-length=100`
- **Type checker:** `mypy --strict` — all public APIs must have type annotations
- **Docstrings:** Google-style on all public classes and methods
- **Imports:** Sorted by ruff (isort-compatible). Standard library, third-party, then local.
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) format:
  - `feat: add greenhouse adapter`
  - `fix: handle empty response from Kenya Airways API`
  - `docs: update adapter catalog in README`
  - `test: add unit tests for dedup engine`
  - `chore: update ruff to 0.4.x`

Run `make format` to auto-fix style issues before committing.

## Adding a New Adapter

This is the most common and most welcome type of contribution. Each job portal gets its own adapter — a self-contained class that knows how to fetch listings from that specific source.

### Step 1: Choose your adapter type

| Type | Base Class | Use When | Dependencies |
|------|-----------|----------|--------------|
| **API** | `APIAdapter` | Portal has a REST/JSON API | `httpx` (core) |
| **HTML** | `HTMLAdapter` | Portal serves server-rendered HTML | `beautifulsoup4` + `lxml` (core) |
| **Browser** | `BrowserAdapter` | Portal requires JavaScript rendering | `playwright` (optional extra) |

### Step 2: Create the adapter file

Place your adapter in the correct subdirectory:

```
src/ijobs_scraper/adapters/
├── api/           # REST API adapters
│   └── my_portal.py
├── html/          # HTML scraping adapters
│   └── my_portal.py
└── browser/       # Playwright browser adapters
    └── my_portal.py
```

### Step 3: Implement the adapter

Here is a complete, annotated template for an API adapter:

```python
# src/ijobs_scraper/adapters/api/my_portal.py
from ijobs_scraper.adapters.base import APIAdapter
from ijobs_scraper._registry import AdapterRegistry
from ijobs_scraper.models import RawListing, SourceConfig


@AdapterRegistry.register("my_portal")
class MyPortalAdapter(APIAdapter):
    """Scrapes jobs from My Portal.

    Config:
        base_url: The portal's API base URL.
        config: No additional config required.
    """

    async def fetch_listings(self, config: SourceConfig):
        """Fetch all job listings from the portal.

        Yields RawListing objects for each job found. The engine
        handles enrichment, dedup, and persistence.
        """
        data = await self._get(f"{config.base_url}/jobs")
        for item in data["results"]:
            yield RawListing(
                external_id=str(item["id"]),
                external_url=item["url"],
                title=item.get("title"),
                raw_json=item,
                company_name=config.name,
            )

    def can_handle_url(self, url: str) -> bool:
        """Return True if this adapter can parse the given URL.

        Used by the manual scraper to auto-detect the right adapter
        when a user pastes a job URL.
        """
        return "myportal.com" in url
```

### Step 4: Register and import

The `@AdapterRegistry.register("my_portal")` decorator handles registration automatically. Make sure the module is imported — add it to `src/ijobs_scraper/adapters/api/__init__.py` (or the corresponding `html/` or `browser/` init file).

### Step 5: Add tests

Create a test file at `tests/adapters/test_my_portal.py`:

```python
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
    """Mock API response matching the portal's actual format."""
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
        ]
    }


async def test_fetch_listings(config, sample_response, respx_mock):
    respx_mock.get("https://api.myportal.com/jobs").respond(json=sample_response)

    adapter = MyPortalAdapter()
    listings = [listing async for listing in adapter.fetch_listings(config)]

    assert len(listings) == 2
    assert listings[0].title == "Software Engineer"
    assert listings[0].external_id == "1001"
    assert listings[0].company_name == "My Portal"


async def test_can_handle_url():
    adapter = MyPortalAdapter()
    assert adapter.can_handle_url("https://myportal.com/jobs/123") is True
    assert adapter.can_handle_url("https://other-site.com/jobs/456") is False


@pytest.mark.live
async def test_fetch_listings_live(config):
    """Live test — hits the real API. Run with: make test-live"""
    adapter = MyPortalAdapter()
    listings = [listing async for listing in adapter.fetch_listings(config)]
    assert len(listings) > 0
    for listing in listings:
        assert listing.external_url
        assert listing.company_name == "My Portal"
```

### Step 6: Update documentation

- Add your portal to the **Supported Sources** table in `README.md`
- Update `CHANGELOG.md` with a `feat:` entry

See [docs/adding-an-adapter.md](docs/adding-an-adapter.md) for a more detailed guide covering pagination, rate limits, error handling, and anti-scraping measures.

## Writing Tests

### Unit tests

Every adapter and core module must have unit tests. Use mocked HTTP responses — never hit real APIs in default CI.

- **HTTP mocking:** Use [respx](https://lundberg.github.io/respx/) for `httpx`-based adapters
- **Async tests:** All async tests are auto-detected by `pytest-asyncio`
- **Fixtures:** Shared fixtures live in `tests/conftest.py`

```bash
make test              # Run all unit tests
pytest tests/ -v -k "test_greenhouse"  # Run specific tests
```

### Live tests

Tests that hit real APIs are marked with `@pytest.mark.live` and excluded from default CI. They run weekly via the `adapter-test.yml` workflow to catch portal-side breaking changes.

```bash
make test-live         # Run live tests against real APIs
```

### Test file naming

```
tests/
├── conftest.py                    # Shared fixtures
├── test_engine.py                 # ScraperEngine tests
├── test_enrichment.py             # Enrichment pipeline tests
├── test_dedup.py                  # Dedup engine tests
├── test_scheduler.py              # Scheduler tests
└── adapters/
    ├── test_greenhouse.py         # One test file per adapter
    ├── test_kenya_airways.py
    └── ...
```

## PR Process

### Branch naming

```
feat/greenhouse-adapter     # New feature or adapter
fix/dedup-hash-collision    # Bug fix
docs/adapter-guide          # Documentation change
test/engine-edge-cases      # Test improvements
chore/update-dependencies   # Maintenance
```

### Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add SmartRecruiters adapter
fix: handle pagination for Kenya Airways API
docs: add configuration examples to README
test: improve coverage for enrichment pipeline
chore: bump httpx to 0.28
```

### PR checklist

Before submitting your PR, verify:

- [ ] `make lint` passes (ruff check + ruff format --check + mypy --strict)
- [ ] `make test` passes with adequate coverage
- [ ] New adapter is registered with `@AdapterRegistry.register()`
- [ ] New adapter is added to the Supported Sources table in README.md
- [ ] Tests include unit tests with mocked responses
- [ ] Docstrings added to all public classes and methods
- [ ] `CHANGELOG.md` updated
- [ ] No framework imports (no fastapi, sqlalchemy, django) inside `src/ijobs_scraper/`

### What reviewers look for

1. **Correctness** — Does the adapter actually parse the portal's response format?
2. **Error handling** — Does it handle empty responses, missing fields, and HTTP errors gracefully?
3. **Rate limiting** — Does it respect the portal's rate limits?
4. **Test quality** — Are edge cases covered? Are mocked responses realistic?
5. **Type safety** — Does `mypy --strict` pass?
6. **No framework coupling** — Zero imports from web frameworks inside the package

## Issue Labels

| Label | Color | Use For |
|-------|-------|---------|
| `good first issue` | ![#7057ff](https://placehold.co/15x15/7057ff/7057ff.png) | Simple adapter additions, doc fixes, test improvements |
| `new-adapter` | ![#0E8A16](https://placehold.co/15x15/0E8A16/0E8A16.png) | PRs that add a new portal adapter |
| `bug` | ![#D73A4A](https://placehold.co/15x15/D73A4A/D73A4A.png) | Something broken |
| `enhancement` | ![#A2EEEF](https://placehold.co/15x15/A2EEEF/A2EEEF.png) | New features or improvements to core |
| `help wanted` | ![#008672](https://placehold.co/15x15/008672/008672.png) | Issues where community help is needed |
| `breaking-change` | ![#B60205](https://placehold.co/15x15/B60205/B60205.png) | Changes that affect the public API |
| `priority: critical` | ![#E11D48](https://placehold.co/15x15/E11D48/E11D48.png) | Must be fixed before next release |
| `priority: high` | ![#F97316](https://placehold.co/15x15/F97316/F97316.png) | Should be in next sprint |

## Getting Help

- Open an [issue](https://github.com/mrrobotke/ijobs-scraper/issues) for bugs or feature requests
- Use the `new-adapter` issue template when proposing a new portal
- Check the [architecture doc](docs/scraper-engine.md) for technical details
- See [docs/adding-an-adapter.md](docs/adding-an-adapter.md) for the complete adapter development guide
