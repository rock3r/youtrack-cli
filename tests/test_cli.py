"""Tests for the typer CLI (yt status) — M0 contract (docs/contracts.md)."""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path

from typer.testing import CliRunner

from youtrack_cli.cli.app import app
from youtrack_cli.onepassword import OnePasswordError

runner = CliRunner()


def _clear_env(monkeypatch) -> None:
    for k in ("YOUTRACK_TOKEN", "YOUTRACK_BASE_URL"):
        monkeypatch.delenv(k, raising=False)


def test_status_success_text(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)  # no .env here
    httpx_mock.add_response(
        url="http://localhost:8080/api/users/me?fields=login,fullName",
        method="GET",
        json={"login": "admin", "fullName": "Admin"},
    )
    res = runner.invoke(
        app, ["--token", "perm-test", "--base-url", "http://localhost:8080", "status"]
    )
    assert res.exit_code == 0
    assert "admin" in res.stdout


def test_status_success_json(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(
        url="http://localhost:8080/api/users/me?fields=login,fullName",
        method="GET",
        json={"login": "admin", "fullName": "Admin"},
    )
    res = runner.invoke(
        app,
        [
            "--output",
            "json",
            "--token",
            "perm-test",
            "--base-url",
            "http://localhost:8080",
            "status",
        ],
    )
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["ok"] is True
    assert payload["data"]["login"] == "admin"


def test_status_quiet_suppresses_ok_line(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(
        url="http://localhost:8080/api/users/me?fields=login,fullName",
        method="GET",
        json={"login": "admin"},
    )
    res = runner.invoke(
        app, ["--quiet", "--token", "perm-test", "--base-url", "http://localhost:8080", "status"]
    )
    assert res.exit_code == 0
    assert res.stdout.strip() == ""


def test_status_401_maps_to_permission_exit(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(
        url="http://localhost:8080/api/users/me?fields=login,fullName",
        method="GET",
        status_code=401,
        json={"error_description": "Invalid token"},
    )
    res = runner.invoke(app, ["--token", "bad", "--base-url", "http://localhost:8080", "status"])
    assert res.exit_code == 5  # PERMISSION


def test_status_connection_error_maps_to_api_exit(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_exception(Exception("boom"), is_reusable=True)  # any transport failure
    res = runner.invoke(
        app, ["--token", "perm-test", "--base-url", "http://localhost:8080", "status"]
    )
    assert res.exit_code == 1  # API


def test_status_no_token_maps_to_usage_exit(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)  # cwd has no .env
    res = runner.invoke(app, ["status", "--base-url", "http://localhost:8080"])
    assert res.exit_code == 2  # USAGE


def test_status_401_json_envelope(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(
        url="http://localhost:8080/api/users/me?fields=login,fullName",
        method="GET",
        status_code=401,
        json={"error_description": "Invalid token"},
    )
    res = runner.invoke(
        app, ["--output", "json", "--token", "bad", "--base-url", "http://localhost:8080", "status"]
    )
    assert res.exit_code == 5
    expected = (
        '{"error": {"code": "PERMISSION", "exit_code": 5, "field": null, '
        '"message": "Invalid token", "request": {"method": "GET", "path": "/api/users/me"}, '
        '"rule_name": null, "status": 401, "type": null, "workflow_type": null}, "ok": false}\n'
    )
    assert res.stdout == expected


def test_op_token_global_flag_used(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    captured: dict[str, str] = {}

    def _fake_fetch_token(*, vault: str, item: str, field: str) -> str:
        captured["vault"] = vault
        captured["item"] = item
        captured["field"] = field
        return "op-token"

    monkeypatch.setattr("youtrack_cli.cli.app.fetch_token", _fake_fetch_token)
    httpx_mock.add_response(
        url="http://localhost:8080/api/users/me?fields=login,fullName",
        method="GET",
        json={"login": "admin", "fullName": "Admin"},
    )
    res = runner.invoke(
        app,
        [
            "--op-vault",
            "Engineering",
            "--op-item",
            "YouTrack",
            "--op-field",
            "token",
            "--base-url",
            "http://localhost:8080",
            "status",
        ],
    )
    assert res.exit_code == 0, res.output
    assert captured == {"vault": "Engineering", "item": "YouTrack", "field": "token"}
    request = httpx_mock.get_requests()[0]
    assert "Bearer op-token" in request.headers.get("Authorization", "")


def test_op_token_env_used(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("YOUTRACK_OP_VAULT", "Engineering")
    monkeypatch.setenv("YOUTRACK_OP_ITEM", "YouTrack")
    monkeypatch.setenv("YOUTRACK_OP_FIELD", "token")
    captured: dict[str, str] = {}

    def _fake_fetch_token(*, vault: str, item: str, field: str) -> str:
        captured["vault"] = vault
        captured["item"] = item
        captured["field"] = field
        return "op-token-env"

    monkeypatch.setattr("youtrack_cli.cli.app.fetch_token", _fake_fetch_token)
    httpx_mock.add_response(
        url="http://localhost:8080/api/users/me?fields=login,fullName",
        method="GET",
        json={"login": "admin", "fullName": "Admin"},
    )
    res = runner.invoke(app, ["--base-url", "http://localhost:8080", "status"])
    assert res.exit_code == 0, res.output
    assert captured == {"vault": "Engineering", "item": "YouTrack", "field": "token"}
    request = httpx_mock.get_requests()[0]
    assert "Bearer op-token-env" in request.headers.get("Authorization", "")


def test_op_error_surfaces_as_validation_error(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)

    def _fake_fetch_token(*, vault: str, item: str, field: str) -> str:
        raise OnePasswordError("1Password CLI ('op') not found on PATH.")

    monkeypatch.setattr("youtrack_cli.cli.app.fetch_token", _fake_fetch_token)
    res = runner.invoke(
        app, ["--op-item", "YouTrack", "--base-url", "http://localhost:8080", "status"]
    )
    assert res.exit_code == 3  # VALIDATION


# ---- M1: yt issues and yt show ----


def test_issues_default_query(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(
        method="GET",
        json=[
            {
                "idReadable": "JT-1",
                "summary": "First issue",
                "project": {"name": "YouTrack"},
                "updated": 1710000000000,
                "customFields": [
                    {"name": "State", "value": {"name": "Open"}},
                    {"name": "Priority", "value": {"name": "Major"}},
                ],
            }
        ],
    )
    res = runner.invoke(
        app, ["--token", "perm-test", "--base-url", "http://localhost:8080", "issues"]
    )
    assert res.exit_code == 0
    assert "JT-1" in res.stdout
    assert "First issue" in res.stdout
    req = httpx_mock.get_requests()[0]
    assert req.url.params["query"] == "for: me #Unresolved"
    assert req.url.params["$top"] == "20"


def test_issues_all_flag(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(method="GET", json=[])
    res = runner.invoke(
        app, ["--token", "perm-test", "--base-url", "http://localhost:8080", "issues", "--all"]
    )
    assert res.exit_code == 0
    req = httpx_mock.get_requests()[0]
    assert req.url.params["query"] == ""


def test_issues_json(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(method="GET", json=[])
    res = runner.invoke(
        app,
        [
            "--output",
            "json",
            "--token",
            "perm-test",
            "--base-url",
            "http://localhost:8080",
            "issues",
        ],
    )
    assert res.exit_code == 0
    assert res.stdout == '{"data": [], "ok": true}\n'


def test_issues_offset_passed_to_api(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(method="GET", json=[])
    res = runner.invoke(
        app,
        [
            "--token",
            "perm-test",
            "--base-url",
            "http://localhost:8080",
            "issues",
            "--offset",
            "10",
        ],
    )
    assert res.exit_code == 0
    request = httpx_mock.get_requests()[0]
    query = urllib.parse.unquote(request.url.query.decode())
    assert "$skip=10" in query
    assert "$top=20" in query


def test_show_success(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(
        method="GET",
        json={
            "idReadable": "JT-1",
            "summary": "The first issue",
            "project": {"name": "YouTrack"},
            "customFields": [{"name": "State", "value": {"name": "Open"}}],
        },
    )
    res = runner.invoke(
        app, ["--token", "perm-test", "--base-url", "http://localhost:8080", "show", "JT-1"]
    )
    assert res.exit_code == 0
    assert "JT-1" in res.stdout
    assert "The first issue" in res.stdout


def test_show_not_found(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(
        method="GET",
        status_code=404,
        json={},
    )
    res = runner.invoke(
        app, ["--token", "perm-test", "--base-url", "http://localhost:8080", "show", "JT-999"]
    )
    assert res.exit_code == 4  # NOT_FOUND


# ---- M2: yt create ----


def _demo_schema() -> list[dict]:
    return [
        {
            "$type": "EnumProjectCustomField",
            "field": {
                "name": "Type",
                "fieldType": {"valueType": "enum", "isMultiValue": False},
            },
            "canBeEmpty": False,
            "emptyFieldText": "No Type",
            "defaultValues": [{"name": "Bug"}],
            "bundle": {"values": [{"name": "Bug"}, {"name": "Task"}]},
        },
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
            "bundle": {"values": [{"name": "Submitted"}, {"name": "Open"}]},
        },
        {
            "$type": "VersionProjectCustomField",
            "field": {
                "name": "Target version",
                "fieldType": {"valueType": "version", "isMultiValue": False},
            },
            "canBeEmpty": False,
            "emptyFieldText": "No version",
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


def _create_mocks(httpx_mock) -> None:
    httpx_mock.add_response(method="GET", json={"id": "0-99", "$type": "Project"})
    httpx_mock.add_response(method="GET", json=_demo_schema())
    httpx_mock.add_response(
        method="POST",
        json={
            "idReadable": "DEMO-42",
            "summary": "A new issue",
            "project": {"name": "Demo"},
            "customFields": [{"name": "State", "value": {"name": "Submitted"}}],
        },
    )


def test_create_success(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    _create_mocks(httpx_mock)
    res = runner.invoke(
        app,
        [
            "--token",
            "perm-test",
            "--base-url",
            "http://localhost:8080",
            "create",
            "DEMO",
            "A new issue",
            "--type",
            "Bug",
            "--priority",
            "Major",
            "--field",
            "Target version=2026.1",
        ],
    )
    assert res.exit_code == 0
    assert "DEMO-42" in res.stdout
    requests = httpx_mock.get_requests()
    assert requests[2].method == "POST"
    body = json.loads(requests[2].content)
    assert body["summary"] == "A new issue"
    assert body["project"]["id"] == "0-99"
    assert any(
        cf["name"] == "Priority" and cf["value"]["name"] == "Major" for cf in body["customFields"]
    )


def test_create_dry_run(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(method="GET", json={"id": "0-99", "$type": "Project"})
    httpx_mock.add_response(method="GET", json=_demo_schema())
    res = runner.invoke(
        app,
        [
            "--token",
            "perm-test",
            "--base-url",
            "http://localhost:8080",
            "create",
            "DEMO",
            "A new issue",
            "--type",
            "Bug",
            "--dry-run",
        ],
    )
    assert res.exit_code == 0
    assert "customFields" in res.stdout
    assert len([r for r in httpx_mock.get_requests() if r.method == "POST"]) == 0


def test_create_rejects_period_field(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(method="GET", json={"id": "0-99", "$type": "Project"})
    httpx_mock.add_response(method="GET", json=_demo_schema())
    res = runner.invoke(
        app,
        [
            "--token",
            "perm-test",
            "--base-url",
            "http://localhost:8080",
            "create",
            "DEMO",
            "A new issue",
            "--field",
            "Estimation=2h",
        ],
    )
    assert res.exit_code == 3  # VALIDATION


def test_create_rejects_period_field_json_envelope(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(method="GET", json={"id": "0-99", "$type": "Project"})
    httpx_mock.add_response(method="GET", json=_demo_schema())
    res = runner.invoke(
        app,
        [
            "--output",
            "json",
            "--token",
            "perm-test",
            "--base-url",
            "http://localhost:8080",
            "create",
            "DEMO",
            "A new issue",
            "--field",
            "Estimation=2h",
        ],
    )
    assert res.exit_code == 3
    payload = json.loads(res.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION"
    assert payload["error"]["exit_code"] == 3


def test_create_rejects_unknown_field(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(method="GET", json={"id": "0-99", "$type": "Project"})
    httpx_mock.add_response(method="GET", json=_demo_schema())
    res = runner.invoke(
        app,
        [
            "--token",
            "perm-test",
            "--base-url",
            "http://localhost:8080",
            "create",
            "DEMO",
            "A new issue",
            "--field",
            "Mystery=value",
        ],
    )
    assert res.exit_code == 3  # VALIDATION


def test_create_workflow_required_field_error(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(method="GET", json={"id": "0-99", "$type": "Project"})
    httpx_mock.add_response(method="GET", json=_demo_schema())
    httpx_mock.add_response(
        method="POST",
        status_code=400,
        json={
            "error": "Field required",
            "error_description": "Target version is required",
            "error_field": "Target version",
            "error_type": "workflow",
            "error_workflow_type": "require",
        },
    )
    res = runner.invoke(
        app,
        [
            "--token",
            "perm-test",
            "--base-url",
            "http://localhost:8080",
            "create",
            "DEMO",
            "Missing target version",
            "--type",
            "Bug",
        ],
    )
    assert res.exit_code == 6  # WORKFLOW
