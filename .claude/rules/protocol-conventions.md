---
paths:
  - "src/ijobs_scraper/protocols.py"
description: Conventions for Protocol interface definitions
---

When working on protocols:

- Use `typing.Protocol` for structural subtyping — the host app should NOT need to inherit from these
- All methods must be `async def` (the package is async-first)
- Keep protocol methods minimal — only what the engine actually calls
- Type all parameters and return values explicitly (mypy --strict)
- Don't add default implementations — protocols are pure interfaces
- Don't import any host app types — protocols define the package boundary
- Document each method with a docstring explaining what the host app should implement
