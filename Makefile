# youtrack-cli — common dev tasks. Usage: `make <target>`.

PY := python3
PIP := $(PY) -m pip

.PHONY: help install dev lint format format-check typecheck test test-live check standalone clean

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n",$$1,$$$2}'

dev:            ## Create venv and install dev deps (editable)
	$(PY) -m venv .venv
	. .venv/bin/activate && $(PIP) install -U pip && $(PIP) install -e ".[dev]"

lint:           ## Lint with ruff
	ruff check youtrack_cli tests

format:         ## Format with ruff (mutating)
	ruff format youtrack_cli tests

format-check:   ## Check formatting without mutating files
	ruff format --check youtrack_cli tests

typecheck:      ## Type-check with mypy
	mypy

test:           ## Run offline tests (unit + contract)
	pytest

test-live:      ## Run live integration tests against the local YouTrack instance
	pytest -m live

check: lint format-check typecheck test  ## Full pre-push gate (offline; non-mutating)

standalone:     ## Build dist/yt.pyz (zipapp with deps vendored, via shiv)
	@mkdir -p dist
	$(PIP) install -q shiv
	shiv -c yt -o dist/yt.pyz .

clean:          ## Remove build artifacts and caches
	rm -rf build dist *.egg-info .mypy_cache .ruff_cache .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
