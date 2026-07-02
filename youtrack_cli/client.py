"""HTTP client — frozen contract in docs/contracts.md.

The ONLY place that knows httpx. Returns parsed JSON; raises APIError on any non-2xx or
network failure. Never exposes httpx.Response to domain code.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from youtrack_cli.config import Config
from youtrack_cli.errors import APIError

__all__ = ["Client"]

_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)
_RETRY_BACKOFF = 0.5  # fixed, no jitter (deterministic for tests)


class Client:
    """Thin sync httpx wrapper over the YouTrack REST API."""

    def __init__(
        self,
        cfg: Config,
        *,
        httpx_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._cfg = cfg
        self._client = httpx_client if httpx_client is not None else httpx.Client(timeout=_TIMEOUT)
        self._sleep = sleep

    @property
    def timeout(self) -> httpx.Timeout:
        """The frozen timeout profile (exposed for tests/contract checks)."""
        t = self._client.timeout
        return (
            httpx.Timeout(connect=t.connect, read=t.read, write=t.write, pool=t.pool)
            if isinstance(t, httpx.Timeout)
            else _TIMEOUT
        )

    def get(
        self, path: str, *, params: dict[str, str] | None = None, fields: str | None = None
    ) -> Any:
        return self.request("GET", path, params=params, fields=fields)

    def post(
        self,
        path: str,
        *,
        json_body: Any | None = None,
        params: dict[str, str] | None = None,
        fields: str | None = None,
    ) -> Any:
        return self.request("POST", path, params=params, json_body=json_body, fields=fields)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: Any | None = None,
        fields: str | None = None,
    ) -> Any:
        url = self._cfg.base_url + path
        query: dict[str, str] = dict(params or {})
        if fields is not None:
            query["fields"] = fields
        headers = {
            "Authorization": f"Bearer {self._cfg.token}",
            "Accept": "application/json",
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        is_get = method.upper() == "GET"
        attempts_left = 2 if is_get else 1  # idempotent GET: 1 initial + 1 retry

        while True:
            try:
                resp = self._client.request(
                    method, url, params=query, json=json_body, headers=headers
                )
            except httpx.HTTPError as exc:
                if is_get and attempts_left > 1:
                    attempts_left -= 1
                    self._sleep(_RETRY_BACKOFF)
                    continue
                raise APIError.network_error(method, path, str(exc)) from exc

            if is_get and resp.status_code >= 500 and attempts_left > 1:
                attempts_left -= 1
                self._sleep(_RETRY_BACKOFF)
                continue

            if not (200 <= resp.status_code < 300):
                try:
                    body = resp.json()
                except ValueError:
                    body = {}
                if not isinstance(body, dict):
                    body = {}
                raise APIError.from_response(method, path, resp.status_code, body)

            if not resp.content:
                return None
            return resp.json()
