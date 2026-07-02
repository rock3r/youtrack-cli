"""Error types and exit codes — frozen contract in docs/contracts.md.

Stdlib-only (imports nothing from this package).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class ExitCode(IntEnum):
    """Process exit codes. Stable — scripts depend on these values."""

    OK = 0
    API = 1  # other HTTP/server error or unexpected failure
    USAGE = 2
    VALIDATION = 3  # client-side validation (bad value, unknown project/field)
    NOT_FOUND = 4  # 404 — may be "no match" OR "no access"
    PERMISSION = 5  # 401 (bad/missing token or scope) or 403 (no right)
    WORKFLOW = 6  # server workflow guard (required field, bad transition)


class CliError(Exception):
    """Base for all errors the CLI surfaces with a specific exit code."""

    @property
    def exit_code(self) -> ExitCode:
        raise NotImplementedError


@dataclass
class APIError(CliError):
    """An error returned by the YouTrack REST API (the only HTTP error type)."""

    status: int
    code: str | None
    description: str
    rule_name: str | None
    field: str | None
    type: str | None
    workflow_type: str | None
    request_method: str
    request_path: str
    raw: Any

    def __post_init__(self) -> None:
        super().__init__(self.description)

    @classmethod
    def from_response(cls, method: str, path: str, status: int, body: dict[str, Any]) -> APIError:
        """Build an APIError from a decoded JSON error body, tolerating missing fields."""
        return cls(
            status=status,
            code=body.get("error_code") or body.get("error"),
            description=body.get("error_description") or body.get("message") or "",
            rule_name=body.get("error_rule_name"),
            field=body.get("error_field"),
            type=body.get("error_type"),
            workflow_type=body.get("error_workflow_type"),
            request_method=method,
            request_path=path,
            raw=body,
        )

    @classmethod
    def network_error(cls, method: str, path: str, message: str) -> APIError:
        """A transport/network failure (connection refused, DNS, timeout)."""
        return cls(
            status=0,
            code="connect_error",
            description=message,
            rule_name=None,
            field=None,
            type=None,
            workflow_type=None,
            request_method=method,
            request_path=path,
            raw={},
        )

    @property
    def exit_code(self) -> ExitCode:
        if self.status in (401, 403):
            return ExitCode.PERMISSION
        if self.status == 404:
            return ExitCode.NOT_FOUND
        if self.status == 400:
            if self.type == "workflow" or self.rule_name:
                return ExitCode.WORKFLOW
            return ExitCode.VALIDATION
        return ExitCode.API

    @property
    def retryable(self) -> bool:
        """True for 5xx or transport/network errors (status==0); never for 4xx."""
        return self.status == 0 or self.status >= 500


class ConfigError(CliError):
    """Raised when required configuration (token) is missing or invalid."""

    @property
    def exit_code(self) -> ExitCode:
        return ExitCode.USAGE


class ValidationError(CliError):
    """Raised for client-side validation failures (bad field value, unknown project/field)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)

    @property
    def exit_code(self) -> ExitCode:
        return ExitCode.VALIDATION
