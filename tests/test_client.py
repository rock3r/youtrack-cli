"""Tests for youtrack_cli.client — frozen contract (docs/contracts.md)."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from youtrack_cli.client import Client
from youtrack_cli.config import Config
from youtrack_cli.errors import APIError, ExitCode

CFG = Config(base_url="http://localhost:8080", token="perm-test", me=None)


def test_get_returns_parsed_json(httpx_mock) -> None:
    httpx_mock.add_response(
        url="http://localhost:8080/api/users/me?fields=login",
        method="GET",
        json={"login": "admin"},
    )
    c = Client(CFG, sleep=lambda _s: None)
    assert c.get("/api/users/me", fields="login") == {"login": "admin"}


def test_get_sends_auth_accept_and_fields(httpx_mock) -> None:
    httpx_mock.add_response(
        url="http://localhost:8080/api/users/me?fields=login,fullName",
        method="GET",
        json={"login": "admin"},
    )
    c = Client(CFG, sleep=lambda _s: None)
    c.get("/api/users/me", fields="login,fullName")
    req = httpx_mock.get_requests()[0]
    assert req.headers["Authorization"] == "Bearer perm-test"
    assert req.headers["Accept"] == "application/json"
    # fields value is URL-encoded (spaces/commas)
    assert req.url.params["fields"] == "login,fullName"


def test_post_sends_content_type_and_body(httpx_mock) -> None:
    httpx_mock.add_response(
        url="http://localhost:8080/api/issues?fields=idReadable",
        method="POST",
        json={"idReadable": "JT-1"},
    )
    c = Client(CFG, sleep=lambda _s: None)
    res = c.post("/api/issues", json_body={"summary": "x"}, fields="idReadable")
    assert res == {"idReadable": "JT-1"}
    req = httpx_mock.get_requests()[0]
    assert req.headers["Content-Type"] == "application/json"


def test_non_2xx_raises_api_error(httpx_mock) -> None:
    httpx_mock.add_response(
        url="http://localhost:8080/api/issues",
        method="POST",
        status_code=403,
        json={"error_description": "No permission to create issue in project YouTrack"},
    )
    c = Client(CFG, sleep=lambda _s: None)
    with pytest.raises(APIError) as exc:
        c.post("/api/issues", json_body={})
    assert exc.value.exit_code == ExitCode.PERMISSION
    assert exc.value.status == 403
    assert "No permission" in exc.value.description


def test_404_maps_to_not_found(httpx_mock) -> None:
    httpx_mock.add_response(
        url="http://localhost:8080/api/issues/X", method="GET", status_code=404, json={}
    )
    c = Client(CFG, sleep=lambda _s: None)
    with pytest.raises(APIError) as exc:
        c.get("/api/issues/X")
    assert exc.value.exit_code == ExitCode.NOT_FOUND


def test_network_error_is_retryable_and_maps_to_api(httpx_mock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"), is_reusable=True)
    c = Client(CFG, sleep=lambda _s: None)
    with pytest.raises(APIError) as exc:
        c.get("/api/users/me")
    assert exc.value.status == 0
    assert exc.value.retryable is True
    assert exc.value.exit_code == ExitCode.API
    assert "Connection refused" in exc.value.description


def test_get_retries_5xx_once_then_succeeds(httpx_mock) -> None:
    httpx_mock.add_response(
        url="http://localhost:8080/api/users/me", method="GET", status_code=500, is_reusable=False
    )
    httpx_mock.add_response(
        url="http://localhost:8080/api/users/me",
        method="GET",
        status_code=200,
        json={"login": "admin"},
    )
    sleep = MagicMock()
    c = Client(CFG, sleep=sleep)
    assert c.get("/api/users/me") == {"login": "admin"}
    sleep.assert_called_once_with(0.5)


def test_post_not_retried_on_5xx(httpx_mock) -> None:
    httpx_mock.add_response(
        url="http://localhost:8080/api/issues", method="POST", status_code=500, json={}
    )
    sleep = MagicMock()
    c = Client(CFG, sleep=sleep)
    with pytest.raises(APIError) as exc:
        c.post("/api/issues", json_body={})
    assert exc.value.status == 500
    sleep.assert_not_called()


def test_empty_2xx_body_returns_none(httpx_mock) -> None:
    httpx_mock.add_response(
        url="http://localhost:8080/api/x", method="POST", status_code=200, text=""
    )
    c = Client(CFG, sleep=lambda _s: None)
    assert c.post("/api/x") is None


def test_default_timeouts_are_set() -> None:
    # the Client owns an httpx.Client with the frozen timeout profile
    c = Client(CFG, sleep=lambda _s: None)
    t = c.timeout
    assert t.connect == 10.0
    assert t.read == 60.0
    assert t.write == 30.0
    assert t.pool == 10.0
