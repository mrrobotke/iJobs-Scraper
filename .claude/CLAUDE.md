

PROJECT BRIEF

**ijobs-scraper**

Open-Source Job Scraping & AI Enrichment Engine

Team Lead Assignment & Project Kickoff Document

April 2026

| GitHub Org | mrrobotke |
| :---- | :---- |
| **Repository** | ijobs-scraper |
| **License** | MIT |
| **Python** | \>= 3.12 |
| **Package** | pip install ijobs-scraper |
| **Status** | Greenfield — New project |

# **1\. Purpose & Context**

You are being assigned as the technical team lead to build and ship a new open-source Python package called ijobs-scraper. This package is the scraping and AI enrichment engine that powers the iJobs platform — a next-generation job marketplace for the African market.

This document contains everything you need: the project scope, architecture decisions already made, repository setup requirements, team structure, milestones, and quality standards. Your job is to create the team, set up the repo under the mrrobotke GitHub org, and deliver a production-ready v1.0 on PyPI within 8 weeks.

## **1.1 What This Package Does**

* **Auto Scraper:** Scheduled background scraping of 60+ Kenyan vacancy portals via pluggable adapters. Runs on cron schedules, fetches job listings, enriches them through OpenAI structured outputs, deduplicates across sources, and emits structured job data through a callback interface.

* **Manual Scraper:** On-demand URL parsing. A user pastes a job URL, the engine auto-detects the source, fetches content, runs it through the same AI pipeline, and returns structured job data ready for form pre-fill.

## **1.2 Why Standalone Package**

* **Reusability:** Any Python application can integrate it, not just iJobs

* **Testability:** Full test suite runs without a database, web framework, or live API keys

* **Open-source growth:** Other developers can contribute adapters for their own job portals/markets

* **Clean separation:** The iJobs backend imports and configures the package via dependency injection — zero coupling

# **2\. GitHub Repository Setup**

