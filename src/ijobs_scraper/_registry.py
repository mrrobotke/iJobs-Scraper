"""Adapter registry for mapping names to adapter classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ijobs_scraper.exceptions import AdapterError

if TYPE_CHECKING:
    from collections.abc import Callable

    from ijobs_scraper.adapters.base import BaseAdapter


class AdapterRegistry:
    """Maps adapter names to their implementation classes.

    Adapters register themselves using the ``@AdapterRegistry.register("name")``
    decorator. The engine uses ``get()`` to instantiate adapters by name and
    ``detect_from_url()`` for automatic URL-based adapter selection.
    """

    _adapters: dict[str, type[BaseAdapter]] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[type[BaseAdapter]], type[BaseAdapter]]:
        """Decorator that registers an adapter class under the given name."""

        def decorator(adapter_cls: type[BaseAdapter]) -> type[BaseAdapter]:
            cls._adapters[name] = adapter_cls
            return adapter_cls

        return decorator

    @classmethod
    def get(cls, name: str) -> type[BaseAdapter]:
        """Return the adapter class registered under *name*.

        Raises:
            AdapterError: If no adapter is registered with that name.
        """
        if name not in cls._adapters:
            available = ", ".join(sorted(cls._adapters)) or "(none)"
            raise AdapterError(
                name, f"No adapter registered as '{name}'. Available: {available}", retryable=False
            )
        return cls._adapters[name]

    @classmethod
    def detect_from_url(cls, url: str) -> type[BaseAdapter] | None:
        """Return the first adapter whose ``can_handle_url`` matches *url*."""
        for adapter_cls in cls._adapters.values():
            instance = adapter_cls()
            if instance.can_handle_url(url):
                return adapter_cls
        return None

    @classmethod
    def list_adapters(cls) -> dict[str, type[BaseAdapter]]:
        """Return a copy of all registered adapters."""
        return dict(cls._adapters)

    @classmethod
    def _clear(cls) -> None:
        """Clear registry. Used in tests only."""
        cls._adapters.clear()
