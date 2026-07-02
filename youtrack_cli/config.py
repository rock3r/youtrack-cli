"""Configuration resolution — frozen contract in docs/contracts.md.

Stdlib-only (imports nothing from this package except re-exporting ConfigError).
"""

from __future__ import annotations

import os
import sys
import typing
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from youtrack_cli.errors import ConfigError

__all__ = ["Config", "ConfigError", "default_config_path", "resolve", "write_config"]

_DEFAULT_BASE_URL = "http://localhost:8080"

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass(frozen=True)
class Config:
    """Resolved CLI configuration."""

    base_url: str  # normalized, no trailing slash
    token: str
    me: str | None  # cached login from /api/users/me; None until the health check fills it


def default_config_path() -> Path:
    """Return the default user config file path."""
    config_dir = Path.home() / ".config" / "youtrack-cli"
    return config_dir / "config.toml"


def resolve(
    *,
    base_url: str | None = None,
    token: str | None = None,
    env: dict[str, str] | None = None,
    dotenv_path: str | None = None,
    config_path: str | Path | None = None,
    op_token: Callable[[], str] | None = None,
) -> Config:
    """Resolve config per-key: flag -> env -> current-directory `.env` -> config file -> op -> default.

    To avoid leaking a stored config token to a malicious CWD `.env`, the `.env`
    and config-file sources are never mixed: if the token comes from `.env`,
    base_url is taken from `.env` (or default); if the token comes from the
    config file, base_url is taken from the config file (or default). Flag and
    env remain fully composable per-key. 1Password (`op_token`) is the last
    token source; it is only invoked when no earlier source yields a token.

    A flag value counts as set unless it is `None` — an empty string does NOT
    fall through. base_url defaults to http://localhost:8080; a missing/empty
    token raises ConfigError.
    """
    env_map = env if env is not None else os.environ
    dotenv = _read_dotenv(dotenv_path) if dotenv_path is not None else _read_dotenv(".env")
    config = _read_config(config_path)

    env_token = env_map.get("YOUTRACK_TOKEN")
    dotenv_token = dotenv.get("YOUTRACK_TOKEN")
    config_token = config.get("token")

    resolved_token: str | None = None
    token_source: str | None = None

    if token is not None:
        resolved_token = token
        token_source = "flag"
    elif env_token:
        resolved_token = env_token
        token_source = "env"
    elif dotenv_token:
        resolved_token = dotenv_token
        token_source = "dotenv"
    elif config_token:
        resolved_token = config_token
        token_source = "config"
    elif op_token is not None:
        resolved_token = op_token()
        token_source = "op"

    env_base = env_map.get("YOUTRACK_BASE_URL")
    dotenv_base = dotenv.get("YOUTRACK_BASE_URL")
    config_base = config.get("base_url")

    if token_source in ("flag", "env", "op"):
        # Token from explicit flag, environment, or interactive op: base_url may be
        # resolved per-key across all remaining sources.
        resolved_base = _pick(base_url, env_base, dotenv_base, config_base)
    elif token_source == "dotenv":
        # Token from .env: do not use config-file base_url.
        resolved_base = _pick(base_url, env_base, dotenv_base, None)
    elif token_source == "config":
        # Token from config file: do not use .env base_url.
        resolved_base = _pick(base_url, env_base, None, config_base)
    else:
        resolved_base = _pick(base_url, env_base, dotenv_base, config_base)

    if not resolved_base:
        resolved_base = _DEFAULT_BASE_URL
    resolved_base = _normalize_base_url(resolved_base)

    if not resolved_token:
        raise ConfigError("youtrack-cli: not configured — set YOUTRACK_TOKEN (or pass --token=…).")

    return Config(base_url=resolved_base, token=resolved_token, me=None)


def write_config(
    base_url: str,
    token: str,
    config_path: str | Path | None = None,
    *,
    mode: int = 0o600,
) -> Path:
    """Write base_url and token to the config file atomically with restricted permissions.

    The parent directory is created (or re-stricted) with ``0o700`` and the file
    is written to a temporary sibling, then moved into place with ``os.replace``.
    After writing, the file's mode is set to ``0o600`` (or ``mode``) so that an
    existing permissive file is also tightened.
    """
    path = Path(config_path) if config_path else default_config_path()
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Tighten the directory only when it is under the user's home directory; for
    # custom paths (e.g. /tmp/...) we should not change system permissions.
    try:
        home = Path.home().resolve()
        resolved_parent = parent.resolve()
        if resolved_parent == home or home in resolved_parent.parents:
            parent.chmod(0o700)
    except OSError:
        pass

    text = f"base_url = {base_url!r}\ntoken = {token!r}\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        os.close(fd)
        raise
    tmp.replace(path)
    path.chmod(mode)
    return path


def _pick(
    flag: str | None,
    env_val: str | None,
    dotenv_val: str | None,
    config_val: str | None,
) -> str | None:
    """Flag wins if not None (even if empty); otherwise first truthy of env/dotenv/config."""
    if flag is not None:
        return flag
    if env_val:
        return env_val
    if dotenv_val:
        return dotenv_val
    if config_val:
        return config_val
    return None


def _normalize_base_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url:
        return url
    scheme = urlparse(url).scheme.lower()
    if scheme not in ("http", "https"):
        url = "https://" + url
    return url


def _read_dotenv(path: str) -> dict[str, str]:
    """Parse a .env file (KEY=VALUE), ignoring blanks and # comments. No shell expansion."""
    out: dict[str, str] = {}
    p = Path(path)
    if not p.is_file():
        return out
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value
    return out


def _read_config(path: str | Path | None) -> dict[str, Any]:
    """Parse a TOML config file, returning an empty dict if it does not exist."""
    p = Path(path) if path else default_config_path()
    if not p.is_file():
        return {}
    try:
        with p.open("rb") as f:
            return typing.cast(dict[str, Any], tomllib.load(f))
    except Exception as exc:
        raise ConfigError(f"Could not read config file {p}: {exc}") from exc
