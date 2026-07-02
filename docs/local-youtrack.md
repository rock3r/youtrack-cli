# Local YouTrack instance (Apple Container)

A fully automated local JetBrains YouTrack server running in
[Apple's `container`](https://github.com/apple/container) tool, provisioned with
a realistic structure that mirrors [youtrack.jetbrains.com](https://youtrack.jetbrains.com)
so we can build and test the YouTrack CLI against representative data, schemas,
and workflows.

## What you get

| | |
|---|---|
| **YouTrack** | `jetbrains/youtrack:2026.2.17012`, running in an Apple Container VM |
| **URL** | http://localhost:8080 |
| **Admin** | `admin` / `Yt-Admin-2026!` |
| **API token** | written to `.env` (`YOUTRACK_TOKEN`) |
| **Data** | `.youtrack-server/{data,conf,logs,backups}` (persistent across restarts) |

### Seed data

- **8 projects**: `DEMO` (built-in demo project) + `JT` (YouTrack), `IJPL` (IntelliJ
  Platform), `IDEA` (IntelliJ IDEA), `KT` (Kotlin Plugin), `RID` (Rider), `WEB`
  (WebStorm), `PY` (PyCharm).
- **~115 issues** across all major states: `Submitted`, `Open`, `In Progress`,
  `To be discussed`, `Reopened`, `Fixed`, `Verified`, `Won't fix`, `Can't Reproduce`.
- **Priorities**: `Show-stopper`, `Critical`, `Major`, `Normal`, `Minor`.
- **Types**: `Bug`, `Feature`, `Task`, `Cosmetics`, `Exception`, `Performance Problem`, `Epic`.
- **Subsystems** per project (e.g. `Editor`, `VCS`, `Debugger`, `Plugins`, `UI`, …).
- **11 users**: `admin` plus 10 team members; 4 groups (`Developers`, `QA Engineers`,
  `Designers`, `YouTrack Team`).
- **Workflow variety**: many issues have comments and links (`relates to`, `depends on`,
  `duplicates`) thanks to `provision_enrichment.py`.

### Field schema variety

`scripts/provision_jewel.py` applies the exact custom-field schema from the **Jewel**
project on youtrack.jetbrains.com to every project (except `DEMO`, which keeps the
out-of-the-box YouTrack fields):

| Field | Type | Multi | Required | Default / Empty text |
|---|---|---|---|---|
| Priority | enum | no | yes | `Normal` |
| Type | enum | no | yes | — |
| State | state | no | yes | `Submitted` |
| Subsystems | enum | yes | no | `No Subsystems` |
| Assignee | user | no | no | `Unassigned` |
| Target version | version | no | yes | `Backlog` |
| Included in builds | build | yes | no | `No included in builds` |
| Available in | version | yes | no | `No available in` |
| Security Severity | enum | no | no | `None` |
| Security Problem Type | enum | no | no | `Vulnerability` |
| QA | user | no | no | `No qa` (hidden) |
| Verified | enum | no | no | `No verified` |
| Verified in builds | build | yes | no | `No verified in builds` |

The `DEMO` project keeps the default YouTrack fields (`Subsystem`, `Fix versions`,
`Affected versions`, `Fixed in build`, `Estimation`, `Spent time`) so the local setup
also exercises the standard built-in schema.

## Prerequisites

- macOS 26 (Tahoe) on Apple silicon — required by Apple Container.
- [Homebrew](https://brew.sh) for installing `container`.

## Setup (automated)

Everything — install Apple Container, run YouTrack, complete the wizard, mint the API
token, and provision seed data — is done by one script:

```bash
./scripts/setup.sh
```

What it does:

1. Installs `container` if needed and starts the Apple Container system.
2. Creates persistent data directories under `.youtrack-server/`.
3. Runs the YouTrack container image (downloads ~3 GB on first run).
4. Completes the first-run configuration wizard headlessly via `/api/wizard/*`.
5. Waits for the YouTrack service to accept requests.
6. Runs the provisioning chain:
   - `scripts/provision.py` — creates users, groups, projects, and issues.
   - `scripts/provision_jewel.py` — applies the youtrack.jetbrains.com custom-field schema.
   - `scripts/provision_enrichment.py` — adds comments and links between issues.

If you prefer to run each step manually, read on.

### 1. Install & start Apple Container

```bash
brew install container
container system start
container system kernel set --recommended   # downloads the Linux kernel once
```

### 2. Run YouTrack

```bash
./scripts/youtrack.sh start
```

The first boot triggers the **Configuration Wizard**. `scripts/configure.py` (called by
`setup.sh`) completes it headlessly.

### 3. Configure the wizard and create an API token

```bash
python3 scripts/configure.py
```

This sets the base URL, the admin password (`Yt-Admin-2026!`), accepts the default
license, and creates a permanent API token with scopes **YouTrack** and **YouTrack
Administration**. The token is saved in `.env`.

### 4. Provision the data

```bash
python3 scripts/provision.py
python3 scripts/provision_jewel.py
python3 scripts/provision_enrichment.py
```

All three scripts are idempotent — safe to re-run after the initial setup.

## Authentication for the CLI

A permanent API token for `admin` is stored in `.env`:

```bash
# .env
YOUTRACK_BASE_URL=http://localhost:8080
YOUTRACK_TOKEN=perm-...        # Bearer token for the REST API
YOUTRACK_ADMIN_USER=admin
YOUTRACK_ADMIN_PASSWORD=Yt-Admin-2026!
```

Use it as:

```bash
source .env
curl -H "Authorization: Bearer $YOUTRACK_TOKEN" \
  "$YOUTRACK_BASE_URL/api/issues?query=project:JT&fields=idReadable,summary"
```

## Day-to-day commands

```bash
./scripts/youtrack.sh status     # health + container info
./scripts/youtrack.sh logs 100   # last 100 log lines
./scripts/youtrack.sh stop       # stop the VM (data persists)
./scripts/youtrack.sh start      # resume the VM
./scripts/youtrack.sh shell      # bash inside the container
./scripts/youtrack.sh reset-data # ⚠ wipe everything, fresh install
```

> Container auto-starts on login via `brew services`. If the system service isn't
> running, `./scripts/youtrack.sh start` will fail with a connection error — run
> `container system start` first.

## Re-provisioning

You can re-run individual provisioning scripts at any time to refresh the data after
a schema change or to add more variety:

```bash
python3 scripts/provision.py             # re-creates users/groups/projects/issues (idempotent)
python3 scripts/provision_jewel.py       # re-applies the Jewel schema
python3 scripts/provision_enrichment.py  # adds comments/links to existing issues
```

If you want a completely clean start:

```bash
./scripts/youtrack.sh reset-data
./scripts/setup.sh
```

> **Note on description templates:** `scripts/provision.py` only creates issues when they
> do not already exist. If you re-run provisioning after upgrading issue templates, existing
> issues keep their old descriptions. Use `reset-data` for a fresh seed that uses the latest
> templates.

## Notes / gotchas

- **Memory format**: Apple Container's `-m` flag wants a plain suffix (`4G`), not `4Gi`.
- **Image size**: the first `container run` fetches a ~3 GB YouTrack image; the initial
  kernel download is separate (~60 MB).
- **Permissions**: data directories are created with mode `777` so the container's UID
  `13001` can write to them without host `sudo`. This is acceptable for a local dev box.
- **Assignee eligibility**: a fresh YouTrack project only lets you assign to the project
  leader or project-team members. `provision.py` falls back to the leader when a chosen
  assignee isn't eligible, so every issue still gets created.
- **License**: the bundled free license caps at 10 users.
- **Field schema timing**: `provision_jewel.py` runs after issues are created, so the
  Jewel fields are attached to projects and available for `yt edit` even if existing
  issues were not born with values for those fields. `provision_enrichment.py` then adds
  comments and links on top.
