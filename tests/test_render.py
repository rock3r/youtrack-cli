"""Tests for the Rich-based renderer (M1)."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from youtrack_cli.render import render_issue, render_issue_table


def _sample_issue() -> dict:
    return {
        "idReadable": "JT-1",
        "summary": "First issue summary",
        "project": {"name": "YouTrack"},
        "updated": 1710000000000,
        "customFields": [
            {"name": "State", "value": {"name": "Open"}},
            {"name": "Priority", "value": {"name": "Major"}},
            {"name": "Type", "value": {"name": "Task"}},
            {"name": "Assignee", "value": {"name": "Admin", "login": "admin"}},
        ],
    }


def _header_row_index(out: str) -> int:
    return out.index("ID")


def test_table_contains_id_and_summary() -> None:
    console = Console(file=StringIO(), force_terminal=False, width=120)
    render_issue_table([_sample_issue()], console=console)
    out = console.file.getvalue()
    assert "JT-1" in out
    assert "First issue summary" in out
    assert "Open" in out
    assert "Major" in out


def test_table_columns_in_contract_order() -> None:
    console = Console(file=StringIO(), force_terminal=False, width=120)
    render_issue_table([_sample_issue()], console=console)
    out = console.file.getvalue()
    idx = _header_row_index(out)
    header_line = out[idx : out.index("\n", idx)]
    # Contract order: ID  STATE  PRIORITY  TYPE  SUMMARY
    assert header_line.index("ID") < header_line.index("STATE")
    assert header_line.index("STATE") < header_line.index("PRIORITY")
    assert header_line.index("PRIORITY") < header_line.index("TYPE")
    assert header_line.index("TYPE") < header_line.index("SUMMARY")


def test_table_renders_missing_fields_as_dash() -> None:
    issue = _sample_issue()
    issue["customFields"] = [{"name": "State", "value": {"name": "Open"}}]
    console = Console(file=StringIO(), force_terminal=False, width=120)
    render_issue_table([issue], console=console)
    out = console.file.getvalue()
    assert "Open" in out
    assert "-" in out


def test_table_truncates_long_summary() -> None:
    issue = _sample_issue()
    issue["summary"] = "A" * 200
    console = Console(file=StringIO(), force_terminal=False, width=80)
    render_issue_table([issue], console=console)
    out = console.file.getvalue()
    assert "…" in out or "A" * 80 not in out


def test_table_golden_output() -> None:
    issue = _sample_issue()
    console = Console(file=StringIO(), force_terminal=False, width=80)
    render_issue_table([issue], console=console)
    expected = (
        "                         Issues                         \n"
        "┏━━━━━━┳━━━━━━━┳━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓\n"
        "┃ ID   ┃ STATE ┃ PRIORITY ┃ TYPE ┃ SUMMARY             ┃\n"
        "┡━━━━━━╇━━━━━━━╇━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩\n"
        "│ JT-1 │ Open  │ Major    │ Task │ First issue summary │\n"
        "└──────┴───────┴──────────┴──────┴─────────────────────┘\n"
    )
    assert console.file.getvalue() == expected


def test_table_no_issues_message() -> None:
    console = Console(file=StringIO(), force_terminal=False, width=120)
    render_issue_table([], console=console)
    out = console.file.getvalue()
    assert "No issues" in out


def test_detail_contains_summary_and_fields() -> None:
    console = Console(file=StringIO(), force_terminal=False, width=120)
    render_issue(_sample_issue(), console=console)
    out = console.file.getvalue()
    assert "JT-1" in out
    assert "First issue summary" in out
    assert "State" in out
    assert "Open" in out


def test_detail_renders_missing_field_as_dash() -> None:
    issue = _sample_issue()
    issue["customFields"] = [{"name": "State", "value": {"name": "Open"}}]
    console = Console(file=StringIO(), force_terminal=False, width=120)
    render_issue(issue, console=console)
    out = console.file.getvalue()
    assert "Priority: -" in out


def test_detail_renders_multi_value_field() -> None:
    issue = _sample_issue()
    issue["customFields"].append(
        {"name": "Subsystems", "value": [{"name": "UI"}, {"name": "Core"}]}
    )
    console = Console(file=StringIO(), force_terminal=False, width=120)
    render_issue(issue, console=console)
    out = console.file.getvalue()
    assert "Subsystems: UI, Core" in out
