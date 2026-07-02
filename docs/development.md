# Development guide

Thanks for hacking on `youtrack-cli`! This is a Python 3.10+ CLI for the JetBrains
YouTrack REST API.

> **License:** source-available under the [Unenshittifiable License (UEL) v1.0]
> (https://uelicense.eu). By contributing you agree your changes are also UEL-licensed
> (see `LICENSE` §06 and `CONTRIBUTING.md`).

## Quick start

```bash
git clone <repo> && cd youtrack-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # installs yt + dev tools

# Optional: bring up the local YouTrack instance and seed data
./scripts/setup.sh             # see docs/local-youtrack.md
cp .env.example .env           # holds YOUTRACK_BASE_URL + YOUTRACK_TOKEN
```

Sanity check:

```bash
yt --help
yt status                      # requires a configured/running YouTrack instance
pytest                         # offline tests
pytest -m live                 # opt-in live tests, if a local instance is running
# or: make test-live
```

You can develop without a local YouTrack instance for normal unit/contract work. Live tests
are opt-in and require a running instance plus suitable credentials.

## Day-to-day commands

```bash
pytest                         # offline tests
pytest tests/test_errors.py    # one file
pytest -k exit_code            # by name
ruff check .                   # lint
ruff format .                  # format
mypy                           # type-check
ruff check . && ruff format --check . && mypy && pytest   # local pre-push gate
```

## Static analysis

- **ruff** — linter + formatter. Config lives in `pyproject.toml` under `[tool.ruff]`.
  Use `ruff check --fix .` and `ruff format .` when making code changes.
- **mypy** — strict type checking (`[tool.mypy]`, `strict = true`). The `[dev]` extra
  installs it.

GitHub Actions is the intended CI runner for offline checks. Do not assume live YouTrack
tests run on every push; run them explicitly with `pytest -m live`/`make test-live` when you
have a local instance available.

## How we work: TDD

We write tests against the contracts in `docs/contracts.md`.

1. Pick a behavior contract.
2. Write or update a failing test in `tests/`.
3. Implement the minimum change in `youtrack_cli/`.
4. Refactor under green; run ruff, mypy, and pytest.

Golden/contract tests pin request shapes (method, URL, body, `fields=`) and stable JSON/table
output where applicable.

### Test layers

| Layer | When | How |
|---|---|---|
| Unit | Pure functions and small helpers | plain pytest, no live HTTP |
| Contract | Request/response behavior | mocked HTTP, offline |
| Live | Real behavior against YouTrack | `pytest -m live` / `make test-live`, opt-in |

Live tests should be run against a running local YouTrack instance seeded/configured for the
case under test. They are not required for every local edit.

## Project layout

```text
youtrack_cli/        the package
  errors.py          ExitCode, APIError, ConfigError
  config.py          Config resolution and config-file writing
  client.py          httpx wrapper and HTTP error boundary
  query.py           YouTrack query-string composer
  fields.py          field schema and typed value helpers
  issues.py          create/edit/search/comment/link domain logic
  render.py          Rich tables and detail output
  cli/               Typer commands
tests/               pytest suite
docs/                project documentation
scripts/             local-instance and provisioning tooling
```

## Local YouTrack instance

The local instance setup is documented in **`docs/local-youtrack.md`**. Short version:
`./scripts/setup.sh` installs/seeds it, and `./scripts/youtrack.sh {start,stop,status,logs}`
manages it.

## Building a standalone executable

```bash
make standalone       # → dist/yt.pyz (zipapp with deps vendored via shiv)
./dist/yt.pyz --help  # runs on Python 3.10+
```

`pipx install youtrack-cli` is the primary install path. The `.pyz` vendors runtime
dependencies; it is "one file + Python", not "stdlib-only".
