# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