**Repository:** [github.com/mrrobotke/ijobs-scraper](https://github.com/mrrobotke/ijobs-scraper)

**Visibility:** Public

**Default branch:** main

## **2.1 Day-One Repository Contents**

Before any feature work begins, the repo must have this foundation committed to main:

ijobs-scraper/  
├── .github/  
│   ├── workflows/  
│   │   ├── ci.yml                \# Lint \+ test on every PR  
│   │   ├── release.yml            \# Publish to PyPI on tag  
│   │   └── adapter-test.yml       \# Weekly live adapter smoke tests  
│   ├── ISSUE\_TEMPLATE/  
│   │   ├── bug\_report.md  
│   │   ├── feature\_request.md  
│   │   └── new\_adapter.md         \# Template for contributing adapters  
│   ├── PULL\_REQUEST\_TEMPLATE.md  
│   └── CODEOWNERS  
├── src/  
│   └── ijobs\_scraper/  
│       ├── \_\_init\_\_.py  
│       ├── engine.py  
│       ├── models.py  
│       ├── protocols.py  
│       ├── enrichment.py  
│       ├── dedup.py  
│       ├── scheduler.py  
│       ├── exceptions.py  
│       ├── \_registry.py  
│       └── adapters/  
│           ├── \_\_init\_\_.py  
│           ├── base.py  
│           ├── api/  
│           ├── html/  
│           └── browser/  
├── tests/  
│   ├── conftest.py  
│   └── adapters/  
├── docs/  
│   ├── architecture.md            \# Link to iJobs arch doc  
│   ├── adding-an-adapter.md       \# Step-by-step contributor guide  
│   └── api-reference.md           \# Auto-generated or manual API docs  
├── examples/  
│   ├── standalone\_scrape.py  
│   ├── fastapi\_integration.py  
│   └── ijobs\_integration.py  
├── pyproject.toml  
├── README.md  
├── CONTRIBUTING.md  
├── CHANGELOG.md  
├── LICENSE                        \# MIT  
├── Makefile  
└── .pre-commit-config.yaml

## **2.2 Branch Protection Rules**

* main branch: require PR with at least 1 approval

* Require passing CI (lint \+ tests) before merge

* No direct push to main (including admins)

* Squash merge only — keeps history clean

* Delete branch on merge

## **2.3 CI/CD Pipeline (GitHub Actions)**

### **ci.yml — Runs on every PR and push to main**

1. Checkout \+ setup Python 3.12, 3.13

2. make lint — ruff check \+ ruff format \--check \+ mypy \--strict

3. make test — pytest with coverage (minimum 80% for core, 60% for adapters)

4. Upload coverage report as artifact

### **release.yml — Triggers on git tag v\***

5. Build wheel with hatchling

6. Publish to PyPI via trusted publisher (OIDC, no API key)

7. Create GitHub Release with auto-generated notes

### **adapter-test.yml — Weekly schedule (Sunday 6 AM UTC)**

8. Run live smoke tests against real portal APIs (Kenya Airways, Greenhouse, SmartRecruiters, Careerjet)

9. Post results to a Slack/Discord webhook or GitHub issue on failure

*This catches portal-side breaking changes (URL changes, API deprecations) before users report them.*

## **2.4 Makefile**

install:       uv sync \--all-extras  
lint:          ruff check src/ tests/ && ruff format \--check src/ tests/ && mypy src/  
format:        ruff check \--fix src/ tests/ && ruff format src/ tests/  
test:          pytest tests/ \-v \--cov=ijobs\_scraper \--cov-report=term-missing  
test-live:     pytest tests/ \-v \-m live  \# Real API tests (not in CI by default)  
build:         python \-m build  
docs:          \# Generate API docs (pdoc or mkdocs)

# **3\. README.md Requirements**

The README is the first thing any developer sees. It must be excellent. Here is the exact structure and content required:

## **3.1 Required Sections (in order)**

| Section | Content Requirements |
| :---- | :---- |
| **Header \+ Badges** | Package name, one-line description, PyPI badge, CI badge, Python version badge, License badge, Downloads badge |
| **Features** | 6-8 bullet points: pluggable adapters, AI enrichment, 3-layer dedup, async-first, framework-agnostic, type-safe, cron scheduling, open-source |
| **Quick Start** | pip install, 10-line working example that scrapes One Acre Fund via Greenhouse API with a stub AI provider. Must be copy-pasteable and actually run. |
| **Supported Sources** | Table of all 13 adapters with name, type (API/HTML/Browser), portal, and status (stable/beta/planned) |
| **How It Works** | Short paragraph \+ diagram (link to rendered PNG from docs/) showing: Source → Adapter → Raw Listing → AI Enrichment → Dedup → EnrichedJob |
| **Architecture** | Link to full architecture doc. Brief mention of Protocol-based DI, adapter registry, and zero framework coupling. |
| **Usage Examples** | 3 examples: (1) Scrape a source, (2) Parse a single URL, (3) Integrate with FastAPI |
| **Adding an Adapter** | Short 5-step guide with link to full CONTRIBUTING.md. Lower the barrier: 'Adding a new job portal takes \~50 lines of code' |
| **Configuration** | SourceConfig model fields with descriptions. How to pass adapter-specific config. |
| **API Reference** | Link to full API docs (pdoc or mkdocs). Quick list of main exports. |
| **Contributing** | Link to CONTRIBUTING.md. Mention: issues welcome, adapter PRs especially welcome, code of conduct. |
| **License** | MIT — one line |

## **3.2 README Quality Bar**

* Must include a working Quick Start that a developer can copy-paste and get output in under 2 minutes

* All code examples must be tested in CI (use doctest or a dedicated examples test)

* No placeholder text, no 'TODO' markers, no broken links

* Badge URLs must be correct and showing live data once published

* **Tone:** Professional but welcoming. This is an open-source project that wants contributors.

# **4\. CONTRIBUTING.md & Open-Source Standards**

## **4.1 CONTRIBUTING.md Must Cover**

10. Development setup (clone, make install, make test)

11. Code style (ruff, mypy strict, import ordering)

12. How to add a new adapter (step-by-step with code template)

13. How to write tests (unit vs live, marking live tests with @pytest.mark.live)

14. PR process (branch naming, commit messages, what reviewers look for)

15. Issue labels and how to pick up work

## **4.2 Adding an Adapter Guide**

This is the most important contributor workflow. The guide (also in docs/adding-an-adapter.md) must include:

16. **Step 1:** Create the adapter file in the correct directory (api/, html/, or browser/)

17. **Step 2:** Subclass the right base (APIAdapter, HTMLAdapter, or BrowserAdapter)

18. **Step 3:** Implement fetch\_listings() and optionally fetch\_detail() and can\_handle\_url()

19. **Step 4:** Register with @AdapterRegistry.register("my\_portal")

20. **Step 5:** Add tests (unit test with mocked responses \+ optional live test)

21. **Step 6:** Update the adapter catalog in README.md

Include a complete, annotated code template that contributors can copy:

\# src/ijobs\_scraper/adapters/api/my\_portal.py  
from ijobs\_scraper.adapters.base import APIAdapter, AdapterRegistry  
from ijobs\_scraper.models import RawListing, SourceConfig

@AdapterRegistry.register("my\_portal")  
class MyPortalAdapter(APIAdapter):  
    """Scrapes jobs from My Portal."""

    async def fetch\_listings(self, config: SourceConfig):  
        data \= await self.\_get(f"{config.base\_url}/jobs")  
        for item in data\["results"\]:  
            yield RawListing(  
                external\_id=str(item\["id"\]),  
                external\_url=item\["url"\],  
                title=item.get("title"),  
                raw\_json=item,  
                company\_name=config.name,  
            )

    def can\_handle\_url(self, url: str) \-\> bool:  
        return "myportal.com" in url

## **4.3 Issue Labels**

| Label | Color | Use For |
| :---- | :---- | :---- |
| good first issue | \#7057ff | Simple adapter additions, doc fixes, test improvements |
| new-adapter | \#0E8A16 | PRs that add a new portal adapter |
| bug | \#D73A4A | Something broken |
| enhancement | \#A2EEEF | New features or improvements to core |
| help wanted | \#008672 | Issues where community help is needed |
| breaking-change | \#B60205 | Changes that affect the public API |
| priority: critical | \#E11D48 | Must be fixed before next release |
| priority: high | \#F97316 | Should be in next sprint |

# **5\. Architecture Summary**

The full architecture document is already written and available in the iJobs backend repo at docs/architecture/scraper-engine.md. It includes 5 PlantUML diagrams (rendered to PNG). Below is the summary your team needs to internalize.

## **5.1 Core Design Principles**

* **Zero framework coupling** — no FastAPI, SQLAlchemy, or ORM imports inside the package. The host application provides persistence and AI via Protocol interfaces.

* **Protocol-based DI** — three interfaces the host app implements: AIProvider (OpenAI calls), StorageBackend (persistence), JobCallback (what to do with enriched jobs)

* **Pluggable adapters** — each portal is a self-contained class registered via @AdapterRegistry.register(). Adding a source \= adding a file.

* **Async-first** — all I/O uses async/await. httpx for HTTP, playwright for browsers.

* **Type-safe** — Pydantic v2 models throughout. mypy strict passes.

## **5.2 Key Components**

| Component | Responsibility |
| :---- | :---- |
| **ScraperEngine** | Main orchestrator. Exposes scrape\_source(), parse\_url(), scrape\_all(). Coordinates adapters, enrichment, dedup, and callbacks. |
| **AdapterRegistry** | Maps adapter names to classes. Auto-detects adapter from URL for manual scraping. |
| **BaseAdapter** | Abstract base. Subclassed as APIAdapter (httpx), HTMLAdapter (BeautifulSoup), BrowserAdapter (Playwright). |
| **EnrichmentPipeline** | Takes raw content, calls AIProvider.structured\_extract() with a JSON schema, returns validated EnrichedJob. |
| **DedupEngine** | Three-layer dedup: (1) source URL uniqueness, (2) SHA-256 content hash, (3) optional fuzzy matching (host app). |
| **Scheduler** | Evaluates cron expressions via croniter. Returns which sources are due. Does NOT enqueue — that's the host app's job. |
| **Models** | Pydantic v2: SourceConfig, RawListing, EnrichedJob, ScrapeResult, JobRequirements. |
| **Protocols** | AIProvider, StorageBackend, JobCallback — structural subtyping interfaces for the host app. |

## **5.3 Adapter Catalog (13 Adapters)**

| Portal | Type | Reusable | Notes |
| :---- | :---- | :---- | :---- |
| **Kenya Airways** | API | No | iRec REST API. Full JSON. No auth. |
| **One Acre Fund** | API | Yes | Greenhouse public board API. board\_token config. |
| **Amref Health Africa** | API | Yes | SmartRecruiters. Slug: AmrefHealthAfrica4. |
| **Careerjet Kenya** | API | Yes | Official Python SDK. Indexes 60+ sites. Biggest coverage multiplier. |
| **ReliefWeb** | API | No | UN OCHA API. Appname registration done, pending approval. |
| **BrighterMonday** | HTML | No | Laravel. Cloudflare \+ CSRF. Needs session handling. |
| **MyJobMag** | HTML | No | PHP. Cloudflare headers. Straightforward HTML parsing. |
| **MyGov Kenya** | HTML | No | Government portal at /job-adverts. |
| **Fuzu Kenya** | HTML | No | Rails. Server-rendered. All /api/ routes return 403\. |
| **KCB Bank** | HTML | No | Custom PHP 7.4 careers page. |
| **Absa Bank** | Browser | Yes | Workday. Requires Playwright for session auth. |
| **NCBA Bank** | Browser | Yes | Workday. Same adapter as Absa with different config. |
| **Impactpool** | Browser | No | Rails \+ Stimulus. Check /feeds/ for RSS. |

## **5.4 Reference Documents**

The following documents have already been created and are available in the iJobs backend repo. Your team should read all of them:

22. **Architecture & Requirements:** docs/architecture/scraper-engine.md — Full 16-section technical spec with code examples

23. **PlantUML Diagrams:** docs/architecture/diagrams/scraper/\*.puml — 5 diagrams (package structure, data flow, integration, sequence, DB schema) with rendered PNGs

24. **API Discovery Report:** docs/scraper-api-discovery-report-v1.3.docx — Complete audit of all portal APIs, endpoints, and accessibility

25. **Implementation Plan:** docs/scraper-implementation-plan.docx — Original 10-section plan with portal research findings

# **6\. Team Structure & Roles**

Recommended team size: 3-4 engineers including the team lead.

| Role | Focus | Requirements |
| :---- | :---- | :---- |
| **Team Lead (You)** | Architecture \+ core | Owns ScraperEngine, protocols, enrichment pipeline, dedup, CI/CD, code review. Writes BaseAdapter classes and at least 2 reference adapters. |
| **Backend Dev 1** | API adapters | Builds Kenya Airways, Greenhouse, SmartRecruiters, Careerjet, ReliefWeb adapters. Strong with httpx, REST APIs, Pydantic. |
| **Backend Dev 2** | HTML \+ Browser adapters | Builds BrighterMonday, MyJobMag, MyGov, Fuzu, KCB, Workday, Impactpool adapters. Strong with BeautifulSoup and Playwright. |
| **Backend Dev 3 (optional)** | iJobs integration | Builds bridge layer (IJobsAIProvider, IJobsStorage, JobCallback), Alembic migrations, admin API endpoints, background tasks. Knows iJobs codebase. |

# **7\. Milestones & Deliverables**

8-week timeline. Each milestone has a clear definition of done.

| Milestone | Deadline | Deliverables | Definition of Done |
| :---- | :---- | :---- | :---- |
| **M0: Repo** | **Day 1** | GitHub repo with full scaffold, README, CI, CONTRIBUTING, LICENSE, Makefile, pyproject.toml | make lint and make test pass on empty project. README renders correctly. |
| **M1: Core** | **Week 2** | ScraperEngine, models, protocols, enrichment pipeline, dedup, BaseAdapter classes, AdapterRegistry, Scheduler | Unit tests pass with mock AI provider. pip install \-e . works. mypy strict passes. |
| **M2: APIs** | **Week 3** | 5 API adapters (Kenya Airways, Greenhouse, SmartRecruiters, Careerjet, ReliefWeb) | Live smoke tests pass. Each adapter returns valid RawListings from real endpoints. |
| **M3: HTML** | **Week 4** | 5 HTML adapters (BrighterMonday, MyJobMag, MyGov, Fuzu, KCB) | Unit tests with mocked HTML. At least 2 live smoke tests pass. |
| **M4: Browser** | **Week 5** | 3 browser adapters (Workday, Impactpool, World Vision) | Playwright tests pass in CI (headless). Workday adapter works for both Absa and NCBA configs. |
| **M5: Docs** | **Week 6** | Complete README, API reference, adding-an-adapter guide, all examples tested | A new contributor can add an adapter by following the guide with zero questions. |
| **M6: v0.1.0** | **Week 7** | First PyPI release. CHANGELOG. GitHub Release. | pip install ijobs-scraper works. All examples run. CI green on Python 3.12 \+ 3.13. |
| **M7: Integrate** | **Week 8** | iJobs backend integration: bridge, migrations, admin API, background tasks | End-to-end: trigger scrape → adapter fetches → OpenAI enriches → job appears in DB with status=pending. |

# **8\. Quality Standards**

## **8.1 Code Quality**

* **Linter:** ruff — same config as iJobs backend (line-length=100, select E,F,I,B,UP,SIM,C4)

* **Formatter:** ruff format — double quotes, spaces, LF line endings

* **Type checker:** mypy \--strict — no Any escapes except for json\_schema dicts

* **Pre-commit hooks:** ruff \+ ruff-format \+ mypy run before every commit

## **8.2 Testing**

* **Framework:** pytest \+ pytest-asyncio \+ pytest-cov

* **Coverage:** Minimum 80% on core (engine, enrichment, dedup, models). Minimum 60% on adapters.

* **Unit tests:** Every adapter must have unit tests with mocked HTTP responses (use pytest-httpx or respx)

* **Live tests:** Marked with @pytest.mark.live. Not in default CI. Run weekly via adapter-test.yml.

* **Example tests:** All README code examples must be tested (doctest or dedicated test file)

## **8.3 Documentation**

* **Docstrings:** Google-style on all public classes and methods

* **Type hints:** 100% coverage on all public APIs

* **CHANGELOG:** Keep-a-Changelog format. Updated with every PR.

* **Commit messages:** Conventional commits (feat:, fix:, docs:, chore:, test:)

## **8.4 PR Review Checklist**

26. Does it pass CI (lint \+ test \+ mypy)?

27. Does it include tests?

28. Does it update documentation if needed?

29. Does it update CHANGELOG.md?

30. Is the adapter registered in AdapterRegistry?

31. Is the adapter added to the README table?

32. Are there no framework imports (no fastapi, sqlalchemy, django)?

# **9\. Technical Decisions (Already Made)**

These decisions are final and should not be re-debated:

| Decision | Choice | Rationale |
| :---- | :---- | :---- |
| **Build backend** | hatchling | Already used by iJobs. Simple, fast, standard. |
| **HTTP client** | httpx (async) | Already in iJobs. Async-native. No requests dependency. |
| **HTML parsing** | beautifulsoup4 \+ lxml | Industry standard. lxml for speed. |
| **Browser automation** | playwright | More reliable than Selenium. Better async support. |
| **Data models** | pydantic v2 | Type-safe, fast, serializable. Already in iJobs. |
| **Cron parsing** | croniter | Lightweight. Battle-tested. |
| **AI provider** | Protocol (no OpenAI SDK) | Host app provides implementation. Package has zero AI deps. |
| **Dedup hashing** | SHA-256 | Deterministic, fast, collision-resistant. |
| **Package manager** | uv (dev), pip (users) | uv for development speed. Standard pip for end users. |
| **Python versions** | 3.12+ | Matches iJobs. Uses modern syntax (type hints, match, etc.). |
| **Test framework** | pytest \+ pytest-asyncio | Standard. Good async support. |
| **Linter/formatter** | ruff | Fast. Replaces flake8 \+ isort \+ black. |

# **10\. PyPI Publishing Setup**

## **10.1 Trusted Publisher (OIDC)**

Use PyPI trusted publishers instead of API tokens. This is more secure and doesn't require storing secrets.

33. Create the ijobs-scraper project on PyPI

34. Configure trusted publisher: GitHub Actions, repository mrrobotke/ijobs-scraper, workflow release.yml

35. Tag a release (git tag v0.1.0 && git push \--tags) to trigger automatic publishing

## **10.2 Versioning**

* **Scheme:** Semantic Versioning (MAJOR.MINOR.PATCH)

* **Pre-1.0:** 0.x releases. Minor bumps can break API. Patch bumps are bug fixes.

* **1.0 criteria:** All 13 adapters stable, full test coverage, iJobs integration proven in production, at least 2 external contributors

## **10.3 Package Metadata**

\[project\]  
name \= "ijobs-scraper"  
description \= "Job scraping & AI enrichment engine for African job markets"  
keywords \= \["scraping", "jobs", "ai", "openai", "kenya", "africa", "nlp"\]  
classifiers \= \[  
    "Development Status :: 3 \- Alpha",  
    "Intended Audience :: Developers",  
    "License :: OSI Approved :: MIT License",  
    "Programming Language :: Python :: 3.12",  
    "Programming Language :: Python :: 3.13",  
    "Topic :: Internet :: WWW/HTTP :: Indexing/Search",  
\]  
\[project.urls\]  
Homepage \= "https://github.com/mrrobotke/ijobs-scraper"  
Documentation \= "https://github.com/mrrobotke/ijobs-scraper\#readme"  
Repository \= "https://github.com/mrrobotke/ijobs-scraper"  
"Bug Tracker" \= "https://github.com/mrrobotke/ijobs-scraper/issues"

# **11\. Success Criteria**

The project is considered successful when ALL of the following are true:

| \# | Criterion |
| :---- | :---- |
| **1** | pip install ijobs-scraper installs from PyPI and all examples run without modification |
| **2** | All 13 adapters return valid job listings (5 API, 5 HTML, 3 Browser) |
| **3** | A new contributor can add an adapter by following docs alone (validated by having at least 1 external PR merged) |
| **4** | CI passes on Python 3.12 and 3.13 with 80%+ core coverage |
| **5** | iJobs backend can trigger a scrape, enrich via OpenAI, and create a job with status=pending in the database |
| **6** | Manual scraper endpoint accepts a URL and returns structured job data in under 15 seconds |
| **7** | Dedup correctly identifies cross-source duplicates (same job on Careerjet and direct employer site) |
| **8** | README is professional quality with working badges, examples, and architecture diagram |
| **9** | CHANGELOG has entries for every PR, following Keep-a-Changelog format |
| **10** | Repository has proper labels, issue templates, PR template, and branch protection |

# **12\. Immediate Next Steps (Your First Week)**

**Day 1:**

36. Create the GitHub repo at mrrobotke/ijobs-scraper (public, MIT license)

37. Set up branch protection on main

38. Commit the full project scaffold (pyproject.toml, src/, tests/, Makefile, .github/)

39. Write and commit README.md with all required sections

40. Write and commit CONTRIBUTING.md with adapter guide

41. Set up CI workflow (ci.yml) — verify make lint and make test pass

**Day 2-3:**

42. Implement core models (SourceConfig, RawListing, EnrichedJob, ScrapeResult) in models.py

43. Implement protocols (AIProvider, StorageBackend, JobCallback) in protocols.py

44. Implement AdapterRegistry and BaseAdapter classes

45. Implement ScraperEngine with scrape\_source() and parse\_url()

46. Write unit tests with a StubAIProvider

**Day 4-5:**

47. Implement EnrichmentPipeline with the JSON schema

48. Implement DedupEngine (Layer 1 \+ 2\)

49. Build the first reference adapter: GreenhouseAdapter (simplest API, reusable)

50. Verify end-to-end: engine.scrape\_source() with Greenhouse returns EnrichedJob objects

51. Assign adapters to team members and create GitHub issues for each

**Questions?** Reach out directly. The architecture doc (docs/architecture/scraper-engine.md) and API discovery report (docs/scraper-api-discovery-report-v1.3.docx) are your primary references. Everything you need to start building is there.

*End of Project Brief — ijobs-scraper*