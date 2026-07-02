"""Rich-based rendering for the CLI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from rich.console import Console
from rich.table import Table

from youtrack_cli.fields import field_value


def _console(console: Console | None, *, no_color: bool = False) -> Console:
    if console is None:
        return Console(no_color=no_color, highlight=False)
    return console


def _fmt_ts(timestamp: int | None) -> str:
    if not timestamp:
        return ""
    try:
        dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return str(timestamp)
    return dt.strftime("%Y-%m-%d")


def render_issue_table(
    issues: list[dict[str, Any]], *, console: Console | None = None, no_color: bool = False
) -> None:
    """Render a list of issues as a Rich table."""
    c = _console(console, no_color=no_color)
    if not issues:
        c.print("No issues found.")
        return

    table = Table(title="Issues")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("STATE")
    table.add_column("PRIORITY")
    table.add_column("TYPE")
    # Truncate SUMMARY to the remaining terminal width so long summaries do not
    # force an unusably wide table. Rich renders the ellipsis.
    summary_width = max(20, c.width - 45) if c.width else 60
    table.add_column("SUMMARY", style="green", overflow="ellipsis", max_width=summary_width)

    for issue in issues:
        table.add_row(
            issue.get("idReadable", ""),
            field_value(issue, "State") or "-",
            field_value(issue, "Priority") or "-",
            field_value(issue, "Type") or "-",
            issue.get("summary", ""),
        )
    c.print(table)


def render_issue(
    issue: dict[str, Any], *, console: Console | None = None, no_color: bool = False
) -> None:
    """Render a single issue in detail."""
    c = _console(console, no_color=no_color)
    id_readable = issue.get("idReadable", "")
    summary = issue.get("summary", "")
    project = (issue.get("project") or {}).get("name", "")

    c.print(f"[cyan bold]{id_readable}[/cyan bold]: {summary}")
    if project:
        c.print(f"Project: {project}")
    c.print("-" * 40)

    for field_name in (
        "State",
        "Type",
        "Priority",
        "Assignee",
        "Subsystems",
        "Target version",
        "Verified",
    ):
        value = field_value(issue, field_name)
        c.print(f"[bold]{field_name}:[/bold] {value or '-'}")

    c.print(f"[bold]Created:[/bold]  {_fmt_ts(issue.get('created'))}")
    c.print(f"[bold]Updated:[/bold]  {_fmt_ts(issue.get('updated'))}")

    description = issue.get("description") or ""
    if description:
        c.print()
        c.print("[bold]Description:[/bold]")
        c.print(description)
