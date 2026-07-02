"""Tests for the 1Password CLI integration."""

from __future__ import annotations

import json
import subprocess

import pytest

from youtrack_cli.onepassword import OnePasswordError, clear_cache, fetch_token


@pytest.fixture(autouse=True)
def _clear_op_cache() -> None:
    clear_cache()


def test_fetch_token_op_not_found(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _cmd: None)
    with pytest.raises(OnePasswordError, match="not found on PATH"):
        fetch_token("vault", "item")


def test_fetch_token_empty_vault_or_item() -> None:
    with pytest.raises(OnePasswordError, match="vault is required"):
        fetch_token("", "item")
    with pytest.raises(OnePasswordError, match="item is required"):
        fetch_token("vault", "")


def test_fetch_token_timeout(monkeypatch) -> None:
    def _raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("op", 30)

    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/op")
    monkeypatch.setattr("subprocess.run", _raise_timeout)
    with pytest.raises(OnePasswordError, match="timed out"):
        fetch_token("vault", "item")


def test_fetch_token_op_error(monkeypatch) -> None:
    def _bad_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="[ERROR] 2026/07/02: item not found",
        )

    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/op")
    monkeypatch.setattr("subprocess.run", _bad_run)
    with pytest.raises(OnePasswordError, match="item not found"):
        fetch_token("vault", "item")


def test_fetch_token_invalid_json(monkeypatch) -> None:
    def _bad_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="not-json",
            stderr="",
        )

    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/op")
    monkeypatch.setattr("subprocess.run", _bad_run)
    with pytest.raises(OnePasswordError, match="invalid JSON"):
        fetch_token("vault", "item")


def test_fetch_token_missing_field(monkeypatch) -> None:
    def _run(*_args, **_kwargs):
        data = {"fields": [{"id": "username", "label": "username", "value": "alice"}]}
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(data),
            stderr="",
        )

    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/op")
    monkeypatch.setattr("subprocess.run", _run)
    with pytest.raises(OnePasswordError, match="Field 'password' not found"):
        fetch_token("vault", "item")


def test_fetch_token_success(monkeypatch) -> None:
    def _run(*_args, **_kwargs):
        data = {
            "fields": [
                {"id": "username", "label": "username", "value": "alice"},
                {"id": "password", "label": "password", "value": "secret-token"},
            ]
        }
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(data),
            stderr="",
        )

    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/op")
    monkeypatch.setattr("subprocess.run", _run)
    assert fetch_token("vault", "item") == "secret-token"


def test_fetch_token_caches_result(monkeypatch) -> None:
    calls = []

    def _run(*_args, **_kwargs):
        calls.append(1)
        data = {"fields": [{"id": "password", "label": "password", "value": "cached"}]}
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(data),
            stderr="",
        )

    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/op")
    monkeypatch.setattr("subprocess.run", _run)
    assert fetch_token("vault", "item") == "cached"
    assert fetch_token("vault", "item") == "cached"
    assert len(calls) == 1
