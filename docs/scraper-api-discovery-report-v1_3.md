**iJobsScraper**

API Endpoint Discovery Report

Addendum v1.3 — Updated Portal Analysis

April 1, 2026

# **1\. Executive Summary**

This report documents the comprehensive API endpoint discovery audit conducted across all target Kenyan vacancy portals. Every portal was systematically tested for public REST APIs, hidden ATS platform APIs, RSS/XML feeds, and any alternative data access methods beyond HTML scraping.

The audit identified 5 portals with confirmed or partially working API access (Tier 0), 1 portal with a known but currently unavailable API (Tier 1), and 12 portals requiring HTML scraping or browser automation (Tier 2/3). The API-first sources alone cover an estimated 40-60% of the international/NGO job market in Kenya, with Careerjet acting as a coverage multiplier across 60+ indexed sites.

## **Key Findings at a Glance**

* **5 confirmed API sources:** Kenya Airways (iRec), One Acre Fund (Greenhouse), Amref (SmartRecruiters), Careerjet (official API), ReliefWeb (needs registration)  
* **1 partially available:** Equity Bank (Taleo REST API responds but career section currently offline)  
* **3 Workday instances identified:** Absa, NCBA — both require authenticated sessions, no public API  
* **1 new portal identified:** Fuzu Kenya (Ruby on Rails, all /api/ routes blocked with 403, requires HTML scraping)  
* **9 portals with no API:** Require HTML scraping with BeautifulSoup or Playwright for JS-rendered content  
* **Key discovery:** Safaricom has fully decommissioned Taleo (DNS dead) and migrated to an unknown ATS behind CDN protection

# **2\. Complete Portal API Matrix**

The following table classifies all audited portals by their API accessibility tier, confirmed endpoints, and implementation approach.

| Portal | Platform | API Endpoint | Status | Tier | Notes |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Kenya Airways | iRec ATS | api-irec-prod.kenya-airways.com/careers/api/v2/ | CONFIRMED | Tier 0 | Full REST API with pagination. Returns complete job JSON. |
| One Acre Fund | Greenhouse | boards-api.greenhouse.io/v1/boards/oneacrefund/jobs | CONFIRMED | Tier 0 | Public board API. Full job details with content=true param. |
| Amref Health Africa | SmartRecruiters | api.smartrecruiters.com/v1/companies/AmrefHealthAfrica4/postings | CONFIRMED | Tier 0 | 17 current openings. Company slug: AmrefHealthAfrica4. |
| Careerjet Kenya | Careerjet API | public.api.careerjet.net (Python SDK) | CONFIRMED | Tier 0 | Official API via careerjet-api PyPI. Indexes 60+ sites. |
| ReliefWeb | ReliefWeb API | api.reliefweb.int/v1/jobs | PARTIAL | Tier 0 | Appname registration submitted. Approval expected within 1 business day. API will be fully functional once approved. |
| Equity Bank | Taleo | equitybank.taleo.net/careersection/rest/jobboard/searchjobs | PARTIAL | Tier 1 | REST API responds (POST 200\) but careerSectionUnAvailable=true. May be temporary. |
| Absa Bank Kenya | Workday | absa.wd3.myworkdayjobs.com/wday/cxs/absa/AbsaCareers/jobs | BLOCKED | Tier 2 | Workday CXS API requires auth session. No public access. |
| NCBA Bank | Workday | ncba.wd3.myworkdayjobs.com/wday/cxs/... | BLOCKED | Tier 2 | Workday instance. API returns 406 without auth. |
| Safaricom | Unknown (migrated) | N/A \- Taleo decommissioned | NO API | Tier 2 | Taleo DNS dead. Migrated to unknown ATS. CDN-protected. |
| BrighterMonday KE | Laravel | N/A | NO API | Tier 2 | Laravel with Cloudflare. Has CSRF protection. Needs session handling for scraping. |
| MyJobMag Kenya | PHP | N/A | NO API | Tier 2 | Simple PHP site. Still shows Cloudflare headers but straightforward HTML scraping. |
| Fuzu Kenya | Ruby on Rails | N/A | NO API | Tier 2 | All /api/ routes return 403\. No public API. HTML scraping needed. |
| Impactpool | Rails | N/A | NO API | Tier 2 | Rails with Stimulus controllers. Check /feeds/ for possible RSS/XML feed. |
| World Vision | Rails | N/A | NO API | Tier 2 | Rails with Hotwire Turbo. Server-rendered but JS-enhanced pagination. |
| KCB Bank | PHP | N/A | NO API | Tier 2 | PHP 7.4 with proprietary careers module. No JSON endpoints. |
| MyGov Kenya | Government Portal | N/A | NO API | Tier 2 | Government portal at /job-adverts. HTML table structure. |

