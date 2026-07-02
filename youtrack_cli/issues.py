"""Issue query composer, field helpers, and create/edit orchestration."""

from __future__ import annotations

import typing
from typing import Any

from youtrack_cli.client import Client
from youtrack_cli.errors import APIError, ValidationError
from youtrack_cli.fields import (
    Field,
    build_value,
    issue_type_for,
    parse_field_flag,
    project_fields_from_schema,
)

ISSUE_LIST_FIELDS = (
    "$type,idReadable,summary,updated,project(name),customFields(name,value(name),$type)"
)
ISSUE_SHOW_FIELDS = (
    "$type,idReadable,summary,description,created,updated,"
    "reporter(name),assignee(name),project(name),customFields(name,value(name),$type)"
)


# ---------------------------------------------------------------------------
# issue field helpers (schema-aware rendering support lives in fields.py)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# create issue
# ---------------------------------------------------------------------------


def build_create_body(
    client: Client,
    project: str,
    summary: str,
    *,
    description: str | None = None,
    issue_type: str | None = None,
    priority: str | None = None,
    state: str | None = None,
    assignee: str | None = None,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """Build the JSON body for ``POST /api/issues`` without sending it."""
    project_id = _project_id(client, project)
    schema = _project_fields(client, project)
    explicit = _collect_explicit(
        issue_type=issue_type,
        priority=priority,
        state=state,
        assignee=assignee,
        fields=fields,
    )
    custom_fields = _build_custom_fields(schema, explicit)

    body: dict[str, Any] = {
        "$type": "Issue",
        "project": {"$type": "Project", "id": project_id},
        "summary": summary,
    }
    if description:
        body["description"] = description
    if custom_fields:
        body["customFields"] = custom_fields
    return body


def create_issue(
    client: Client,
    project: str,
    summary: str,
    *,
    description: str | None = None,
    issue_type: str | None = None,
    priority: str | None = None,
    state: str | None = None,
    assignee: str | None = None,
    fields: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create a new issue in ``project`` using the direct ``POST /api/issues`` endpoint.

    Structured flags are translated into typed custom-field bodies. Period fields are
    rejected on creation (the server silently drops minutes). The server workflow is
    left to enforce required fields so the user gets a precise, field-level error.

    When ``dry_run`` is True, the request body is built and returned without sending it.
    """
    body = build_create_body(
        client,
        project,
        summary,
        description=description,
        issue_type=issue_type,
        priority=priority,
        state=state,
        assignee=assignee,
        fields=fields,
    )

    if dry_run:
        return body

    explicit = _collect_explicit(
        issue_type=issue_type,
        priority=priority,
        state=state,
        assignee=assignee,
        fields=fields,
    )
    try:
        return typing.cast(
            dict[str, Any], client.post("/api/issues", json_body=body, fields=ISSUE_SHOW_FIELDS)
        )
    except APIError as exc:
        # The server often returns a generic "Value is not allowed" when an assignee
        # is not eligible for the project. The error payload does not positively identify
        # which field failed, so we surface it with a contextual hint rather than retrying.
        if exc.description == "Value is not allowed" and "Assignee" in explicit:
            exc.description = (
                f"{exc.description} — the assignee '{explicit['Assignee']}' may not be "
                "eligible for this project. Try again without --assignee."
            )
        raise


def _collect_explicit(
    *,
    issue_type: str | None = None,
    priority: str | None = None,
    state: str | None = None,
    assignee: str | None = None,
    fields: list[str] | None = None,
) -> dict[str, str]:
    explicit: dict[str, str] = {}
    if issue_type:
        explicit["Type"] = issue_type
    if priority:
        explicit["Priority"] = priority
    if state:
        explicit["State"] = state
    if assignee:
        explicit["Assignee"] = assignee
    for flag in fields or []:
        name, value = parse_field_flag(flag)
        explicit[name] = value
    return explicit


def _period_minutes(value: str) -> int:
    """Convert a period string like '2h' or '120m' into minutes."""
    value = value.strip().lower()
    if value.endswith("h"):
        return int(value[:-1]) * 60
    if value.endswith("m"):
        return int(value[:-1])
    return int(value)


def _send_command(client: Client, issue_id: str, query: str) -> Any:
    """Apply a YouTrack command to an existing issue."""
    return client.post(
        "/api/commands",
        json_body={
            "$type": "CommandList",
            "query": query,
            "issues": [{"$type": "Issue", "idReadable": issue_id}],
        },
    )


# ---------------------------------------------------------------------------
# edit / comment / link
# ---------------------------------------------------------------------------


def edit_issue(  # noqa: PLR0912 — branching mirrors the CLI flag surface
    client: Client,
    issue_id: str,
    *,
    summary: str | None = None,
    description: str | None = None,
    issue_type: str | None = None,
    priority: str | None = None,
    state: str | None = None,
    assignee: str | None = None,
    fields: list[str] | None = None,
    command: str | None = None,
) -> None:
    """Edit an existing issue.

    Summary and description are updated via a direct ``POST /api/issues/{id}`` because
    the command language does not support them. Other structured flags are translated
    into a YouTrack command query. Period fields are applied via a direct typed update.
    """
    # Only resolve the project if we need schema for period fields.
    schema: dict[str, Field] | None = None
    if fields:
        issue = client.get(f"/api/issues/{issue_id}", fields="project(shortName)")
        project = (issue.get("project") or {}).get("shortName")
        if not project:
            raise ValidationError(f"Could not resolve project for issue {issue_id}")
        schema = _project_fields(client, project)

    command_parts: list[str] = []
    if command:
        command_parts.append(command)
    if issue_type:
        command_parts.append(f"Type: {issue_type}")
    if priority:
        command_parts.append(f"Priority: {priority}")
    if state:
        command_parts.append(f"State: {state}")
    if assignee:
        command_parts.append(f"Assignee: {assignee}")

    direct_body: dict[str, Any] = {"$type": "Issue"}
    if summary:
        direct_body["summary"] = summary
    if description:
        direct_body["description"] = description

    direct_fields: list[dict[str, Any]] = []
    if fields and schema:
        for flag in fields:
            name, raw = parse_field_flag(flag)
            field = schema.get(name)
            if field and field.value_type == "period":
                direct_fields.append(
                    {
                        "name": name,
                        "$type": "PeriodIssueCustomField",
                        "value": {"minutes": _period_minutes(raw)},
                    }
                )
            else:
                command_parts.append(f"{name}: {raw}")

    if direct_fields:
        direct_body["customFields"] = direct_fields

    if command_parts:
        _send_command(client, issue_id, " ".join(command_parts))

    if len(direct_body) > 1:
        client.post(
            f"/api/issues/{issue_id}",
            json_body=direct_body,
            fields=ISSUE_SHOW_FIELDS,
        )


def add_comment(client: Client, issue_id: str, text: str) -> None:
    """Add a comment to an issue using the dedicated comments endpoint."""
    client.post(
        f"/api/issues/{issue_id}/comments",
        json_body={"$type": "IssueComment", "text": text},
    )


_LINK_TYPES = {
    "relates_to": "relates to",
    "duplicates": "duplicates",
    "depends_on": "depends on",
    "is_required_for": "is required for",
    "is_dependent_on": "is dependent on",
    "parent_for": "parent for",
    "subtask_of": "subtask of",
}


def link_issue(client: Client, issue_id: str, link_type: str, target: str) -> None:
    """Create a link between two issues using the command language."""
    command = _LINK_TYPES.get(link_type, link_type.replace("_", " "))
    _send_command(client, issue_id, f"{command} {target}")


def _project_id(client: Client, project: str) -> str:
    data = client.get(f"/api/admin/projects/{project}", fields="id")
    if not isinstance(data, dict) or "id" not in data:
        raise ValidationError(f"Project '{project}' not found or not accessible")
    return str(data["id"])


def _project_fields(client: Client, project: str) -> dict[str, Field]:
    raw = client.get(
        f"/api/admin/projects/{project}/customFields",
        fields="$type,field(name,fieldType(isMultiValue,valueType)),canBeEmpty,emptyFieldText,defaultValues(name),bundle(values(name))",
    )
    if not isinstance(raw, list):
        raise ValidationError(f"Could not read custom fields for project '{project}'")
    return project_fields_from_schema(raw)


def _build_custom_fields(
    schema: dict[str, Field], explicit: dict[str, str]
) -> list[dict[str, Any]]:
    custom_fields: list[dict[str, Any]] = []
    for name, raw_value in explicit.items():
        field = schema.get(name)
        if not field:
            raise ValidationError(f"Unknown field '{name}' in this project")
        value = build_value(field, raw_value)
        custom_fields.append(
            {
                "name": name,
                "$type": issue_type_for(field),
                "value": value,
            }
        )
    return custom_fields
