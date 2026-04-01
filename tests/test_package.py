"""Smoke test: verify the package is importable."""


def test_package_imports() -> None:
    import ijobs_scraper

    assert ijobs_scraper.__doc__ is not None
