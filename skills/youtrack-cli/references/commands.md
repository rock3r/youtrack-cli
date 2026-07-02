# Command reference for `yt`

Use this reference when constructing or double-checking `youtrack-cli` commands. The main `SKILL.md` contains the common path and gotchas; this file is the extended command matrix.

## Status and connectivity

```bash
yt status
yt --base-url https://youtrack.example.com --token $TOKEN status
yt --version
```

## Search and show

```bash
yt issues                              # my unresolved issues
yt issues --all --limit 50             # all issues, 50 rows
yt issues --project JT --state Open
yt issues --assignee alice --sort "Priority desc"
yt issues --query "project: JT #Unresolved state: Open" --limit 20 --offset 20
yt show JT-1
yt --output json issues --project JT --limit 100
```

## Create

```bash
yt create DEMO "Fix the widget" --description "It is broken." \
  --type Bug --priority Major --state Submitted --assignee alice

# Custom fields (repeatable, split on first =)
yt create DEMO "Add feature" --type Task --field "Subsystems=Core" --field "Target version=2026.1"

# Multi-value custom field
yt create DEMO "Cross-platform fix" --field "Subsystems=Core,UI"

# Preview only
yt create DEMO "Test" --type Task --dry-run
```

## Edit

```bash
yt edit JT-1 --state Done --summary "Fixed the widget"
yt edit JT-1 --description "Updated description"
yt edit JT-1 --assignee bob
yt edit JT-1 --field "Priority=Critical" --field "Subsystems=Core,UI"

# Raw YouTrack command language for fields not exposed as flags
yt edit JT-1 --command "Subsystem UI"
```

## Comment and link

```bash
yt comment JT-1 "Verified on staging"
yt link JT-1 relates_to JT-2
```

Common link types: `relates_to`, `duplicates`, `depends_on`.

## Authentication helpers

```bash
yt auth login
yt --op-vault Private --op-item "YouTrack token" --op-field "api token" status
```
