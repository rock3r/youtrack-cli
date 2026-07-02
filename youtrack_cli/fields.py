"""Project custom-field schema resolution and typed value builders for create/edit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from youtrack_cli.errors import ValidationError


@dataclass(frozen=True)
class Field:
    """Resolved schema for a single project custom field."""

    name: str
    value_type: str
    multi: bool
    can_be_empty: bool
    defaults: list[str]
    allowed: list[str]


def project_fields_from_schema(raw: list[dict[str, Any]]) -> dict[str, Field]:
    """Parse a list of project custom-field entities into a name-indexed Field map."""
    out: dict[str, Field] = {}
    for entry in raw:
        field = entry.get("field", {})
        field_name = field.get("name")
        if not field_name:
            continue
        field_type = field.get("fieldType", {}) or {}
        value_type = field_type.get("valueType") or ""
        multi = bool(field_type.get("isMultiValue"))
        defaults = [v.get("name") for v in entry.get("defaultValues", []) if v.get("name")]
        bundle = entry.get("bundle") or {}
        allowed = [v.get("name") for v in bundle.get("values", []) if v.get("name")]
        out[field_name] = Field(
            name=field_name,
            value_type=value_type,
            multi=multi,
            can_be_empty=bool(entry.get("canBeEmpty")),
            defaults=defaults,
            allowed=allowed,
        )
    return out


def issue_type_for(field: Field) -> str:
    """Map a resolved field to the issue-side custom-field $type."""
    if field.value_type == "period":
        return "PeriodIssueCustomField"
    if field.value_type == "state":
        return "StateIssueCustomField"
    cardinality = "Multi" if field.multi else "Single"
    base = {
        "enum": "Enum",
        "ownedField": "Owned",
        "version": "Version",
        "build": "Build",
        "user": "User",
    }.get(field.value_type)
    if not base:
        raise ValidationError(
            f"Unsupported field value type '{field.value_type}' for '{field.name}'"
        )
    return f"{cardinality}{base}IssueCustomField"


def build_value(field: Field, raw: str) -> Any:
    """Build the typed value payload for a custom field from a string input."""
    if field.value_type == "period":
        raise ValidationError(
            f"Field '{field.name}' is a period field; set it after creation with `yt edit`"
        )

    parts = [p.strip() for p in raw.split(",") if p.strip()] if field.multi else [raw.strip()]

    if not parts:
        raise ValidationError(f"Empty value for field '{field.name}'")

    if field.allowed and field.value_type != "user":
        for part in parts:
            if part not in field.allowed:
                raise ValidationError(f"Value '{part}' is not allowed for field '{field.name}'")

    values: list[dict[str, Any]] = []
    for part in parts:
        if field.value_type == "user":
            values.append({"login": part})
        else:
            values.append({"name": part})

    return values if field.multi else values[0]


def parse_field_flag(flag: str) -> tuple[str, str]:
    """Parse a ``--field Name=value`` string."""
    if "=" not in flag:
        raise ValidationError(f"Field flag must contain an '=' character: {flag!r}")
    name, value = flag.split("=", 1)
    return name.strip(), value.strip()


def field_value(issue: dict[str, Any], name: str) -> str:
    """Return the human-readable string for a named custom field on an issue."""
    for cf in issue.get("customFields") or []:
        if cf.get("name") == name:
            value = cf.get("value")
            if value is None:
                return ""
            if isinstance(value, list):
                return ", ".join(
                    v.get("name") or v.get("login") or str(v) for v in value if v is not None
                )
            if isinstance(value, dict):
                return value.get("login") or value.get("name") or value.get("text") or ""
            return str(value)
    return ""
