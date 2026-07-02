#!/usr/bin/env python3
"""
Complete YouTrack's first-run Configuration Wizard headlessly and mint a
permanent API token. Writes credentials to ../.env.

Idempotent: if the wizard is already done (server answers /api/users/me with
401/200) it skips straight to token creation/verification.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://localhost:8080"
ADMIN_PW = os.environ.get("YOUTRACK_ADMIN_PASSWORD", "Yt-Admin-2026!")
CONTAINER = "/opt/homebrew/bin/container"
NAME = "youtrack"
HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, "..", ".env")


def http(method, path, body=None, token=None, params=None):
    url = BASE + path
    q = dict(params or {})
    if token:
        q["wizardToken"] = token
    if q:
        url += "?" + urllib.parse.urlencode(q)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def container_logs():
    return subprocess.run([CONTAINER, "logs", NAME], capture_output=True, text=True).stdout


def get_wizard_token():
    for _ in range(60):
        log = container_logs()
        m = re.search(r"wizard_token=([A-Za-z0-9]+)", log)
        if m:
            return m.group(1)
        time.sleep(3)
    return None


def server_up():
    code, _ = http("GET", "/api/users/me")
    return code in (200, 401, 403)


def run_wizard():
    token = get_wizard_token()
    if not token:
        print("  no wizard token found in logs — already configured?", file=sys.stderr)
        return
    print(f"  wizard token: {token}")
    _, basic = http("GET", "/api/wizard/basic-settings/default", token=token)
    http("POST", "/api/wizard/basic-settings", basic, token=token)
    http("POST", "/api/wizard/hub-settings",
         {"disableInternalHub": False, "rootUser": "admin",
          "rootPassword": ADMIN_PW, "allowAnonymousAccess": False}, token=token)
    _, lic = http("GET", "/api/wizard/license-key/default", token=token)
    http("POST", "/api/wizard/license-key", lic, token=token)
    http("POST", "/api/wizard/wait/dump", {}, token=token)
    print("  wizard finished — server is starting the real service…")


def bearer(token):
    req = urllib.request.Request(BASE + "/api/users/me?fields=id,login,name")
    req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def get_token():
    # Reuse an existing token from .env if it still works.
    if os.path.exists(ENV_PATH):
        existing = {}
        for line in open(ENV_PATH):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                existing[k] = v
        tok = existing.get("YOUTRACK_TOKEN", "")
        if tok and tok.startswith("perm-") and bearer(tok):
            print(f"  existing token still valid")
            return tok

    # Basic auth to discover ids, then mint a permanent token via Hub.
    import base64
    auth = base64.b64encode(f"admin:{ADMIN_PW}".encode()).decode()

    def hub(path, method="GET", body=None):
        url = BASE + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", "Basic " + auth)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode() or "null")

    hub_id = hub("/hub/api/rest/users/me?fields=id")["id"]
    services = hub("/hub/api/rest/services?fields=id,name")
    scopes = [{"id": s["id"]} for s in services if s["name"] in ("YouTrack", "YouTrack Administration")]
    tok = hub(f"/hub/api/rest/users/{hub_id}/permanenttokens?fields=name,token,id",
              "POST", {"name": "youtrack-cli", "scope": scopes})["token"]
    print(f"  minted token: {tok}")
    return tok


def write_env(token):
    lines = [
        "# YouTrack local dev instance (Apple Container)",
        "YOUTRACK_BASE_URL=http://localhost:8080",
        "YOUTRACK_ADMIN_USER=admin",
        f"YOUTRACK_ADMIN_PASSWORD={ADMIN_PW}",
        f"YOUTRACK_TOKEN={token}",
    ]
    with open(ENV_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  wrote {ENV_PATH}")


def main():
    if not server_up():
        print("==> Completing configuration wizard")
        run_wizard()
        print("==> Waiting for YouTrack to finish booting")
        for _ in range(60):
            if server_up():
                break
            time.sleep(5)
    if not server_up():
        print("!! YouTrack did not come up", file=sys.stderr)
        sys.exit(1)
    print("==> API token")
    token = get_token()
    write_env(token)


if __name__ == "__main__":
    main()
