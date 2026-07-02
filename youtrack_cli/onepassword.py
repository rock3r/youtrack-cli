"""Fetch secrets from the 1Password CLI (`op`).

This module is intentionally small and isolated: it only knows how to invoke `op` and
parse its JSON output. All error paths raise `OnePasswordError` so the CLI can surface
a clear, actionable message.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from youtrack_cli.errors import ValidationError


class OnePasswordError(ValidationError):
    """Raised when the 1Password CLI cannot return a requested secret."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# Cache per (vault, item, field) so a single command never invokes `op` more than once.
_cache: dict[tuple[str, str, str], str] = {}


def _run_op(args: list[str], timeout: float) -> str:
    """Run the 1Password CLI with the supplied arguments and return stdout text."""
    op_path = shutil.which("op")
    if not op_path:
        raise OnePasswordError("1Password CLI ('op') not found on PATH.")

    try:
        result = subprocess.run(
            [op_path, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise OnePasswordError(
            "1Password sign-in timed out or was not approved. "
            "Check that 1Password is unlocked and that this process can reach it."
        ) from None
    except OSError as exc:
        raise OnePasswordError(f"Could not run 1Password CLI: {exc}") from exc

    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise OnePasswordError(f"1Password CLI failed: {err}")

    return result.stdout


def _item_value(item: dict[str, Any], field: str) -> str:
    """Extract the requested field value from a `op item get --format json` response."""
    for f in item.get("fields", []):
        if f.get("id") == field or f.get("label") == field:
            value = f.get("value")
            if value is None:
                raise OnePasswordError(f"1Password field '{field}' has no value")
            return str(value)
    raise OnePasswordError(
        f"Field '{field}' not found in 1Password item. "
        f"Available fields: {', '.join(str(f.get('label')) for f in item.get('fields', []))}"
    )


def fetch_token(
    vault: str,
    item: str,
    field: str = "password",
    *,
    timeout: float = 30.0,
) -> str:
    """Return a secret from 1Password, caching the result for the process lifetime.

    The field name matches either the field's `id` or `label` in the 1Password item.
    The default field is ``password``.
    """
    if not vault:
        raise OnePasswordError("1Password vault is required")
    if not item:
        raise OnePasswordError("1Password item is required")

    key = (vault, item, field)
    if key in _cache:
        return _cache[key]

    stdout = _run_op(
        ["item", "get", item, "--vault", vault, "--format", "json"],
        timeout=timeout,
    )

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise OnePasswordError(f"1Password CLI returned invalid JSON: {exc}") from exc

    value = _item_value(data, field)
    _cache[key] = value
    return value


def clear_cache() -> None:
    """Clear the in-process cache. Useful in tests."""
    _cache.clear()
