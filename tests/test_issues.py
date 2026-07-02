"""Tests for the query composer and issue data helpers (M1)."""

from __future__ import annotations

import pytest

from youtrack_cli.fields import field_value
from youtrack_cli.query import compose_query


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({}, "for: me #Unresolved"),
        ({"all": True}, ""),
        ({"project": "JT"}, "for: me #Unresolved project: JT"),
        ({"state": "Open"}, "for: me #Unresolved state: Open"),
        ({"assignee": "rock3r"}, "for: me #Unresolved assignee: rock3r"),
        ({"sort": "Priority desc"}, "for: me #Unresolved sort by: Priority desc"),
        ({"all": True, "project": "JT"}, "project: JT"),
        ({"query": "project: JT"}, "project: JT"),
        ({"query": "project: JT", "sort": "created desc"}, "project: JT sort by: created desc"),
    ],
)
def test_compose_query(kwargs, expected) -> None:
    assert compose_query(**kwargs) == expected


def test_explicit_query_overrides_other_filters() -> None:
    assert (
        compose_query(all=True, project="JT", state="Open", query="#show-stopper")
        == "#show-stopper"
    )


@pytest.mark.parametrize(
    ("field_name", "value", "expected"),
    [
        ("State", {"name": "Open"}, "Open"),
        ("Priority", None, ""),
        ("Assignee", {"name": "Admin", "login": "admin"}, "admin"),
        ("Votes", 42, "42"),
        ("Missing", {"name": "x"}, ""),
    ],
)
def test_field_value(field_name, value, expected) -> None:
    issue = {
        "idReadable": "JT-1",
        "customFields": [
            {"name": "State", "value": {"name": "Open"}},
            {"name": "Assignee", "value": {"name": "Admin", "login": "admin"}},
            {"name": "Votes", "value": 42},
        ],
    }
    assert field_value(issue, field_name) == expected


def test_field_value_empty_issue() -> None:
    assert field_value({}, "State") == ""
