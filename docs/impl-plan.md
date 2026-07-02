# Implementation Plan — youtrack-cli v0.1

This plan tracks the current pre-release CLI implementation. The scope is intentionally
narrow: health check, issue listing/detail, basic create/edit/comment/link, auth login,
config resolution, and zipapp packaging.

## Goals & non-goals

**Goals**

- Provide a small, scriptable YouTrack CLI using permanent-token authentication.
- Keep output predictable: Rich tables by default and JSON envelopes with `--output json` or
  `--json`.
- Use explicit YouTrack `fields=` projections and stable exit-code classification.
- Support a practical subset of issue create/edit/search workflows without promising full
  YouTrack UI parity.

**Non-goals for v0.1**

- Admin/setup commands, agile boards, reports, dashboards, time tracking, OAuth, or a TUI.
- Batch mutation commands.
- Comment visibility or notification controls.
- Custom issue-list columns.

## Decisions

**Language: Python 3.10+.** Typer handles the CLI, httpx handles synchronous HTTP, and Rich
handles human-readable table/detail output. Packaging is through `pyproject.toml`; the
standalone build uses `shiv` to create a dependency-vendored zipapp.

**Auth scope.** v0.1 uses permanent YouTrack tokens. The CLI reads schema endpoints needed
for project custom fields through the authenticated user's permissions.

**Field input grammar.** Generic field input is `--field Name=value`; parsing splits on the
first `=`. The implementation supports the bundle-backed field types used by the current
create/edit paths and rejects unsupported create-time period fields with guidance.

**Edit mechanism.** Summary/description use direct issue updates. Other structured edit
flags and raw `--command` are sent through YouTrack command language; period fields use the
direct typed update path.

## Architecture

```text
youtrack_cli/
  __main__.py       entrypoint and console-script target
  cli/              Typer command definitions and output/error orchestration
  config.py         flag/env/.env/config-file resolution; auth config writer
  client.py         httpx boundary, auth headers, fields= handling, error decoding
  errors.py         ExitCode, APIError, ConfigError, validation/workflow classes
  fields.py         project custom-field schema parsing and typed value builders
  query.py          YouTrack query composer for implemented issue filters
  issues.py         issue create/edit/search/comment/link orchestration
  render.py         Rich table/detail renderers

tests/              pytest suite
docs/               project documentation
scripts/            local YouTrack helpers and provisioning scripts
```

Key invariants:

- `client.py` is the only HTTP boundary.
- `config.py` and `errors.py` stay small and import-light.
- CLI globals are parsed before subcommands (`yt --output json issues`).
- Mutating requests are not retried automatically.

## Delivery milestones

### M0 — Foundation — done

- Config resolution foundation and error contracts.
- HTTP client wrapper with explicit `fields=`, bearer auth, timeouts, error decoding, and
  GET-only transient retry.
- `yt status` health check through `/api/users/me`.
- Global options: `--output`/`--json`, `--base-url`, `--token`, `--no-color`, `--quiet`.

### M1 — Search and show — done, trimmed to implemented flags

Implemented:

```text
yt issues [--all] [--project <p>] [--state <s>] [--assignee <login>]
          [--query <q>] [--sort <s>] [--limit <n>] [--offset <n>]
yt show <id>
```

Behavior:

- Default `yt issues` query is `for: me #Unresolved`; `--all` disables that default.
- `--limit` maps to `$top`; `--offset` maps to `$skip`.
- Default table columns are `ID STATE PRIORITY TYPE SUMMARY`.
- `yt show` renders issue detail and a fixed set of custom fields.

Not in M1/v0.1: query text outside the `--query` flag, custom list columns, extra
pagination warnings, or comments/links in `show`.

### M2 — Create — done, trimmed to implemented behavior

Implemented:

```text
yt create <project> <summary> [--description|-d <text>]
           [--type <T>] [--priority <P>] [--state <S>] [--assignee <login>]
           [--field <Name>=<value>]... [--dry-run]
```

Behavior:

- Resolves project and custom-field schema.
- Builds typed YouTrack issue custom-field payloads.
- Rejects create-time period fields because this YouTrack build drops period minutes on
  issue creation.
- `--dry-run` prints the body that would be sent.
- Assignee eligibility is left to server validation; `Value is not allowed` with an
  assignee gets a contextual hint. The CLI does not retry by creating the issue unassigned.

Not in M2/v0.1: batch creation or auto-retry with altered field values after a server
rejection.

### M3 — Edit, comment, link — done, trimmed to implemented features

Implemented:

```text
yt edit <issue> [--summary <s>] [--description|-d <d>]
        [--type <T>] [--priority <P>] [--state <S>] [--assignee <login>]
        [--field <Name>=<value>]... [--command|-c <youtrack command>]
yt comment <issue> <text>
yt link <issue> <type> <target>
```

Behavior:

- `yt edit` targets one issue.
- Summary/description use direct issue update.
- Structured field flags and `--command` use YouTrack command language when applicable.
- Period fields use a direct typed issue update.
- `yt comment` posts a plain comment.
- `yt link` creates links through command language.

Not in M3/v0.1: batch edits, field clearing/delta helpers, comments through `yt edit`,
comment visibility, notification controls, or diff-style output.

### M4 — Config/auth hardening — done

Implemented:

- Config file at `~/.config/youtrack-cli/config.toml`.
- Global `--config` path override.
- `yt auth login` prompting for base URL and token with hidden token input.
- Config file writes with mode `0600` and parent directory `0700` when applicable.
- Resolver security rule preventing `.env`/config-file mixing when one of them supplies the
  token.
- `--version`.

Not included in M4/v0.1: shell completions beyond Typer defaults, custom column presets, or
OS keyring storage.

### Packaging — done

- `pipx install`/editable install from `pyproject.toml`.
- `make standalone` builds `dist/yt.pyz`, a shiv zipapp with runtime dependencies vendored.

## Testing strategy

- **Offline tests:** run with `pytest`. These cover unit/contract behavior using mocks where
  HTTP is involved.
- **Live tests:** opt-in via `pytest -m live` (or `make test-live`). They require a running
  local YouTrack instance and appropriate tokens/configuration.
- **CI:** GitHub Actions is the intended CI runner for offline checks. Live tests should not
  be described or configured as running on every push; if used in CI, they should be manual,
  scheduled, or otherwise opt-in because they require a live YouTrack service.
- **Static checks:** `ruff check`, `ruff format --check`, and `mypy` remain part of the local
  pre-push gate.

## Resolved decisions

1. Language — Python 3.10+.
2. HTTP mock library — `pytest-httpx`.
3. Default `yt issues` — current user's unresolved issues; `--all` for unfiltered listing.
4. Distribution — Python package primary; zipapp via `shiv` for one-file deployment.
5. Token storage — plaintext TOML config with mode `0600`; keyring is not v0.1.

See `docs/contracts.md` for the behavior-level contract and `docs/cuj-map.md` for the user
journey map.
