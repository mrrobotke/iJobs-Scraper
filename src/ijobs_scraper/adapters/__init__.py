"""Adapter modules for job portal sources.

Importing this package auto-registers all built-in adapters with
the :class:`~ijobs_scraper.AdapterRegistry`.
"""

import importlib
import logging

_logger = logging.getLogger(__name__)


def _import_subpackage(name: str) -> None:
    """Import adapter sub-package, skipping gracefully if optional deps missing."""
    try:
        importlib.import_module(f"ijobs_scraper.adapters.{name}")
    except ImportError:
        _logger.debug("Skipping adapter sub-package %s (optional dependency missing)", name)


# API and HTML adapters use core deps — always available
_import_subpackage("api")
_import_subpackage("html")

# Browser adapters require playwright (optional extra)
_import_subpackage("browser")