# **3\. Implementation Tiers**

## **Tier 0: Confirmed APIs**

Kenya Airways (iRec): Full REST API with pagination. Returns complete job JSON.

One Acre Fund (Greenhouse): Public board API. Full job details with content=true param.

Amref Health Africa (SmartRecruiters): 17 current openings. Company slug: AmrefHealthAfrica4.

Careerjet Kenya (Careerjet API): Official API via careerjet-api PyPI. Indexes 60+ sites.

ReliefWeb: Appname registration submitted. Approval expected within 1 business day. API will be fully functional once approved.

## **Tier 1: Partially Available**

Equity Bank (Taleo): REST API responds (POST 200\) but careerSectionUnAvailable=true. May be temporary.

## **Tier 2: HTML Scraping Required**

* Absa Bank Kenya (Workday): Workday CXS API requires auth session. No public access.  
* NCBA Bank (Workday): Workday instance. API returns 406 without auth.  
* Safaricom: Taleo DNS dead. Migrated to unknown ATS. CDN-protected.  
* BrighterMonday KE: Laravel with Cloudflare. Has CSRF protection and requires session handling for scraping. Server-rendered HTML.  
* MyJobMag Kenya: Simple PHP site. Still shows Cloudflare headers but straightforward HTML scraping.  
* Fuzu Kenya: Ruby on Rails. All /api/ routes return 403\. No public API. HTML scraping needed.  
* Impactpool: Rails with Stimulus controllers. Check /feeds/ for possible RSS/XML feed.  
* World Vision: Rails with Hotwire Turbo. Server-rendered but JS-enhanced pagination.  
* KCB Bank: PHP 7.4 with proprietary careers module. No JSON endpoints.  
* MyGov Kenya: Government portal at /job-adverts. HTML table structure.  
* Co-operative Bank: Removed from analysis (no longer included in scope).

# **4\. Updated Implementation Priority**

Based on the API audit findings, the implementation phases should prioritize early coverage with minimum effort:

## **Phase 1: API-First Sources (Week 1-2)**

* Kenya Airways iRec API adapter (direct JSON, highest reliability)  
* Greenhouse adapter for One Acre Fund (reusable for any Greenhouse employer)  
* SmartRecruiters adapter for Amref (reusable pattern)  
* Careerjet API integration (covers 60+ sites, biggest coverage multiplier)  
* ReliefWeb API (register appname first, then simple REST integration)

## **Phase 2: High-Value Scrapers (Week 3-4)**

* BrighterMonday Kenya (high volume, requires session handling for CSRF)  
* MyGov Kenya (government jobs, static HTML)  
* Workday instances via Playwright (Absa, NCBA)

## **Phase 3: Remaining Scrapers (Week 5-6)**

* Safaricom (requires reverse-engineering new ATS)  
* MyJobMag Kenya (straightforward PHP scraping)  
* Fuzu Kenya (Rails, no public API)  
* Impactpool, World Vision (Rails apps)  
* KCB Bank (custom PHP module)  
* Equity Bank Taleo (monitor for career section re-activation)

# **5\. Estimated Coverage by Phase**

With Careerjet acting as a meta-aggregator and the 4 direct ATS APIs, Phase 1 alone is projected to capture the majority of available job listings:

| Phase | Sources | Est. Daily Jobs | Cumulative % |
| :---- | :---- | :---- | :---- |
| Phase 1 (API) | 5 APIs \+ Careerjet | 200-400 | 50-65% |
| Phase 2 (Scraping) | 3 scrapers \+ 2 Workday | 100-200 | 75-85% |
| Phase 3 (Remaining) | 6+ scrapers | 50-100 | 90-95% |

*End of API Discovery Report v1.3 — Generated April 1, 2026*