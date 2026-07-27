# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.6] - 2026-07-27

### Added

- Resumable source batches through `max_new_listings_per_batch` and
  `ScrapeResult.continuation_required`, allowing host queues to yield between
  batches without truncating a source crawl.
- Optional failed-listing checkpoints so permanent listing errors do not pin
  every continuation to the same URLs.

## [0.1.5] - 2026-07-27

### Added

- Bounded transient retries for API and HTML requests, including `Retry-After`
  handling for rate limits.
- Current NCBA Group first-party careers adapter.
- GAA-hosted public-sector advert PDF extraction for the legacy MyGov source.
- Live contract checks for ABSA, Impactpool, BrighterMonday, MyGov/GAA, NCBA,
  KCB, ReliefWeb, Amref, Kenya Airways, and Careerjet.

### Changed

- ABSA Workday scraping now uses the Candidate Experience JSON endpoints instead
  of browser automation.
- Impactpool scraping now uses its server-rendered Kenya search and detail pages
  instead of browser automation.
- AI enrichment input defaults to 16,000 characters and can be adjusted per
  source with `max_content_length` between 1,000 and 40,000 characters.
- Careerjet preserves the listing's employer name and sends a versioned client
  identifier.

### Fixed

- Current ABSA Workday instance and Kenya facet compatibility.
- MyGov redirects to the Government Advertising Agency vacancy table.
- Careerjet listing records now retain the actual employer rather than the
  aggregator name.

## [0.1.3] - 2026-04-16

### Added
- `.env.example` template with placeholder values for all environment variables
- Live integration tests for API adapters (`tests/adapters/test_api_live.py`)
- ReliefWeb appname configuration (`RELIEFWEB_APPNAME`)

### Fixed
- ReliefWeb adapter upgraded from decommissioned v1 API to v2 API (410 Gone)

## [0.1.1] - 2026-04-08

### Changed
- **BREAKING:** `user_ip` is now a required field in Careerjet adapter `SourceConfig.config`
  instead of defaulting to `127.0.0.1`. Callers must provide the end-user's real IP address.

### Fixed
- Careerjet adapter no longer silently sends `127.0.0.1` as the user IP, which violated
  Careerjet API terms and could cause request rejections.
- Kenya Airways adapter updated for iRec API migration (#9).

## [0.1.0] - 2026-04-02

### Added
- Project scaffold with pyproject.toml, Makefile, CI workflows
- Core data models: SourceConfig, RawListing, EnrichedJob, ScrapeResult
- Protocol interfaces: AIProvider, StorageBackend, JobCallback
- ScraperEngine orchestrator with scrape_source(), parse_url(), scrape_all()
- Adapter system: BaseAdapter, APIAdapter, HTMLAdapter, BrowserAdapter
- AdapterRegistry with @register() decorator and URL auto-detection
- EnrichmentPipeline with OpenAI structured output JSON schema
- DedupEngine with SHA-256 content hashing (Layer 1 + Layer 2)
- Cron scheduler via croniter
- Greenhouse API adapter (first reference implementation)
- Comprehensive unit test suite
- API adapters: kenya_airways, smartrecruiters, careerjet, reliefweb
- HTML adapters: brightermonday, myjobmag, mygov, fuzu, kcb
- Security-hardened HTMLAdapter base with sanitized headers and URL validation
- Browser adapters: workday (reusable for Absa + NCBA), impactpool, world_vision
- BrowserAdapter base class with Playwright lifecycle management
- Complete README with adapter catalog, usage examples, and configuration guide
- API reference documentation
- Step-by-step adapter contributor guide with templates for all 3 adapter types
- Standalone, FastAPI, and iJobs integration examples

[0.1.6]: https://github.com/mrrobotke/ijobs-scraper/releases/tag/v0.1.6
[0.1.5]: https://github.com/mrrobotke/ijobs-scraper/releases/tag/v0.1.5
[0.1.3]: https://github.com/mrrobotke/ijobs-scraper/releases/tag/v0.1.3
[0.1.1]: https://github.com/mrrobotke/ijobs-scraper/releases/tag/v0.1.1
[0.1.0]: https://github.com/mrrobotke/ijobs-scraper/releases/tag/v0.1.0
