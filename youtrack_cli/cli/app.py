"""Typer app + commands. typer lives ONLY here (import rule, docs/contracts.md)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import typer

from youtrack_cli import __version__
from youtrack_cli.client import Client
from youtrack_cli.config import Config, resolve, write_config
from youtrack_cli.errors import APIError, CliError, ExitCode
from youtrack_cli.issues import (
    ISSUE_LIST_FIELDS,
    ISSUE_SHOW_FIELDS,
    add_comment,
    create_issue,
    edit_issue,
    link_issue,
)
from youtrack_cli.onepassword import fetch_token
from youtrack_cli.query import compose_query
from youtrack_cli.render import render_issue, render_issue_table


def _version_callback(value: bool, ctx: typer.Context) -> None:
    if ctx.resilient_parsing:
        return
    if value:
        typer.echo(f"yt {__version__}")
        raise typer.Exit(0)


app = typer.Typer(
    name="yt",
    help="A portable command-line client for the JetBrains YouTrack REST API.",
    no_args_is_help=True,
    add_completion=True,
)


@dataclass
class Options:
    output: str = "table"
    base_url: str | None = None
    token: str | None = None
    config_path: str | None = None
    no_color: bool = False
    quiet: bool = False
    op_vault: str | None = None
    op_item: str | None = None
    op_field: str = "password"


_opts = Options()


@app.callback()
def _main(
    output: str = typer.Option("table", "--output", "-o", help="Output format: table or json."),
    json_out: bool = typer.Option(False, "--json", help="Alias for --output json."),
    base_url: str | None = typer.Option(None, "--base-url", help="YouTrack base URL."),
    token: str | None = typer.Option(None, "--token", help="Permanent API token."),
    config_path: str | None = typer.Option(None, "--config", help="Path to config file."),
    op_vault: str | None = typer.Option(
        None, "--op-vault", help="1Password vault containing the token."
    ),
    op_item: str | None = typer.Option(
        None, "--op-item", help="1Password item containing the token."
    ),
    op_field: str | None = typer.Option(
        None, "--op-field", help="1Password field to use (default: password)."
    ),
    version: bool = typer.Option(
        False, "--version", help="Show version and exit.", callback=_version_callback, is_eager=True
    ),
    no_color: bool = typer.Option(False, "--no-color", help="Disable color."),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress non-essential output."),
) -> None:
    """Set global options."""
    _opts.output = "json" if (json_out or output == "json") else "table"
    _opts.base_url = base_url
    _opts.token = token
    _opts.config_path = config_path
    _opts.no_color = no_color
    _opts.quiet = quiet

    # 1Password source: stash options; resolution happens lazily in _resolve_config().
    # Env vars are used as fallback when the flags are not provided.
    _opts.op_vault = op_vault or os.environ.get("YOUTRACK_OP_VAULT")
    _opts.op_item = op_item or os.environ.get("YOUTRACK_OP_ITEM")
    _opts.op_field = (op_field or os.environ.get("YOUTRACK_OP_FIELD")) or "password"


def _error_payload(err: Exception) -> dict[str, Any]:
    if isinstance(err, APIError):
        return {
            "code": err.exit_code.name,
            "exit_code": int(err.exit_code),
            "status": err.status,
            "message": err.description or str(err),
            "rule_name": err.rule_name,
            "field": err.field,
            "type": err.type,
            "workflow_type": err.workflow_type,
            "request": {"method": err.request_method, "path": err.request_path},
        }
    if isinstance(err, CliError):
        return {
            "code": err.exit_code.name,
            "exit_code": int(err.exit_code),
            "status": None,
            "message": str(err) or err.__class__.__name__,
            "rule_name": None,
            "field": None,
            "type": None,
            "workflow_type": None,
            "request": None,
        }
    return {
        "code": ExitCode.API.name,
        "exit_code": int(ExitCode.API),
        "status": None,
        "message": str(err) or err.__class__.__name__,
        "rule_name": None,
        "field": None,
        "type": None,
        "workflow_type": None,
        "request": None,
    }


def _emit_error(err: Exception) -> None:
    payload = _error_payload(err)
    if _opts.output == "json":
        typer.echo(json.dumps({"ok": False, "error": payload}, sort_keys=True))
        return
    msg = payload["message"] or "error"
    typer.echo(f"✗ {msg}", err=True)
    if isinstance(err, APIError) and err.status == 0:
        typer.echo(
            "  is the YouTrack server running? (start it with: ./scripts/youtrack.sh start)",
            err=True,
        )
    if isinstance(err, APIError) and err.field and err.exit_code == ExitCode.WORKFLOW:
        typer.echo(f"  workflow guard on field: {err.field}", err=True)


def _run(action: Any) -> None:
    """Run `action()` (a zero-arg callable) with unified error/exit handling."""
    try:
        action()
    except CliError as e:
        _emit_error(e)
        raise typer.Exit(int(e.exit_code)) from e
    except typer.Exit:
        raise
    except Exception as e:
        _emit_error(e)
        raise typer.Exit(int(ExitCode.API)) from e


def _resolve_config() -> Config:
    """Resolve configuration, using 1Password only as the last token source."""
    op_fetcher = None
    if _opts.op_item:
        op_fetcher = lambda: fetch_token(  # noqa: E731 — small inline factory
            vault=_opts.op_vault or "",
            item=_opts.op_item,
            field=_opts.op_field,
        )
    return resolve(
        base_url=_opts.base_url,
        token=_opts.token,
        config_path=_opts.config_path,
        op_token=op_fetcher,
    )


def _do_status() -> None:
    cfg = _resolve_config()
    client = Client(cfg)
    me = client.get("/api/users/me", fields="login,fullName")
    me = me or {}
    login = me.get("login") or "?"
    full = me.get("fullName") or login
    if _opts.output == "json":
        typer.echo(
            json.dumps(
                {"ok": True, "data": {"login": login, "full_name": full, "base_url": cfg.base_url}},
                sort_keys=True,
            )
        )
    elif not _opts.quiet:
        typer.echo(f"✓ connected to {cfg.base_url} as {login} ({full})")


@app.command()
def status() -> None:
    """Check connectivity and authentication against YouTrack."""
    _run(_do_status)


@app.command()
def issues(
    all: bool = typer.Option(False, "--all", help="Show all issues, not only your open ones."),
    project: str | None = typer.Option(
        None, "--project", "-p", help="Filter by project short name."
    ),
    state: str | None = typer.Option(None, "--state", "-s", help="Filter by state name."),
    assignee: str | None = typer.Option(None, "--assignee", "-a", help="Filter by assignee login."),
    query: str | None = typer.Option(None, "--query", "-q", help="Use a raw YouTrack query."),
    sort: str | None = typer.Option(None, "--sort", help="Sort order, e.g. 'Priority desc'."),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum issues to return."),
    offset: int = typer.Option(
        0, "--offset", "--skip", help="Skip this many issues before returning results."
    ),
) -> None:
    """Search and list issues."""

    def _do() -> None:
        cfg = _resolve_config()
        client = Client(cfg)
        q = compose_query(
            all=all, project=project, state=state, assignee=assignee, query=query, sort=sort
        )
        data = client.get(
            "/api/issues",
            params={"query": q, "$top": str(limit), "$skip": str(offset)},
            fields=ISSUE_LIST_FIELDS,
        )
        if _opts.output == "json":
            typer.echo(json.dumps({"ok": True, "data": data}, sort_keys=True))
        elif not _opts.quiet:
            render_issue_table(data, no_color=_opts.no_color)

    _run(_do)


@app.command()
def show(id: str) -> None:
    """Show full details of a single issue."""

    def _do() -> None:
        cfg = _resolve_config()
        client = Client(cfg)
        issue = client.get(f"/api/issues/{id}", fields=ISSUE_SHOW_FIELDS)
        if _opts.output == "json":
            typer.echo(json.dumps({"ok": True, "data": issue}, sort_keys=True))
        elif not _opts.quiet:
            render_issue(issue, no_color=_opts.no_color)

    _run(_do)


@app.command()
def create(
    project: str,
    summary: str,
    description: str | None = typer.Option(None, "--description", "-d", help="Issue description."),
    issue_type: str | None = typer.Option(None, "--type", help="Issue type (e.g. Bug, Task)."),
    priority: str | None = typer.Option(None, "--priority", help="Priority (e.g. Major)."),
    state: str | None = typer.Option(None, "--state", help="Initial state (e.g. Submitted)."),
    assignee: str | None = typer.Option(None, "--assignee", "-a", help="Assignee login."),
    field: list[str] = typer.Option([], "--field", "-f", help="Generic field: Name=value."),  # noqa: B008 — typer handles mutable defaults safely
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the request body and exit."),
) -> None:
    """Create a new issue in a project."""

    def _do() -> None:
        cfg = _resolve_config()
        client = Client(cfg)
        result = create_issue(
            client,
            project,
            summary,
            description=description,
            issue_type=issue_type,
            priority=priority,
            state=state,
            assignee=assignee,
            fields=field,
            dry_run=dry_run,
        )
        if dry_run:
            if _opts.output == "json":
                typer.echo(json.dumps({"ok": True, "data": result}, sort_keys=True))
            elif not _opts.quiet:
                typer.echo(json.dumps(result, sort_keys=True, indent=2))
            return
        if _opts.output == "json":
            typer.echo(json.dumps({"ok": True, "data": result}, sort_keys=True))
        elif not _opts.quiet:
            typer.echo(f"Created {result['idReadable']}: {result['summary']}")

    _run(_do)


@app.command()
def edit(
    issue_id: str,
    summary: str | None = typer.Option(None, "--summary", help="New summary."),
    description: str | None = typer.Option(None, "--description", "-d", help="New description."),
    issue_type: str | None = typer.Option(None, "--type", help="New issue type."),
    priority: str | None = typer.Option(None, "--priority", help="New priority."),
    state: str | None = typer.Option(None, "--state", help="New state."),
    assignee: str | None = typer.Option(None, "--assignee", "-a", help="New assignee login."),
    field: list[str] = typer.Option([], "--field", "-f", help="Generic field: Name=value."),  # noqa: B008 — typer handles mutable defaults safely
    command: str | None = typer.Option(None, "--command", "-c", help="Raw YouTrack command."),
) -> None:
    """Edit an existing issue."""

    def _do() -> None:
        cfg = _resolve_config()
        client = Client(cfg)
        edit_issue(
            client,
            issue_id,
            summary=summary,
            description=description,
            issue_type=issue_type,
            priority=priority,
            state=state,
            assignee=assignee,
            fields=field,
            command=command,
        )
        if _opts.output == "json":
            typer.echo(json.dumps({"ok": True, "data": None}, sort_keys=True))
        elif not _opts.quiet:
            typer.echo(f"Updated {issue_id}")

    _run(_do)


@app.command()
def comment(issue_id: str, text: str) -> None:
    """Add a comment to an issue."""

    def _do() -> None:
        cfg = _resolve_config()
        client = Client(cfg)
        add_comment(client, issue_id, text)
        if _opts.output == "json":
            typer.echo(json.dumps({"ok": True, "data": None}, sort_keys=True))
        elif not _opts.quiet:
            typer.echo(f"Commented on {issue_id}")

    _run(_do)


@app.command()
def link(issue_id: str, link_type: str, target: str) -> None:
    """Link two issues (e.g. relates_to, duplicates, depends_on)."""

    def _do() -> None:
        cfg = _resolve_config()
        client = Client(cfg)
        link_issue(client, issue_id, link_type, target)
        if _opts.output == "json":
            typer.echo(json.dumps({"ok": True, "data": None}, sort_keys=True))
        elif not _opts.quiet:
            typer.echo(f"Linked {issue_id} {link_type} {target}")

    _run(_do)


auth_app = typer.Typer(help="Authentication commands")
app.add_typer(auth_app, name="auth")


@auth_app.command("login")
def login(
    base_url: str | None = typer.Option(
        None, "--base-url", help="YouTrack base URL (prompted if omitted)."
    ),
    token: str | None = typer.Option(
        None, "--token", help="Permanent API token (prompted securely if omitted)."
    ),
) -> None:
    """Save YouTrack credentials to the config file (mode 0600)."""

    def _do() -> None:
        if not base_url:
            default_url = _opts.base_url or "http://localhost:8080"
            resolved_base = typer.prompt("YouTrack base URL", default=default_url)
        else:
            resolved_base = base_url

        resolved_token = token or _opts.token
        if not resolved_token and _opts.op_item:
            resolved_token = fetch_token(
                vault=_opts.op_vault or "",
                item=_opts.op_item,
                field=_opts.op_field,
            )
        if not resolved_token:
            resolved_token = typer.prompt("Permanent API token", hide_input=True)

        path = write_config(resolved_base, resolved_token, _opts.config_path)
        if _opts.output == "json":
            typer.echo(json.dumps({"ok": True, "data": {"config_path": str(path)}}, sort_keys=True))
        elif not _opts.quiet:
            typer.echo(f"✓ credentials saved to {path}")

    _run(_do)
