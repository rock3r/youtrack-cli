---
name: youtrack-cli
description: |
  Use when asked to create, search, edit, comment, link, or configure issues in JetBrains YouTrack via the yt command-line tool (package jetbrains-youtrack-cli, YouTrack REST API, issue tracker CLI). Handles global option placement, token precedence, JSON output, and exit code WORKFLOW errors.
compatibility: Python 3.10+ with jetbrains-youtrack-cli (pipx) or dist/yt.pyz. Requires network access to the YouTrack base URL, a permanent API token, and optionally the 1Password CLI (op) for token sourcing.
license: UEL-1.0
metadata:
  package: jetbrains-youtrack-cli
  binary: yt
---

# YouTrack CLI (`yt`)

Guidance for using `jetbrains-youtrack-cli` (`yt`) against the YouTrack REST API.

## When to use

Use this skill when the user asks to:

- Search or list issues in a YouTrack project.
- Show issue details.
- Create, edit, comment on, or link issues.
- Authenticate or configure `yt`.
- Understand error messages or output formats from `yt`.

Do not use this skill for YouTrack admin tasks not covered by the CLI (boards, reports, time tracking, OAuth, user administration).

## Install

Preferred:

```bash
pipx install jetbrains-youtrack-cli
```

Or use the standalone zipapp from the GitHub release:

```bash
python3 dist/yt.pyz --version
```

## Authenticate

`yt` needs a base URL and a permanent API token. Resolution order is strict:

1. `--base-url` / `--token` flags
2. `YOUTRACK_BASE_URL` / `YOUTRACK_TOKEN` environment variables
3. `.env` in the current working directory
4. `~/.config/youtrack-cli/config.toml` (written by `yt auth login`)
5. 1Password CLI (`--op-vault`, `--op-item`, `--op-field`, or `YOUTRACK_OP_*` env vars) — **last** token source
6. Default base URL: `http://localhost:8080`

Persist credentials interactively:

```bash
yt auth login
```

This writes `~/.config/youtrack-cli/config.toml` with mode `0600` and tightens the parent directory to `0700`.

Use 1Password as the token source only when no earlier source has a token:

```bash
yt --op-vault Private --op-item "YouTrack token" --op-field "api token" status
```

### Global options placement

Global options (`--output`, `--base-url`, `--token`, `--config`, `--op-*`, `--no-color`, `--quiet`, `--version`) must appear **before** the subcommand:

```bash
yt --output json issues
yt --base-url https://youtrack.example.com --token $TOKEN issues
```

## Common commands

Quick examples; for the full matrix see `references/commands.md`.

Search:

```bash
yt issues --all --limit 50
yt issues --project JT --state Open
yt show JT-1
```

Create:

```bash
yt create DEMO "Fix the widget" --type Bug --priority Major --assignee alice
```

Edit:

```bash
yt edit JT-1 --state Done --summary "Fixed the widget"
yt edit JT-1 --command "Subsystem UI"
```

Comment and link:

```bash
yt comment JT-1 "Verified on staging"
yt link JT-1 relates_to JT-2
```

## Field syntax

Repeatable `--field` accepts `Name=value` and splits on the first `=` only. Multi-value fields are comma-separated:

```bash
yt create DEMO "Cross-platform fix" --field "Subsystems=Core,UI"
```

Use `--dry-run` to preview the request body before sending:

```bash
yt create DEMO "Test" --type Task --dry-run
```

## Output and exit codes

- Default: Rich table for `issues`, formatted text for `show`.
- `--output json` / `--json` returns a stable envelope: `{ "ok": true, "data": ... }` or `{ "ok": false, "error": { ... } }`.
- Exit codes: `OK=0`, `API=1`, `USAGE=2`, `VALIDATION=3`, `NOT_FOUND=4`, `PERMISSION=5`, `WORKFLOW=6`.

## Gotchas

- **Global options go before the subcommand.** `yt issues --output json` is wrong; use `yt --output json issues`.
- **No mixing of `.env` and config file for tokens.** If the token comes from `.env`, the config-file base URL is ignored, and vice versa. Flags and env vars are always composable per-key.
- **1Password is the last source.** If `YOUTRACK_TOKEN` or a config token exists, `--op-*` will not be used.
- **Empty `--token` does not fall through.** An explicit empty string is still considered set and will fail with a config error.
- **Multi-value fields are comma-separated.** `Subsystems=Core,UI`.
- **Assignee is a single login.** Pass `--assignee alice`, not a comma-separated list. YouTrack validates it server-side.
- **Server-side validation applies.** Field and assignee validation is done by YouTrack; the CLI surfaces the error with a contextual hint.
- **Workflow guards.** Some edits may be rejected by YouTrack workflows with exit code `WORKFLOW` (6). Inspect the error field and rule name.

## Validation

Before declaring a command ready, check:

- Global options are placed before the subcommand.
- The correct `--base-url` or `YOUTRACK_BASE_URL` is set for non-local instances.
- A token is available (run `yt status` to verify).
- Field names in `--field` match the project schema exactly.
- For scripts, `--output json` is used and exit code is checked.

## References

- For the full command matrix, read `references/commands.md` (bundled in this skill).
- For CLI help, run `yt --help` or `yt <command> --help`.

If you are working inside the `jetbrains-youtrack-cli` repository, also see `docs/contracts.md`, `docs/cuj-map.md`, and `docs/local-youtrack.md` for developer-level detail.
