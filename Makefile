.PHONY: install lint format test test-live build

install:
	uv sync --all-extras

lint:
	ruff check src/ tests/ && ruff format --check src/ tests/ && mypy --strict src/

format:
	ruff check --fix src/ tests/ && ruff format src/ tests/

test:
	pytest tests/ -v --cov=ijobs_scraper --cov-report=term-missing

test-live:
	pytest tests/ -v -m live

build:
	python -m build
