---
name: verify
description: Run the full quality gate — ruff check, ruff format check, mypy strict, and pytest. Use before marking any phase or task complete.
---

Run the full quality gate for the ijobs-scraper package. Execute these commands in order, stopping on first failure:

1. `ruff check src/ tests/`
2. `ruff format --check src/ tests/`
3. `mypy --strict src/`
4. `pytest`

Report results clearly: pass/fail for each step. If any step fails, show the errors and suggest specific fixes. Do not proceed to the next step if the current one fails.
