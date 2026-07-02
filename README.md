# youtrack-cli

A CLI for the [JetBrains YouTrack REST API](https://www.jetbrains.com/help/youtrack/devportal/youtrack-rest-api.html),
developed and tested against a local YouTrack instance.

## Quick start (users)

```bash
# Install from PyPI
pipx install jetbrains-youtrack-cli

# Or from GitHub directly
# pipx install git+https://github.com/rock3r/youtrack-cli

# Configure your YouTrack instance and save the token
yt auth login

# Verify
yt --version
yt status

# Search issues
yt issues --all --limit 20
yt show JT-1

# Create / edit / comment / link
yt create DEMO "Fix the widget" --type Bug --priority Major
yt edit JT-1 --state Done --summary "Fixed"
yt comment JT-1 "Verified on staging"
yt link JT-1 relates_to JT-2
```

> Global options (`--output`, `--base-url`, `--token`, `--config`, `--op-vault`,
> `--op-item`, `--op-field`, `--no-color`, `--quiet`, `--version`) must appear **before**
> the subcommand because Typer places them on the root app. Example:
> `yt --output json issues`, not `yt issues --output json`.

Run `yt --help` or `yt <command> --help` for options. Use `--output json` for scripting.

**Install:** `pipx install jetbrains-youtrack-cli`, or use `make standalone` for a local `dist/yt.pyz`.

## Authentication

`yt` needs a YouTrack base URL and a permanent API token. It looks them up in this
order:

1. Command-line flags: `--base-url` and `--token`.
2. Environment variables: `YOUTRACK_BASE_URL` and `YOUTRACK_TOKEN`.
3. A `.env` file in the current working directory.
4. The config file at `~/.config/youtrack-cli/config.toml` (written by `yt auth login`).
5. 1Password CLI (`op`): `--op-vault`, `--op-item`, and `--op-field` (or the equivalent
   `YOUTRACK_OP_*` environment variables).
6. Default base URL: `http://localhost:8080`.

If you use 1Password, the token is fetched from `op` once per command and cached for the
process lifetime. The default field is `password`; use `--op-field` to read a different
field. Example:

```bash
yt --op-vault Private --op-item "YouTrack token" --op-field "api token" status
```

Run `yt auth login` to save a token to the config file so you don't need `--token` or
`--op-*` on every invocation.

> Note: the `.env` and config-file sources are never mixed when the token comes from
> different places, so a project directory `.env` can't accidentally redirect a stored
> config token to a different server.

# Quick start (local dev environment)

Everything you need — a local YouTrack server in Apple Container, configured and
seeded with realistic JetBrains-style data — in one command:

```bash
./scripts/setup.sh
```

This installs Apple Container, runs YouTrack 2026.2, completes the first-run
wizard headlessly, mints an API token, and provisions projects/users/issues.
See **[docs/local-youtrack.md](docs/local-youtrack.md)** for full details.

| | |
|---|---|
| URL | http://localhost:8080 |
| Admin | `admin` / `Yt-Admin-2026!` |
| API token | in `.env` (`YOUTRACK_TOKEN`) |

### Verify it

```bash
source .env
curl -s -H "Authorization: Bearer $YOUTRACK_TOKEN" \
  "$YOUTRACK_BASE_URL/api/issues?query=project:JT&fields=idReadable,summary" | jq
```

## Seed data

8 projects (`JT`, `IJPL`, `IDEA`, `KT`, `RID`, `WEB`, `PY`, `DEMO`), 11 users, and
~115 issues across all states/priorities/types/subsystems — mirrors the structure of
youtrack.jetbrains.com. Issues are enriched with comments and links to exercise the
full CLI workflow. Re-provision any time with:

```bash
./scripts/provision.py && ./scripts/provision_jewel.py && ./scripts/provision_enrichment.py
```

(idempotent).

### Custom field schema (mirrors youtrack.jetbrains.com)

`provision_jewel.py` applies the exact custom-field layout from the official instance's
**Jewel** project to every project:

| Field | Type | Required | Default |
|---|---|---|---|
| Priority | enum | yes | Normal |
| Type | enum | yes | — |
| State | state | yes | Submitted |
| Subsystems | enum[*] (multi) | no | — |
| Assignee | user | no | — |
| Target version | version | yes | Backlog |
| Included in builds | build[*] (multi) | no | — |
| Available in | version[*] (multi) | no | — |
| Security Severity | enum | no | — |
| Security Problem Type | enum | no | Vulnerability |
| QA | user | no | — |
| Verified | enum | no | — |
| Verified in builds | build[*] (multi) | no | — |

Plus the YouTrack defaults (`Subsystem`, `Fix versions`, `Affected versions`,
`Fixed in build`, `Estimation`, `Spent time`) — handy for exercising every field type
in the CLI.

## Layout

```
scripts/
  setup.sh                   # one-shot install + configure + provision
  configure.py             # complete the wizard + create API token (idempotent)
  provision.py             # seed projects/users/issues (idempotent)
  provision_jewel.py       # apply the youtrack.jetbrains.com custom-field schema
  provision_enrichment.py  # add comments and links for workflow variety
  youtrack.sh              # start/stop/status/logs/shell/reset-data
  query.sh                 # example API calls (reference for building the CLI)
docs/
  local-youtrack.md
.youtrack-server/   # YouTrack persistent data (gitignored)
.env                # base URL + token (gitignored)
```

## API reference (for building the CLI)

All calls use `Authorization: Bearer $YOUTRACK_TOKEN` and return JSON.
YouTrack uses a `fields=` query param to select returned fields (see
[Fields Syntax](https://www.jetbrains.com/help/youtrack/devportal/Fields-Syntax.html)).

| Resource | Method & path |
|---|---|
| Current user | `GET /api/users/me?fields=login,fullName` |
| Issues (search) | `GET /api/issues?query=<youtrack query>&fields=...` |
| Get issue | `GET /api/issues/{id}?fields=...` |
| Create issue | `POST /api/issues` |
| Apply command | `POST /api/issues/{id}/commands` |
| Projects | `GET /api/admin/projects?fields=...` |
| Users | `GET /api/users?fields=...` |
| Custom fields | `GET /api/admin/customFieldSettings/customFields` |

Run `./scripts/query.sh` for live examples.

## License

Licensed under the **Unenshittifiable License (UEL) v1.0**. Free for internal and community
use, modification, and self-hosting. You may not repackage and sell the CLI itself as a
commercial product; improvements stay under UEL. See `LICENSE` for the full text.
