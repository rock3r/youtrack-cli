# Contracts — implemented v0.1 CLI behavior

These contracts describe the behavior implemented by the current CLI. They are the stable
reference for tests and docs.

Source-available under the **UEL v1.0** — see `LICENSE`.

## ExitCode (`youtrack_cli/errors.py`)

The CLI process exit code equals the domain error's code.

| name | value | meaning |
|---|---:|---|
| `OK` | 0 | success |
| `USAGE` | 2 | argument/usage/configuration error |
| `VALIDATION` | 3 | client-side validation, such as bad value or unknown field |
| `NOT_FOUND` | 4 | 404 — may mean no match or no access |
| `PERMISSION` | 5 | 401/403 authentication or permission failure |
| `WORKFLOW` | 6 | YouTrack workflow guard |
| `API` | 1 | other HTTP/server/transport/unexpected failure |

404 vs 403 rule: schema reads on a project the user cannot access may return 404, while a
missing action right generally returns 403. A 404 should be phrased as "not found or no
access" rather than a confident non-existence claim.

## APIError (`youtrack_cli/errors.py`)

`APIError` is the exception domain code raises for HTTP/API failures. It is built from the
decoded JSON error body when possible and preserves:

- HTTP status
- server error code/description
- workflow rule metadata (`error_rule_name`, `error_field`, `error_type`,
  `error_workflow_type`)
- request method/path
- raw decoded body

Exit-code classification:

- 401/403 → `PERMISSION`
- 404 → `NOT_FOUND`
- workflow-shaped 400 → `WORKFLOW`
- other 400 → `VALIDATION`
- everything else → `API`

## JSON output contract (`--output json` / `--json`)

Success and errors share one envelope:

```jsonc
// success, process exits 0
{ "ok": true, "data": { /* command result */ } }

// error, process exits non-zero
{ "ok": false, "error": {
  "code": "PERMISSION",
  "exit_code": 5,
  "status": 403,
  "message": "No permission to create issue in project YouTrack",
  "rule_name": null,
  "field": null,
  "type": null,
  "workflow_type": null,
  "request": { "method": "POST", "path": "/api/issues" }
}}
```

Text mode prints human messages. JSON mode emits stable structured output suitable for
scripts.

## Config resolver (`youtrack_cli/config.py`)

```python
@dataclass(frozen=True)
class Config:
    base_url: str        # normalized, no trailing slash
    token: str
    me: str | None       # None until a command fills it from /api/users/me
```

Default config file: `~/.config/youtrack-cli/config.toml`.

`yt auth login` is implemented. It prompts for base URL and token, hides token input, and
writes the TOML config file with mode `0600` (creating/tightening the parent directory to
`0700` when applicable). The global `--config` option selects an alternate config file path.

Resolver precedence is:

1. Explicit flag value (`--base-url`, `--token`). An empty string is still considered set.
2. Environment (`YOUTRACK_BASE_URL`, `YOUTRACK_TOKEN`).
3. Current working directory `.env` only. No recursive or parent-directory discovery.
4. Config file (`~/.config/youtrack-cli/config.toml` by default, or `--config`).
5. 1Password CLI (`--op-vault`, `--op-item`, `--op-field` or `YOUTRACK_OP_VAULT`,
   `YOUTRACK_OP_ITEM`, `YOUTRACK_OP_FIELD`). The token is fetched once per command and
   cached for the process lifetime. Default field is `password`.
6. Base URL default `http://localhost:8080`.

`.env` parsing supports `KEY=VALUE`, ignores blank lines and `#` comments, and performs no
shell expansion.

Security/no-mixing rule: flags and environment values may be combined per key with lower
sources, but `.env` and the config file are not mixed when the token comes from one of those
sources. If the token comes from `.env`, config-file base URL is ignored; if the token comes
from the config file, `.env` base URL is ignored.

A missing or empty resolved token raises `ConfigError` (exit `USAGE`) with a message that
starts with `youtrack-cli: not configured` and mentions both `YOUTRACK_TOKEN` and `--token`.
Base URLs are stripped of trailing `/`; URLs without a scheme get `https://` prepended,
except the local default remains `http://localhost:8080`.

