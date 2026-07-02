"""Tests for youtrack_cli.errors — frozen contract (docs/contracts.md)."""

from __future__ import annotations

import pytest

from youtrack_cli.errors import APIError, ConfigError, ExitCode


class TestExitCode:
    def test_values_are_frozen(self) -> None:
        assert ExitCode.OK == 0
        assert ExitCode.USAGE == 2
        assert ExitCode.VALIDATION == 3
        assert ExitCode.NOT_FOUND == 4
        assert ExitCode.PERMISSION == 5
        assert ExitCode.WORKFLOW == 6
        assert ExitCode.API == 1

    def test_is_int(self) -> None:
        assert int(ExitCode.OK) == 0


class TestAPIErrorConstruction:
    def test_from_response_decodes_full_workflow_body(self) -> None:
        body = {
            "error": "Field required",
            "error_description": "Target version is required",
            "error_field": "Target version",
            "error_rule_name": "@jetbrains/required-custom-fields-feature",
            "error_type": "workflow",
            "error_workflow_type": "require",
            "error_project_custom_field_id": "186-503",
        }
        err = APIError.from_response("POST", "/api/issues", 400, body)
        assert err.status == 400
        assert err.code == "Field required"
        assert err.description == "Target version is required"
        assert err.field == "Target version"
        assert err.rule_name == "@jetbrains/required-custom-fields-feature"
        assert err.type == "workflow"
        assert err.workflow_type == "require"
        assert err.request_method == "POST"
        assert err.request_path == "/api/issues"
        assert err.raw == body

    def test_from_response_handles_missing_fields_gracefully(self) -> None:
        # server may return minimal error payloads
        err = APIError.from_response("GET", "/api/issues/X", 500, {})
        assert err.status == 500
        assert err.code is None
        assert err.description == ""
        assert err.field is None
        assert err.rule_name is None
        assert err.type is None
        assert err.workflow_type is None

    def test_from_response_uses_message_when_no_description(self) -> None:
        err = APIError.from_response("GET", "/x", 403, {"message": "No permission"})
        assert err.description == "No permission"

    def test_from_response_prefers_error_code_over_error(self) -> None:
        err = APIError.from_response("GET", "/x", 400, {"error_code": "bad_request", "error": "x"})
        assert err.code == "bad_request"


class TestAPIErrorExitCodeMapping:
    @pytest.mark.parametrize(
        ("status", "body", "expected"),
        [
            (401, {}, ExitCode.PERMISSION),
            (
                403,
                {"error_description": "No permission to create issue in project YouTrack"},
                ExitCode.PERMISSION,
            ),
            (404, {}, ExitCode.NOT_FOUND),
            (400, {"error_type": "workflow"}, ExitCode.WORKFLOW),
            (
                400,
                {"error_rule_name": "@jetbrains/required-custom-fields-feature"},
                ExitCode.WORKFLOW,
            ),
            (400, {"error": "Value is not allowed"}, ExitCode.VALIDATION),
            (500, {}, ExitCode.API),
            (502, {}, ExitCode.API),
        ],
    )
    def test_mapping(self, status: int, body: dict[str, object], expected: ExitCode) -> None:
        err = APIError.from_response("GET", "/x", status, body)
        assert err.exit_code == expected

    def test_workflow_takes_precedence_over_validation(self) -> None:
        # a 400 with a rule_name is a workflow guard, not generic validation
        err = APIError.from_response("POST", "/api/issues", 400, {"error_rule_name": "x"})
        assert err.exit_code == ExitCode.WORKFLOW


class TestAPIErrorRetryable:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [(500, True), (502, True), (503, True), (400, False), (403, False), (404, False)],
    )
    def test_http_retryable(self, status: int, expected: bool) -> None:
        err = APIError.from_response("GET", "/x", status, {})
        assert err.retryable is expected

    def test_network_error_is_retryable(self) -> None:
        err = APIError.network_error("GET", "/x", "Connection refused")
        assert err.status == 0
        assert err.retryable is True
        assert err.exit_code == ExitCode.API
        assert "Connection refused" in err.description


class TestConfigError:
    def test_is_usage_exit(self) -> None:
        err = ConfigError("youtrack-cli: not configured — set YOUTRACK_TOKEN (or pass --token=…).")
        assert err.exit_code == ExitCode.USAGE

    def test_message_contains_required_substrings(self) -> None:
        # frozen message contract: must mention YOUTRACK_TOKEN and --token
        err = ConfigError("youtrack-cli: not configured — set YOUTRACK_TOKEN (or pass --token=…).")
        assert "youtrack-cli: not configured" in str(err)
        assert "YOUTRACK_TOKEN" in str(err)
        assert "--token" in str(err)
