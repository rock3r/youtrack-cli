# Contributing to youtrack-cli

First: thank you. A few short rules keep this pleasant for everyone.

## License

This project is licensed under the **Unenshittifiable License (UEL) v1.0** (`LICENSE` /
<https://uelicense.eu>). Unless you state otherwise, any contribution you make is offered
under the same license (UEL §06) so it can benefit everyone.

If your contribution is substantial or you'd prefer to be explicit, add yourself to the
authors in `pyproject.toml` and/or the file's copyright line. Keep the `LICENSE` and
copyright notices intact (UEL §03) in any substantial portion you copy.

## Before you open a PR

Run the local gate (see `docs/development.md`):

```bash
ruff check . && ruff format --check . && mypy && pytest
```

For anything touching real YouTrack behavior, also run `make test-live` against the seeded
local instance (`./scripts/setup.sh`).

## How we work

- **Test-first.** We write failing tests against the frozen contracts in
  `docs/contracts.md`, then implement. See `docs/development.md` § "How we work: TDD".
- **Quirks are sacred.** `docs/cuj-map.md` documents YouTrack's real API quirks. There's a
  regression test for each one — don't make them go red.
- **No import cycles.** The dependency rules in `docs/contracts.md` ("Import rules") are
  enforced by review. `typer` lives only in `youtrack_cli/cli/`.
- **Keep deps small & portable.** This CLI is meant to run anywhere Python 3.10+ does. New
  runtime dependencies need a real justification.

## Commits & PRs

- Small, focused PRs. One logical change each.
- Clear commit messages; state significant changes (UEL §03 asks forks to be distinguishable).
- Reference the relevant CUJ/contract in the PR description if it's non-trivial.

## Reporting issues / quirks

Found a YouTrack behavior we get wrong? Open an issue with the exact request/response and add
it to `docs/cuj-map.md` — the map is the source of truth for what the CLI must handle.
