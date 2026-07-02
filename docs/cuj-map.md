# Core User Journeys (CUJs) — v0.1 implementation

This document describes the CLI behavior that is implemented today. It intentionally avoids
future/v1 ideas so published docs do not promise flags or behaviors that are not present.

Implemented commands:

- `yt status`
- `yt issues`
- `yt show <id>`
- `yt create <project> <summary>`
- `yt edit <issue>`
- `yt comment <issue> <text>`
- `yt link <issue> <type> <target>`
- `yt auth login`

Global options are parsed by Typer before the subcommand, so put them first:
`yt --output json issues`, not `yt issues --output json`. Globals include `--output`,
`--base-url`, `--token`, `--config`, `--op-vault`, `--op-item`, `--op-field`, `--no-color`,
`--quiet`, and `--version`.

Conventions:
- All API calls use `Authorization: Bearer <token>` and explicit YouTrack `fields=`
  projections.
- `idReadable` is the human issue ID such as `JT-1`.
- Entity `$type` discriminators are included where YouTrack requires them.

---

## 0. Foundational: configure & authenticate

**Implemented.** Commands resolve a base URL and token before calling YouTrack.

Config sources, in precedence order:

1. Explicit flags: `--base-url`, `--token`, and `--config` for the config path.
2. Environment variables: `YOUTRACK_BASE_URL`, `YOUTRACK_TOKEN`.
3. Current working directory `.env`.
4. Config file, defaulting to `~/.config/youtrack-cli/config.toml`.
5. 1Password CLI (`op`): `--op-vault`, `--op-item`, `--op-field` (or `YOUTRACK_OP_*`
   environment variables). The token is fetched once per command and cached for the process.
6. Base URL default: `http://localhost:8080`.

Security caveat: flag and environment values are composable per key, but `.env` and the
config file are not mixed when the token comes from either of those sources. If the token
comes from `.env`, the config-file base URL is ignored; if the token comes from the config
file, the `.env` base URL is ignored. This avoids accidentally combining credentials from a
trusted home config with a potentially untrusted project directory.

`yt auth login` prompts for the base URL and a permanent token. The token prompt uses hidden
input. Credentials are written to the config file with mode `0600`; the parent config
directory is created/tightened to `0700` when applicable.

`yt status` performs the health check with:

- `GET /api/users/me?fields=login,fullName`

Expected behavior:

- 200: print the connected user (or JSON with `--output json`).
- 401/403: report an authentication/permission error.
- Connection failure: report API failure with guidance to start the local server.

---

## 1. Create issue

**User story:** create an issue in a project with a summary, optional description, and a
small set of supported field values.

**CLI surface**

```text
yt create <project> <summary> [--description|-d <text>]
           [--type <T>] [--priority <P>] [--state <S>] [--assignee <login>]
           [--field <Name>=<value>]... [--dry-run]
```

The command creates one issue per invocation and does not retry automatically with altered
field values after a server rejection.

**API shape**

The command resolves the project and project custom-field schema, builds typed custom-field
values, and sends:

- `POST /api/issues?fields=...`

`--dry-run` builds and prints the request body without sending it.

**Supported field input**

- Convenience flags map to YouTrack custom fields: `--type`, `--priority`, `--state`,
  `--assignee`.
- `--field Name=value` is repeatable. Values are split on the first `=`.
- Multi-value fields use comma-separated values in the current implementation.
- Supported typed custom fields are the implemented YouTrack bundle-backed types:
  `state`, `enum`, `user`, `ownedField`, `version`, and `build`.
- Period fields are rejected on create with guidance to set them later via `yt edit`.

**Validation and errors**

- Unknown projects or inaccessible projects are reported as validation/not-found style
  errors, with the usual YouTrack caveat that lack of access can look like not found.
- Bundle-backed non-user values are validated against the schema values available from the
  project custom-field response.
- Assignee eligibility is validated by YouTrack server-side. If the server returns
  `Value is not allowed` for a request that included `--assignee`, the CLI surfaces the
  error with a contextual hint that the assignee may not be eligible and suggests retrying
  without `--assignee`. It does not create a different issue automatically.
