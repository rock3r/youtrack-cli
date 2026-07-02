"""Tests for edit, comment, and link commands (M3)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from youtrack_cli.cli.app import app

runner = CliRunner()


def _clear_env(monkeypatch) -> None:
    for k in ("YOUTRACK_TOKEN", "YOUTRACK_BASE_URL"):
        monkeypatch.delenv(k, raising=False)


def _schema_with_period() -> list[dict]:
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


def test_comment_success(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(
        method="POST",
        json={"$type": "IssueComment", "text": "Looks good to me"},
    )
    res = runner.invoke(
        app,
        [
            "--token",
            "perm-test",
            "--base-url",
            "http://localhost:8080",
            "comment",
            "JT-1",
            "Looks good to me",
        ],
    )
    assert res.exit_code == 0
    assert "JT-1" in res.stdout
    req = httpx_mock.get_requests()[0]
    assert "/api/issues/JT-1/comments" in str(req.url)
    body = json.loads(req.content)
    assert body["text"] == "Looks good to me"
    assert body["$type"] == "IssueComment"


def test_edit_summary_and_state(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    # state -> command; summary -> direct issue update
    httpx_mock.add_response(
        method="POST",
        json={"$type": "CommandList"},
    )
    httpx_mock.add_response(
        method="POST",
        json={"idReadable": "JT-1", "summary": "New summary"},
    )
    res = runner.invoke(
        app,
        [
            "--token",
            "perm-test",
            "--base-url",
            "http://localhost:8080",
            "edit",
            "JT-1",
            "--summary",
            "New summary",
            "--state",
            "Open",
        ],
    )
    assert res.exit_code == 0
    requests = httpx_mock.get_requests()
    command_req = next(r for r in requests if r.url.path == "/api/commands")
    direct_req = next(r for r in requests if "/api/issues/JT-1" in str(r.url))
    command_body = json.loads(command_req.content)
    assert "State: Open" in command_body["query"]
    direct_body = json.loads(direct_req.content)
    assert direct_body["summary"] == "New summary"


def test_edit_with_raw_command(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(
        method="POST",
        json={"$type": "CommandList"},
    )
    res = runner.invoke(
        app,
        [
            "--token",
            "perm-test",
            "--base-url",
            "http://localhost:8080",
            "edit",
            "JT-1",
            "--command",
            "priority Major",
        ],
    )
    assert res.exit_code == 0
    req = httpx_mock.get_requests()[0]
    body = json.loads(req.content)
    assert body["query"] == "priority Major"


def test_edit_period_field_uses_direct_post(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    # issue → project
    httpx_mock.add_response(
        method="GET",
        json={"project": {"shortName": "JT", "$type": "Project"}},
    )
    # schema
    httpx_mock.add_response(method="GET", json=_schema_with_period())
    # direct update
    httpx_mock.add_response(
        method="POST",
        json={"idReadable": "JT-1", "summary": "x"},
    )
    res = runner.invoke(
        app,
        [
            "--token",
            "perm-test",
            "--base-url",
            "http://localhost:8080",
            "edit",
            "JT-1",
            "--field",
            "Estimation=120m",
        ],
    )
    assert res.exit_code == 0
    requests = httpx_mock.get_requests()
    direct = [r for r in requests if r.method == "POST" and "/api/issues/JT-1" in str(r.url)]
    assert len(direct) == 1
    body = json.loads(direct[0].content)
    assert body["customFields"][0]["name"] == "Estimation"
    assert body["customFields"][0]["value"]["minutes"] == 120


def test_link_success(httpx_mock, monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    httpx_mock.add_response(
        method="POST",
        json={"$type": "CommandList"},
    )
    res = runner.invoke(
        app,
        [
            "--token",
            "perm-test",
            "--base-url",
            "http://localhost:8080",
            "link",
            "JT-1",
            "relates_to",
            "JT-2",
        ],
    )
    assert res.exit_code == 0
    req = httpx_mock.get_requests()[0]
    body = json.loads(req.content)
    assert body["query"] == "relates to JT-2"
    assert body["issues"][0]["idReadable"] == "JT-1"
