---
name: youtrack-cli
description: Use when asked to create, search, edit, comment, link, or configure issues in JetBrains YouTrack via the command-line tool yt (jetbrains-youtrack-cli).
compatibility: Requires a Python 3.10+ environment with the jetbrains-youtrack-cli package (pipx install), or the standalone dist/yt.pyz. Needs a YouTrack base URL and a permanent API token.
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

## Search and show issues

Default `yt issues` shows the current user's unresolved issues (`for: me #Unresolved`). Use `--all` to remove that default.

```bash
yt issues --all --limit 50
yt issues --project JT --state Open
yt issues --assignee alice --sort "Priority desc"
yt issues --query "project: JT #Unresolved state: Open" --limit 20 --offset 20
yt show JT-1
```

For scripting, use `--output json` or `--json`:

```bash
yt --output json issues --project JT --limit 100
```

## Create an issue

```bash
yt create DEMO "Fix the widget" --description "It is broken." \
  --type Bug --priority Major --state Submitted --assignee alice
```

Use repeatable `--field` for custom fields. Split on the first `=` only:

```bash
yt create DEMO "Add feature" --type Task --field "Subsystems=Core" --field "Target version=2026.1"
```

Multi-value fields use comma-separated values:

```bash
yt create DEMO "Cross-platform fix" --field "Subsystems=Core,UI"
```

Use `--dry-run` to preview the request body without sending it:

```bash
yt create DEMO "Test" --type Task --dry-run
```

## Edit an issue

```bash
yt edit JT-1 --state Done --summary "Fixed the widget"
yt edit JT-1 --description "Updated description"
yt edit JT-1 --assignee bob
yt edit JT-1 --field "Priority=Critical" --field "Subsystems=Core,UI"
```

For operations the CLI does not expose as a flag, use raw YouTrack command language:

```bash
yt edit JT-1 --command "Subsystem UI"
```

## Comment and link

```bash
yt comment JT-1 "Verified on staging"
yt link JT-1 relates_to JT-2
```

Common link types: `relates_to`, `duplicates`, `depends_on`.

## Output and exit codes

- Default: Rich table for `issues`, formatted text for `show`.
- `--output json` / `--json` returns a stable envelope: `{ "ok": true, "data": ... }` or `{ "ok": false, "error": { ... } }`.
- Exit codes: `OK=0`, `API=1`, `USAGE=2`, `VALIDATION=3`, `NOT_FOUND=4`, `PERMISSION=5`, `WORKFLOW=6`.

## Gotchas

- **Global options go before the subcommand.** `yt issues --output json` is wrong; use `yt --output json issues`.
- **No mixing of `.env` and config file for tokens.** If the token comes from `.env`, the config-file base URL is ignored, and vice versa. Flags and env vars are always composable per-key.
- **1Password is the last source.** If `YOUTRACK_TOKEN` or a config token exists, `--op-*` will not be used.
- **Empty `--token` does not fall through.** An explicit empty string is still considered set and will fail with a config error.
- **Multi-value fields are comma-separated.** `Assignees=alice,bob` or `Subsystems=Core,UI`.
- **Server-side validation applies.** Assignee validation is done by YouTrack; the CLI surfaces the error with a contextual hint.
- **Workflow guards.** Some edits may be rejected by YouTrack workflows with exit code `WORKFLOW` (6). Inspect the error field and rule name.

## Validation

Before declaring a command ready, check:

- Global options are placed before the subcommand.
- The correct `--base-url` or `YOUTRACK_BASE_URL` is set for non-local instances.
- A token is available (run `yt status` to verify).
- Field names in `--field` match the project schema exactly.
- For scripts, `--output json` is used and exit code is checked.

## References

- For full project setup and local dev server, see `docs/local-youtrack.md`.
- For detailed command contracts, exit codes, and resolver behavior, see `docs/contracts.md`.
- For user journeys and examples, see `docs/cuj-map.md`.
- For CLI help, run `yt --help` or `yt <command> --help`.

## Troubleshooting

- **`yt status` fails with 401/403.** Check that `YOUTRACK_TOKEN` or `--token` is set to a valid permanent token. Verify the token is for the intended `--base-url`.
- **`yt issues` returns nothing.** The default query is `for: me #Unresolved`; use `--all` to see every issue, or add `--project` / `--query` filters.
- **`--assignee` is rejected.** YouTrack validates assignees server-side. Pass the login name (e.g. `alice`), not the full display name.
- **`--field` value is rejected.** Custom field names must match the project schema exactly. Use `--dry-run` to inspect the typed body being sent.
- **Wrong server.** If you have both a `.env` and a config file, remember that the token source determines which base URL is used; `.env` and config-file tokens are not mixed.
- **No color.** Use `--no-color` or set `NO_COLOR` in the environment; JSON mode disables color automatically.