- Required-field and workflow guards are surfaced from the server error payload.

**Output**

Text mode prints `Created <ID>: <summary>`. JSON mode wraps the created issue in the common
`{"ok": true, "data": ...}` envelope.

---

## 2. Edit issue, comment, and link

**User story:** update a single issue, add a plain comment, or create a link using the
YouTrack command language.

**CLI surface**

```text
yt edit <issue> [--summary <s>] [--description|-d <d>]
        [--type <T>] [--priority <P>] [--state <S>] [--assignee <login>]
        [--field <Name>=<value>]... [--command|-c <youtrack command>]

yt comment <issue> <text>
yt link <issue> <type> <target>
```

The edit command targets one issue per invocation. Comment visibility, notification controls,
batch result reporting, and diff-style output are outside the current implementation.

**API behavior**

- `--summary` and `--description` use a direct issue update:
  `POST /api/issues/{idReadable}`.
- `--type`, `--priority`, `--state`, `--assignee`, non-period `--field`, and `--command`
  are translated into a single YouTrack command query and posted to `/api/commands`.
- Period `--field` values are applied through the direct issue update path.
- `yt comment` posts a plain comment to `/api/issues/{idReadable}/comments`.
- `yt link` posts a command-language link expression through `/api/commands`. Common
  underscore names such as `relates_to` are normalized to the YouTrack phrase.

**Validation and errors**

- The edit command targets one issue at a time.
- If both command-style changes and direct updates are requested, the command request runs
  before the direct update. There is no multi-operation transaction or rollback.
- Workflow guards and permission failures are reported from the server response.
- Assignee eligibility failures are surfaced explicitly; edits do not silently drop values.

**Output**

Text mode prints `Updated <ID>`, `Commented on <ID>`, or `Linked <ID> <type> <target>`.
JSON mode returns the common envelope with `data: null` for edit/comment/link.

---

## 3. Search and show issues

**User story:** list issues with implemented filters, or show details for one issue.

**CLI surface**

```text
yt issues [--all]
          [--project <p>] [--state <s>] [--assignee <login>]
          [--query <youtrack query>] [--sort <sort expression>]
          [--limit <n>] [--offset <n>]

yt show <id>
```

Query input is through flags only; there is no positional query argument. Custom list columns
and extra pagination warnings are outside the current implementation.

**Default query**

`yt issues` with no filters lists the current user's unresolved issues using the YouTrack
query:

```text
for: me #Unresolved
```

Use `--all` to omit that default and list without the default query constraint.

**Implemented query construction**

- `--query` supplies a raw YouTrack query string.
- `--project`, `--state`, and `--assignee` append supported structured terms.
- `--sort` appends a `sort by:` term.
- `--limit` maps to `$top`; `--offset` maps to `$skip`.

**API behavior**

- List: `GET /api/issues` with explicit fields for ID, summary, updated timestamp, project,
  and rendered custom fields.
- Show: `GET /api/issues/{id}` with summary, description, project, created/updated,
  reporter/assignee, and a fixed set of rendered custom fields.

`yt show` does not fetch or render comments or issue links.

**Output**

The default list output is a table with:

```text
ID  STATE  PRIORITY  TYPE  SUMMARY
```

`SUMMARY` is truncated by Rich to fit terminal width. JSON mode returns the raw issue data in
the common envelope.

---

## Cross-cutting: output & UX rules

- Exit codes: `0` success, `2` usage/argument error, `3` validation error, `4` not found,
  `5` permission/authentication, `6` workflow guard, `1` other API/server error.
- Text mode is human-first and keeps stdout for command output. Errors go to stderr.
- `--output json` and `--json` switch success and error output to the common JSON envelope.
- `--quiet` suppresses non-essential human output but not errors or JSON data.
- `--no-color` disables Rich color.
- Never print secrets. Tokens are read from flags, environment, `.env`, or config and are not
  echoed by normal commands.
