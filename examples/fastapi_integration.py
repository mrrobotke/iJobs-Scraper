"""FastAPI integration example — manual URL parser + background scraping.

This example shows how a FastAPI application would integrate ijobs-scraper.
It is illustrative and NOT meant to be run directly (FastAPI is not a
dependency of this package).

Requires: pip install fastapi uvicorn ijobs-scraper
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# 1. AI Provider — bridges to OpenAI via httpx
# ---------------------------------------------------------------------------


class OpenAIProvider:
    """Implements ijobs_scraper.AIProvider using the OpenAI chat completions API."""

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini") -> None:
        self.api_key = api_key
        self.model = model

    async def structured_extract(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Call OpenAI with JSON schema enforcement and return parsed result."""
        import httpx  # noqa: F811 — runtime import (not a package dep)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_schema", "json_schema": json_schema},
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()

        content: str = resp.json()["choices"][0]["message"]["content"]
        result: dict[str, Any] = json.loads(content)
        return result


# ---------------------------------------------------------------------------
# 2. FastAPI application wiring (illustrative)
# ---------------------------------------------------------------------------

# from fastapi import FastAPI, BackgroundTasks, HTTPException
# from pydantic import BaseModel
#
# app = FastAPI(title="iJobs Scraper API")
#
# OPENAI_API_KEY = "sk-..."  # Load from environment in production
#
# engine = ScraperEngine(ai_provider=OpenAIProvider(OPENAI_API_KEY))
#
#
# class ParseURLRequest(BaseModel):
#     url: str
#     hint: str | None = None
#
#
# @app.post("/scraper/parse-url")
# async def parse_url(request: ParseURLRequest) -> EnrichedJob:
#     """Parse a single job URL and return enriched data."""
#     try:
#         return await engine.parse_url(request.url, hint=request.hint)
#     except Exception as exc:
#         raise HTTPException(status_code=400, detail=str(exc))
#
#
# @app.post("/admin/scraper/sources/{source_slug}/trigger")
# async def trigger_scrape(
#     source_slug: str,
#     background_tasks: BackgroundTasks,
# ) -> dict[str, str]:
#     """Manually trigger a background scrape for a source."""
#     source = SourceConfig(
#         name="One Acre Fund",
#         slug=source_slug,
#         adapter="greenhouse",
#         source_type=SourceType.API,
#         base_url="https://boards-api.greenhouse.io",
#         config={"board_token": "oneacrefund"},
#     )
#
#     async def _run_scrape() -> None:
#         result = await engine.scrape_source(source)
#         print(f"Scrape complete: {result.jobs_created} jobs created")
#
#     background_tasks.add_task(_run_scrape)
#     return {"status": "scrape_enqueued", "source": source_slug}
