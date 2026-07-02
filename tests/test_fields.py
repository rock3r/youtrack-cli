"""Tests for youtrack_cli.fields — project schema + typed field bodies (M2)."""

from __future__ import annotations

import pytest

from youtrack_cli.errors import ValidationError
from youtrack_cli.fields import (
    Field,
    build_value,
    issue_type_for,
    parse_field_flag,
    project_fields_from_schema,
)


def _schema_sample() -> list[dict]:
    return [
        {
            "$type": "EnumProjectCustomField",
            "field": {
                "name": "Priority",
                "fieldType": {"valueType": "enum", "isMultiValue": False},
            },
            "canBeEmpty": False,
            "emptyFieldText": "No Priority",
            "defaultValues": [{"name": "Normal"}],
            "bundle": {"values": [{"name": "Major"}, {"name": "Normal"}]},
        },
        {
            "$type": "StateProjectCustomField",
            "field": {
                "name": "State",
                "fieldType": {"valueType": "state", "isMultiValue": False},
            },
            "canBeEmpty": False,
            "emptyFieldText": "No State",
            "defaultValues": [{"name": "Submitted"}],
            "bundle": {"values": [{"name": "Open"}, {"name": "Submitted"}]},
        },
        {
            "$type": "UserProjectCustomField",
            "field": {
                "name": "Assignee",
                "fieldType": {"valueType": "user", "isMultiValue": False},
            },
            "canBeEmpty": True,
            "emptyFieldText": "Unassigned",
            "defaultValues": [],
            "bundle": {"values": [{"name": "Admin"}]},
        },
        {
            "$type": "VersionProjectCustomField",
            "field": {
                "name": "Fix versions",
                "fieldType": {"valueType": "version", "isMultiValue": True},
            },
            "canBeEmpty": True,
            "emptyFieldText": "Unscheduled",
            "defaultValues": [],
            "bundle": {"values": [{"name": "2026.1"}, {"name": "2026.2"}]},
        },
        {
            "$type": "PeriodProjectCustomField",
            "field": {
                "name": "Estimation",
                "fieldType": {"valueType": "period", "isMultiValue": False},
            },
            "canBeEmpty": True,
            "emptyFieldText": "No estimation",
            "defaultValues": [],
            "bundle": None,
        },
    ]


def test_project_fields_from_schema() -> None:
    schema = project_fields_from_schema(_schema_sample())
    assert set(schema) == {"Priority", "State", "Assignee", "Fix versions", "Estimation"}
    assert schema["Priority"].value_type == "enum"
    assert not schema["Priority"].multi
    assert schema["Priority"].can_be_empty is False
    assert schema["Priority"].defaults == ["Normal"]
    assert schema["Priority"].allowed == ["Major", "Normal"]


def test_issue_type_for_fields() -> None:
    assert (
        issue_type_for(Field("Priority", "enum", False, True, [], []))
        == "SingleEnumIssueCustomField"
    )
    assert issue_type_for(Field("State", "state", False, True, [], [])) == "StateIssueCustomField"
    assert (
        issue_type_for(Field("Assignee", "user", False, True, [], []))
        == "SingleUserIssueCustomField"
    )
    assert (
        issue_type_for(Field("Fix versions", "version", True, True, [], []))
        == "MultiVersionIssueCustomField"
    )
    assert (
        issue_type_for(Field("Estimation", "period", False, True, [], []))
        == "PeriodIssueCustomField"
    )


def test_build_value_single_enum() -> None:
    f = Field("Priority", "enum", False, True, [], ["Major", "Normal"])
    assert build_value(f, "Major") == {"name": "Major"}


def test_build_value_multi_version() -> None:
    f = Field("Fix versions", "version", True, True, [], ["2026.1", "2026.2"])
    assert build_value(f, "2026.1, 2026.2") == [{"name": "2026.1"}, {"name": "2026.2"}]


def test_build_value_user_uses_login() -> None:
    f = Field("Assignee", "user", False, True, [], [])
    assert build_value(f, "admin") == {"login": "admin"}


def test_build_value_rejects_period() -> None:
    f = Field("Estimation", "period", False, True, [], [])
    with pytest.raises(ValidationError, match="period"):
        build_value(f, "2h")


def test_build_value_validates_against_allowed_values() -> None:
    f = Field("Priority", "enum", False, True, [], ["Major", "Normal"])
    with pytest.raises(ValidationError, match="Critical"):
        build_value(f, "Critical")


def test_parse_field_flag() -> None:
    assert parse_field_flag("Target version=2026.2") == ("Target version", "2026.2")
    assert parse_field_flag("Subsystems=UI, Core") == ("Subsystems", "UI, Core")


def test_parse_field_flag_rejects_invalid() -> None:
    with pytest.raises(ValidationError, match="must contain an '='"):
        parse_field_flag("Target version")