## HTTP client (`youtrack_cli/client.py`)

- Sync `httpx.Client` wrapper.
- Every request includes bearer auth and JSON accept/content headers as appropriate.
- Callers pass explicit YouTrack `fields=` projections; the client does not invent them.
- Non-2xx responses are decoded into `APIError`.
- Mutating requests are not retried automatically.
- Idempotent GET retries transient transport/5xx failures once, with a fixed 0.5s backoff.
- Network errors map to `APIError(status=0, code="connect_error", retryable=True)`.

## CLI parsing and global options

Implemented global options:

- `--output {table,json}` / `-o`
- `--json`
- `--base-url`
- `--token`
- `--config`
- `--op-vault`
- `--op-item`
- `--op-field`
- `--no-color`
- `--quiet`
- `--version`

Global options must appear before the subcommand, for example:

```bash
yt --output json issues
```

Typer/Click usage errors exit with `USAGE` (`2`). Repeated `--field` options preserve order,
and `Name=value` field flags split on the first `=`.

## Render contract (Rich)

Default `yt issues` columns are fixed:

```text
ID  STATE  PRIORITY  TYPE  SUMMARY
```

There is no implemented custom-column contract.

Rendering rules:

- Null/missing values render as `-` in tables.
- Multi-values are joined with `, `.
- User fields prefer login/name depending on data returned by YouTrack.
- `SUMMARY` is truncated with an ellipsis to fit terminal width.
- Color is disabled when `--no-color` is used or in JSON mode.

The CLI does not request an extra row for limit detection; `--limit` and `--offset` map
directly to YouTrack `$top` and `$skip`.

## Command contracts by surface

- `yt status`: `GET /api/users/me?fields=login,fullName`.
- `yt issues`: supports `--all`, `--project`, `--state`, `--assignee`, `--query`, `--sort`,
  `--limit`, and `--offset`.
- `yt show <id>`: renders summary, description, project, created/updated, reporter/assignee,
  and a fixed set of custom fields. Comments and links are not fetched.
- `yt create <project> <summary>`: supports `--description`, `--type`, `--priority`,
  `--state`, `--assignee`, repeatable `--field`, and `--dry-run`.
- `yt edit <issue>`: supports `--summary`, `--description`, `--type`, `--priority`,
  `--state`, `--assignee`, repeatable `--field`, and `--command`.
- `yt comment <issue> <text>`: adds a plain comment without visibility controls.
- `yt link <issue> <type> <target>`: creates a link through the command language.
- `yt auth login`: writes credentials to the config file.

## Import rules

- `errors.py` — stdlib only; imports nothing from this package.
- `config.py` — stdlib + `errors` only; accepts an optional `op_token` callback but does
  not know about 1Password.
- `client.py` — imports `config` (value objects) and `errors`.
- `query.py`, `fields.py` — stdlib + `errors` only.
- `onepassword.py` — stdlib + `errors` only; isolated from CLI/HTTP details.
- `issues.py` — imports `client`, `fields`, `query`, `errors`.
- `render.py` — imports `rich`, `errors`, and `fields` (pure helpers).
- `cli/` — the only place `typer` lives; orchestrates the above.

## Distribution / portability contract

- Primary install: Python package from `pyproject.toml` with runtime dependencies (`typer`,
  `httpx`, `rich`, and `tomli` on Python <3.11).
- Standalone build: `make standalone` builds `dist/yt.pyz` via `shiv`, with runtime
  dependencies vendored. The portability claim is "one file + Python 3.10+", not
  "stdlib-only".

## Resolved decisions

- Language/runtime: Python 3.10+.
- HTTP mock library: `pytest-httpx`.
- Default `yt issues`: current user's unresolved issues (`for: me #Unresolved`); `--all`
  removes that default.
- Token storage: plaintext TOML config file with mode `0600`; OS keyring is not part of
  v0.1.
