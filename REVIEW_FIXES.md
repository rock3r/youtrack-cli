## Review fixes

Internal development notes from pre-release review — **not** user-facing release notes.
See `CHANGELOG.md` for what ships in each tag.

- Fix JSON error envelope for non-API `CliError`s (ConfigError, ValidationError) so `exit_code` matches the actual exit code.
- Prevent CWD `.env` from leaking a stored config token: `.env` and config-file base_url/token are no longer mixed when the token comes from a different source.
- Write config file atomically with `0o600` and create parent directory with `0o700`.
- Replace real-looking token in `.env.example` with `REPLACE_ME_WITH_YOUTRACK_TOKEN`.
- Move `compose_query` to `query.py` and `field_value` to `fields.py` to respect module boundaries.
- Fix default `yt issues` columns to `ID STATE PRIORITY TYPE SUMMARY` per contract.
- Render missing/null fields as `-` and multi-value lists joined with `, `.
- Disable Rich auto-highlighting so issue IDs like `JT-1` are not split by terminal styling.
- Honor `--no-color` by passing it through to the Rich Console.
- Add `Makefile` `format-check` target and make `check` depend on it instead of mutating `format`.
- Add `__version__` in package `__init__.py` and use it for `--version`.
- Add security test for `.env` base_url ignoring when token comes from config.
