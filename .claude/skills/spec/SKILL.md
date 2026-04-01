---
name: spec
description: Load the full architecture specification and portal audit report into context. Use when starting implementation or referencing exact model fields, protocol signatures, or adapter details.
---

Load and review the full project specifications:

1. Read `@docs/scraper-engine.md` — complete architecture including:
   - §2: Package structure and pyproject.toml
   - §4: Public API and protocol interfaces
   - §5: Data models (SourceConfig, RawListing, EnrichedJob, ScrapeResult)
   - §6: Adapter system and registry
   - §7: OpenAI enrichment pipeline and JSON schema
   - §8: Deduplication strategy (three-layer)
   - §9: Engine orchestration (scrape_source, parse_url)
   - §13: Error handling and exception hierarchy
   - §14: Implementation phases (6 phases, weeks 1–8)

2. Read `@docs/scraper-api-discovery-report-v1_3.md` — portal audit with:
   - Confirmed API endpoints and authentication requirements
   - Tier classifications (Tier 0: API, Tier 1: partial, Tier 2: scraping)
   - Tech stacks and anti-bot measures per portal
   - Implementation priority order

Summarize the key points relevant to the current task context.
