# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.1]: https://github.com/mrrobotke/ijobs-scraper/releases/tag/v0.1.1
[0.1.0]: https://github.com/mrrobotke/ijobs-scraper/releases/tag/v0.1.0
