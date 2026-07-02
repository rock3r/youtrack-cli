#!/usr/bin/env python3
"""
Enrich the local seed data with comments and links so it represents the
workflow variety seen on youtrack.jetbrains.com (discussions, issue
relationships, etc.).

Idempotent: safe to re-run. Reads config from ../.env.

Usage:
    python3 scripts/provision_enrichment.py
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("YOUTRACK_BASE_URL", "").rstrip("/")
TOKEN = os.environ.get("YOUTRACK_TOKEN", "")

env = os.path.join(HERE, "..", ".env")
if not TOKEN and os.path.exists(env):
    with open(env, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            k, v = stripped.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    BASE = os.environ.get("YOUTRACK_BASE_URL", "").rstrip("/")
    TOKEN = os.environ.get("YOUTRACK_TOKEN", "")
if not TOKEN:
    sys.exit("YOUTRACK_TOKEN not set")


def api(method, path, body=None, fields=None):
    url = BASE + path
    if fields:
        url += ("&" if "?" in url else "?") + "fields=" + urllib.parse.quote(fields)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return {
            "__error__": True,
            "status": e.code,
            "body": json.loads(e.read().decode() or "{}"),
            "url": url,
            "method": method,
        }


def ok(r):
    return not (isinstance(r, dict) and r.get("__error__"))


def err(r):
    print(
        f"  !! {r['method']} {r['url']} -> {r['status']}: {json.dumps(r['body'])[:200]}",
        file=sys.stderr,
    )


COMMENTS = [
    "I can still reproduce this on the latest build.",
    "Looks like a duplicate of an older issue — let's verify.",
    "Added logs and a minimal reproducer.",
    "This is blocked by the indexing refactor.",
    "Verified in 2026.2.17012. Closing.",
    "Could we split this into smaller tickets?",
    "Updated the description with screenshots.",
    "Discussed in the team meeting; target is 2026.3.",
    "Please attach a CPU snapshot if it happens again.",
    "The fix is on the release branch.",
]

LINK_TYPES = ["relates to", "depends on", "duplicates"]

PROJECTS = ["JT", "IJPL", "IDEA", "KT", "RID", "WEB", "PY"]


def issues_for_project(short):
    r = api(
        "GET",
        f"/api/issues?query={urllib.parse.quote(f'project:{short}')}&fields=idReadable,summary&$top=30",
    )
    if not ok(r):
        err(r)
        return []
    return [i for i in (r if isinstance(r, list) else []) if i.get("idReadable")]


def already_enriched(issue_id):
    """Return True if the issue already has comments or links."""
    r = api(
        "GET",
        f"/api/issues/{issue_id}?fields=comments(id),links(id)",
    )
    if not ok(r):
        err(r)
        return True  # safer to skip on error
    has_comments = bool(r.get("comments"))
    has_links = bool(r.get("links"))
    return has_comments or has_links


def add_comment(issue_id, text):
    r = api(
        "POST",
        f"/api/issues/{issue_id}/comments?fields=id",
        {"$type": "IssueComment", "text": text},
    )
    if not ok(r):
        err(r)
    else:
        print(f"  + comment on {issue_id}")


def link_issues(source_id, target_id, link_type):
    r = api(
        "POST",
        "/api/commands",
        {
            "$type": "CommandList",
            "query": f"{link_type} {target_id}",
            "issues": [{"$type": "Issue", "idReadable": source_id}],
        },
    )
    if not ok(r):
        err(r)
    else:
        print(f"  + linked {source_id} {link_type} {target_id}")


def main():
    print("== enriching seed data ==")
    for short in PROJECTS:
        issues = issues_for_project(short)
        if not issues:
            print(f"   {short}: no issues found")
            continue
        print(f"   {short}: {len(issues)} issues")
        for idx, issue in enumerate(issues):
            issue_id = issue["idReadable"]
            if already_enriched(issue_id):
                print(f"   {issue_id}: already enriched, skipping")
                continue
            # Deterministic pseudo-random choices based on issue id
            h = hash(issue_id)

            # Add a comment to ~60% of issues
            if h % 10 < 6:
                comment = COMMENTS[h % len(COMMENTS)]
                add_comment(issue_id, comment)

            # Link to the next issue in the list using a rotating link type
            if idx + 1 < len(issues):
                target = issues[idx + 1]["idReadable"]
                link_type = LINK_TYPES[h % len(LINK_TYPES)]
                link_issues(issue_id, target, link_type)
    print("== done ==")


if __name__ == "__main__":
    main()
