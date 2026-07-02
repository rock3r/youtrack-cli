"""Live integration tests against a running YouTrack instance.

These are opt-in via `pytest -m live` or `make test-live`. They expect a local
YouTrack server at http://localhost:8080 (or YOUTRACK_BASE_URL) with a token in
YOUTRACK_TOKEN. The default pytest run does not execute them.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from youtrack_cli.cli.app import app

runner = CliRunner()


def _base_token() -> tuple[str, str]:
    base = os.environ.get("YOUTRACK_BASE_URL", "http://localhost:8080").rstrip("/")
    token = os.environ.get("YOUTRACK_TOKEN", "")
    env = Path(".env")
    if not token and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            k, v = stripped.split("=", 1)
            if k.strip() == "YOUTRACK_TOKEN" and not token:
                token = v
            if k.strip() == "YOUTRACK_BASE_URL" and base == "http://localhost:8080":
                base = v.rstrip("/")
    if not token:
        pytest.skip("YOUTRACK_TOKEN not set; live tests require a running YouTrack instance")
    return base, token


def _api_delete(base: str, token: str, issue_id: str) -> None:
    req = urllib.request.Request(
        f"{base}/api/issues/{issue_id}",
        method="DELETE",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as e:
        if e.code not in (404, 204):
            raise


def _unique_summary(prefix: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    return f"{prefix}-{ts}"


@pytest.mark.live
class TestLive:
    def test_status(self) -> None:
        base, _ = _base_token()
        res = runner.invoke(app, ["--base-url", base, "status"])
        assert res.exit_code == 0, res.output

    def test_issues_list(self) -> None:
        base, _ = _base_token()
        res = runner.invoke(app, ["--base-url", base, "issues", "--all", "--limit", "3"])
        assert res.exit_code == 0, res.output

    def test_show_existing_issue(self) -> None:
        base, _ = _base_token()
        res = runner.invoke(app, ["--base-url", base, "show", "DEMO-1"])
        assert res.exit_code == 0, res.output

    def test_create_edit_comment_link(self) -> None:
        base, token = _base_token()
        summary = _unique_summary("live-create")

        # Create
        res = runner.invoke(
            app,
            [
                "--base-url",
                base,
                "create",
                "DEMO",
                summary,
                "--type",
                "Bug",
                "--priority",
                "Major",
            ],
        )
        assert res.exit_code == 0, res.output
        issue_id = res.stdout.split(":", 1)[0].split()[-1]
        assert issue_id.startswith("DEMO-")

        try:
            # Edit
            res = runner.invoke(
                app,
                [
                    "--base-url",
                    base,
                    "edit",
                    issue_id,
                    "--state",
                    "Done",
                ],
            )
            assert res.exit_code == 0, res.output

            # Comment
            res = runner.invoke(
                app,
                [
                    "--base-url",
                    base,
                    "comment",
                    issue_id,
                    "Live test comment",
                ],
            )
            assert res.exit_code == 0, res.output

            # Link
            res = runner.invoke(
                app,
                [
                    "--base-url",
                    base,
                    "link",
                    issue_id,
                    "relates_to",
                    "DEMO-1",
                ],
            )
            assert res.exit_code == 0, res.output
        finally:
            _api_delete(base, token, issue_id)

    def test_json_output(self) -> None:
        base, _ = _base_token()
        res = runner.invoke(app, ["--base-url", base, "--output", "json", "status"])
        assert res.exit_code == 0, res.output
        assert '"ok": true' in res.stdout
