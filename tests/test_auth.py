"""Tests for authentication, version, and config-file CLI paths (M4)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from youtrack_cli.cli.app import app

runner = CliRunner()


def _clear_env(monkeypatch) -> None:
    for k in ("YOUTRACK_TOKEN", "YOUTRACK_BASE_URL"):
        monkeypatch.delenv(k, raising=False)


def test_version_flag() -> None:
    res = runner.invoke(app, ["--version"])
    assert res.exit_code == 0
    assert "yt 0.1.0" in res.stdout


def test_version_suppresses_subcommand() -> None:
    res = runner.invoke(app, ["--version", "status"])
    assert res.exit_code == 0
    assert "yt 0.1.0" in res.stdout


def test_auth_login_writes_config(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    config = tmp_path / "config.toml"
    res = runner.invoke(
        app,
        ["--config", str(config), "auth", "login", "--base-url", "http://x.com", "--token", "tok"],
    )
    assert res.exit_code == 0
    assert config.exists()
    text = config.read_text()
    assert "http://x.com" in text
    assert "tok" in text
    assert (config.stat().st_mode & 0o777) == 0o600


def test_auth_login_uses_config_from_global_flag(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    config = tmp_path / "nested" / "config.toml"
    res = runner.invoke(
        app,
        [
            "--config",
            str(config),
            "auth",
            "login",
            "--base-url",
            "http://y.com",
            "--token",
            "tok2",
        ],
    )
    assert res.exit_code == 0
    assert config.exists()
    assert "http://y.com" in config.read_text()
