"""Tests for youtrack_cli.config — frozen contract (docs/contracts.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from youtrack_cli.config import Config, ConfigError, resolve, write_config


def write_dotenv(path: Path, content: str) -> None:
    """Write a .env file."""
    path.write_text(content)


class TestPrecedence:
    def test_flag_overrides_env(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "YOUTRACK_TOKEN=from-dotenv\n")
        cfg = resolve(
            base_url="https://flag.example.com",
            token="from-flag",
            env={"YOUTRACK_BASE_URL": "https://env.example.com", "YOUTRACK_TOKEN": "from-env"},
            dotenv_path=str(dotenv),
        )
        assert cfg.base_url == "https://flag.example.com"
        assert cfg.token == "from-flag"

    def test_env_used_when_no_flag(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "")
        cfg = resolve(
            env={"YOUTRACK_BASE_URL": "https://env.example.com", "YOUTRACK_TOKEN": "env-tok"},
            dotenv_path=str(dotenv),
        )
        assert cfg.base_url == "https://env.example.com"
        assert cfg.token == "env-tok"

    def test_dotenv_used_when_no_env_no_flag(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "YOUTRACK_BASE_URL=https://dot.example.com\nYOUTRACK_TOKEN=dot-tok\n")
        cfg = resolve(env={}, dotenv_path=str(dotenv))
        assert cfg.base_url == "https://dot.example.com"
        assert cfg.token == "dot-tok"

    def test_per_key_mixed_env_base_url_and_dotenv_token(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "YOUTRACK_TOKEN=dot-tok\n")
        cfg = resolve(
            env={"YOUTRACK_BASE_URL": "https://env.example.com"},
            dotenv_path=str(dotenv),
        )
        assert cfg.base_url == "https://env.example.com"
        assert cfg.token == "dot-tok"


class TestDefaultsAndNormalization:
    def test_base_url_defaults_to_localhost(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "YOUTRACK_TOKEN=tok\n")
        cfg = resolve(env={}, dotenv_path=str(dotenv))
        assert cfg.base_url == "http://localhost:8080"

    def test_base_url_trailing_slash_stripped(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "YOUTRACK_TOKEN=tok\n")
        cfg = resolve(
            base_url="https://x.example.com/",
            token="tok",
            env={},
            dotenv_path=str(dotenv),
        )
        assert cfg.base_url == "https://x.example.com"

    def test_base_url_adds_https_scheme_when_missing(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "YOUTRACK_TOKEN=tok\n")
        cfg = resolve(base_url="youtrack.example.com", token="tok", env={}, dotenv_path=str(dotenv))
        assert cfg.base_url == "https://youtrack.example.com"

    def test_localhost_default_keeps_http_scheme(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "YOUTRACK_TOKEN=tok\n")
        cfg = resolve(env={"YOUTRACK_BASE_URL": "http://localhost:1234/"}, dotenv_path=str(dotenv))
        assert cfg.base_url == "http://localhost:1234"


class TestTokenRequired:
    def test_missing_token_raises_config_error(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "")
        with pytest.raises(ConfigError) as exc:
            resolve(env={}, dotenv_path=str(dotenv))
        msg = str(exc.value)
        assert "youtrack-cli: not configured" in msg
        assert "YOUTRACK_TOKEN" in msg
        assert "--token" in msg

    def test_empty_token_flag_does_not_fall_through(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "YOUTRACK_TOKEN=should-not-be-used\n")
        with pytest.raises(ConfigError):
            resolve(
                token="",
                env={"YOUTRACK_TOKEN": "should-not-be-used-either"},
                dotenv_path=str(dotenv),
            )


class TestDotenvParsing:
    def test_ignores_comments_and_blanks(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "\n# a comment\n\nYOUTRACK_TOKEN=real-tok\n  # indented comment\n")
        cfg = resolve(env={}, dotenv_path=str(dotenv))
        assert cfg.token == "real-tok"

    def test_no_shell_expansion(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "YOUTRACK_TOKEN=$HOME-literal\n")
        cfg = resolve(env={}, dotenv_path=str(dotenv))
        assert cfg.token == "$HOME-literal"

    def test_missing_dotenv_file_is_ok(self, tmp_path: Path) -> None:
        cfg = resolve(token="tok", env={}, dotenv_path=str(tmp_path / "nope.env"))
        assert cfg.token == "tok"


class TestConfigShape:
    def test_me_is_none_initially(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "YOUTRACK_TOKEN=tok\n")
        cfg = resolve(env={}, dotenv_path=str(dotenv))
        assert isinstance(cfg, Config)
        assert cfg.me is None


class TestConfigFile:
    def test_config_file_read_when_no_env_or_dotenv(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        config.write_text('base_url = "https://config.example.com"\ntoken = "config-tok"\n')
        cfg = resolve(env={}, dotenv_path=str(tmp_path / "nope.env"), config_path=str(config))
        assert cfg.base_url == "https://config.example.com"
        assert cfg.token == "config-tok"

    def test_env_wins_over_config_file(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        config.write_text('base_url = "https://config.example.com"\ntoken = "config-tok"\n')
        cfg = resolve(
            env={"YOUTRACK_TOKEN": "env-tok", "YOUTRACK_BASE_URL": "https://env.example.com"},
            dotenv_path=str(tmp_path / "nope.env"),
            config_path=str(config),
        )
        assert cfg.base_url == "https://env.example.com"
        assert cfg.token == "env-tok"

    def test_dotenv_wins_over_config_file(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "YOUTRACK_TOKEN=dot-tok\n")
        config = tmp_path / "config.toml"
        config.write_text('token = "config-tok"\n')
        cfg = resolve(env={}, dotenv_path=str(dotenv), config_path=str(config))
        assert cfg.token == "dot-tok"

    def test_write_config_creates_file_with_restricted_perms(self, tmp_path: Path) -> None:
        config = tmp_path / "youtrack-cli" / "config.toml"
        returned = write_config("http://localhost:8080", "secret", config)
        assert returned == config
        assert config.read_text() == "base_url = 'http://localhost:8080'\ntoken = 'secret'\n"
        assert (config.stat().st_mode & 0o777) == 0o600

    def test_write_config_tightens_existing_permissive_file(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        config.write_text('token = "old"\n')
        config.chmod(0o644)
        returned = write_config("http://localhost:8080", "new-secret", config)
        assert returned == config
        assert (config.stat().st_mode & 0o777) == 0o600

    def test_missing_config_file_is_ok(self, tmp_path: Path) -> None:
        config = tmp_path / "missing.toml"
        with pytest.raises(ConfigError) as exc:
            resolve(env={}, dotenv_path=str(tmp_path / "nope.env"), config_path=str(config))
        assert "YOUTRACK_TOKEN" in str(exc.value)


class TestOnePasswordPrecedence:
    def test_flag_token_wins_over_op(self, tmp_path: Path) -> None:
        def _should_not_call() -> str:
            raise AssertionError("op_token should not be called when --token is set")

        cfg = resolve(
            token="flag-tok",
            env={"YOUTRACK_OP_ITEM": "YouTrack"},
            dotenv_path=str(tmp_path / "nope.env"),
            op_token=_should_not_call,
        )
        assert cfg.token == "flag-tok"

    def test_env_token_wins_over_op(self, tmp_path: Path) -> None:
        def _should_not_call() -> str:
            raise AssertionError("op_token should not be called when env token is set")

        cfg = resolve(
            env={"YOUTRACK_TOKEN": "env-tok", "YOUTRACK_OP_ITEM": "YouTrack"},
            dotenv_path=str(tmp_path / "nope.env"),
            op_token=_should_not_call,
        )
        assert cfg.token == "env-tok"

    def test_dotenv_token_wins_over_op(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "YOUTRACK_TOKEN=dot-tok\n")

        def _should_not_call() -> str:
            raise AssertionError("op_token should not be called when .env token is set")

        cfg = resolve(
            env={"YOUTRACK_OP_ITEM": "YouTrack"},
            dotenv_path=str(dotenv),
            op_token=_should_not_call,
        )
        assert cfg.token == "dot-tok"

    def test_config_token_wins_over_op(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        config.write_text('base_url = "https://config.example.com"\ntoken = "config-tok"\n')

        def _should_not_call() -> str:
            raise AssertionError("op_token should not be called when config token is set")

        cfg = resolve(
            env={"YOUTRACK_OP_ITEM": "YouTrack"},
            dotenv_path=str(tmp_path / "nope.env"),
            config_path=str(config),
            op_token=_should_not_call,
        )
        assert cfg.token == "config-tok"

    def test_op_used_when_no_other_token(self, tmp_path: Path) -> None:
        def _op_token() -> str:
            return "op-tok"

        cfg = resolve(
            env={"YOUTRACK_OP_ITEM": "YouTrack"},
            dotenv_path=str(tmp_path / "nope.env"),
            op_token=_op_token,
        )
        assert cfg.token == "op-tok"

    def test_op_token_base_url_may_use_config(self, tmp_path: Path) -> None:
        config = tmp_path / "config.toml"
        config.write_text('base_url = "https://config.example.com"\n')

        def _op_token() -> str:
            return "op-tok"

        cfg = resolve(
            env={"YOUTRACK_OP_ITEM": "YouTrack"},
            dotenv_path=str(tmp_path / "nope.env"),
            config_path=str(config),
            op_token=_op_token,
        )
        assert cfg.token == "op-tok"
        assert cfg.base_url == "https://config.example.com"


class TestConfigSecurity:
    def test_dotenv_base_url_ignored_when_token_from_config(self, tmp_path: Path) -> None:
        dotenv = tmp_path / ".env"
        write_dotenv(dotenv, "YOUTRACK_BASE_URL=https://attacker.example\n")
        config = tmp_path / "config.toml"
        config.write_text('base_url = "https://safe.example.com"\ntoken = "config-tok"\n')
        cfg = resolve(env={}, dotenv_path=str(dotenv), config_path=str(config))
        # base_url must come from config, not from malicious .env
        assert cfg.base_url == "https://safe.example.com"
        assert cfg.token == "config-tok"

    def test_write_config_tightens_parent_dir_under_home(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        path = write_config("http://localhost:8080", "secret")
        assert path.exists()
        assert (path.stat().st_mode & 0o777) == 0o600
        assert (path.parent.stat().st_mode & 0o777) == 0o700
