# Changelog

Format inspired by [Keep a Changelog](https://keepachangelog.com/). Version numbers match
`pyproject.toml`.

## [Unreleased]

### Added

- Agent skill `skills/youtrack-cli/` for discovering and using the `yt` CLI via `npx skill add`.

## [0.1.0] — 2026-07-02

First public preview of `jetbrains-youtrack-cli` (`yt`). Targets the YouTrack REST API
(developed and tested against YouTrack 2026.2).

### Added

- `yt status` — connectivity and authentication check via `/api/users/me`.
- `yt issues` — search and list with filters (`--project`, `--state`, `--assignee`,
  `--query`, `--sort`), pagination (`--limit`, `--offset`), table output, and `--output json`.
- `yt show` — issue detail view.
- `yt create` — create issues with description, common field flags, repeatable `--field`,
  and `--dry-run`.
- `yt edit` — update summary/description, field flags, repeatable `--field`, and raw
  YouTrack `--command`.
- `yt comment` and `yt link` — add comments and issue links via the REST API / command
  language.
- `yt auth login` — save credentials to `~/.config/youtrack-cli/config.toml` (mode `0600`).
- Configuration from flags, environment, CWD `.env`, config file, or 1Password CLI (`op`)
  as the **last** token source (`--op-vault`, `--op-item`, `--op-field` or `YOUTRACK_OP_*`).
- Global options: `--output` / `--json`, `--base-url`, `--token`, `--config`, `--no-color`,
  `--quiet`, `--version` (must appear before the subcommand).
- Standalone zipapp: `make standalone` → `dist/yt.pyz`.
- Local dev environment: Apple Container YouTrack instance, seed scripts, and documentation
  in `docs/local-youtrack.md`.

### Notes

- Pre-alpha (`Development Status :: 2 - Pre-Alpha`). API and CLI surface may change.
- Licensed under UEL v1.0 — see `LICENSE` and README.

[Unreleased]: https://github.com/rock3r/youtrack-cli/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rock3r/youtrack-cli/releases/tag/v0.1.0
