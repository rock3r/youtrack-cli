#!/usr/bin/env python3
"""
Provision a realistic JetBrains-style structure into a local YouTrack instance,
mirroring the structure of youtrack.jetbrains.com so we can build & test the
YouTrack CLI against representative data (projects, custom fields, users, groups,
agile boards, and issues across many states/priorities/types).

Idempotent: safe to re-run. Reads config from .env.

Usage:
    python3 scripts/provision.py
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("YOUTRACK_BASE_URL", "http://localhost:8080").rstrip("/")
TOKEN = os.environ.get("YOUTRACK_TOKEN", "")


def _load_env(path=".env"):
    global TOKEN
    if TOKEN:
        return
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    TOKEN = os.environ.get("YOUTRACK_TOKEN", "")


_load_env(os.path.join(os.path.dirname(__file__), "..", ".env"))
if not TOKEN:
    print("ERROR: YOUTRACK_TOKEN not set (put it in .env)", file=sys.stderr)
    sys.exit(1)


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
        body_txt = e.read().decode()
        try:
            parsed = json.loads(body_txt)
        except Exception:
            parsed = body_txt
        return {"__error__": True, "status": e.code, "body": parsed, "url": url, "method": method}


def ok(res):
    return not (isinstance(res, dict) and res.get("__error__"))


def fail(res):
    print(f"  !! {res['method']} {res['url']} -> {res['status']}: "
          f"{json.dumps(res['body'])[:300]}", file=sys.stderr)


# ---------------------------------------------------------------- resources

def list_existing(path, key="name"):
    res = api("GET", path + "&$top=200")
    if not ok(res):
        fail(res)
        return {}
    items = res if isinstance(res, list) else res.get("items", res.get(res.get("listkey", "users"), []))
    # tolerate paged dict shapes
    if isinstance(res, dict):
        for v in res.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                items = v
                break
    return {it[key]: it for it in items if isinstance(it, dict) and key in it}


def get_bundle(btype, name):
    res = api("GET", f"/api/admin/customFieldSettings/bundles/{btype}?fields=id,name&$top=100")
    if not ok(res):
        return None
    for b in res:
        if b["name"] == name:
            return b["id"]
    return None


def get_field(name):
    res = api("GET", "/api/admin/customFieldSettings/customFields?fields=id,name,fieldType(valueType)&$top=100")
    if not ok(res):
        return None
    for f in res:
        if f["name"] == name:
            return f
    return None


# Global field / bundle map
FIELD = {}  # name -> {id, valueType}
BUNDLE = {}  # name -> id  (global bundles)


def load_globals():
    for f in api("GET", "/api/admin/customFieldSettings/customFields?fields=id,name,fieldType(valueType)&$top=100"):
        FIELD[f["name"]] = {"id": f["id"], "valueType": f["fieldType"]["valueType"]}
    for btype in ("enum", "state", "version", "ownedField", "build"):
        res = api("GET", f"/api/admin/customFieldSettings/bundles/{btype}?fields=id,name&$top=100")
        if ok(res):
            for b in res:
                BUNDLE.setdefault(b["name"], b["id"])


# ---------------------------------------------------------------- users / groups

def ensure_user(login, full, email):
    # Hub user creation
    res = api("GET", f"/hub/api/rest/users?query={urllib.parse.quote(login)}&fields=id,login&$top=5")
    users = res.get("users", []) if ok(res) and isinstance(res, dict) else []
    for u in users:
        if u.get("login") == login:
            return u["id"]
    body = {"login": login, "name": full, "email": email,
            "password": {"oldValue": "", "newValue": os.environ.get("TEAM_DEFAULT_PASSWORD", "JetBrains-2026!")}}
    r = api("POST", "/hub/api/rest/users?fields=id,login", body)
    if ok(r):
        print(f"  + user {login} ({full})")
        return r["id"]
    fail(r)
    # fallback: maybe already exists under a different query
    return None


def ensure_group(name):
    res = api("GET", f"/hub/api/rest/usergroups?query={urllib.parse.quote(name)}&fields=id,name&$top=5")
    groups = res.get("usergroups", []) if ok(res) and isinstance(res, dict) else []
    for g in groups:
        if g.get("name") == name:
            return g["id"]
    r = api("POST", "/hub/api/rest/usergroups?fields=id,name", {"name": name})
    if ok(r):
        print(f"  + group {name}")
        return r["id"]
    fail(r)
    return None


def add_to_group(user_hub_id, group_id):
    api("POST", f"/hub/api/rest/usergroups/{group_id}/users?fields=id", {"id": user_hub_id})


# ---------------------------------------------------------------- projects

def yt_user_id(login):
    r = api("GET", f"/api/users?query={urllib.parse.quote(login)}&fields=id,login&$top=5")
    for u in (r if ok(r) and isinstance(r, list) else []):
        if u.get("login") == login:
            return u["id"]
    return None


_user_id_cache = {}


def ensure_project(short, name, leader_login, description=""):
    res = api("GET", f"/api/admin/projects?fields=id,name,shortName&$top=200")
    for p in res if ok(res) else []:
        if p["shortName"] == short:
            return p["id"]
    if leader_login not in _user_id_cache:
        _user_id_cache[leader_login] = yt_user_id(leader_login)
    lid = _user_id_cache[leader_login]
    body = {
        "name": name,
        "shortName": short,
        "leader": {"id": lid} if lid else {"login": leader_login},
        "description": description,
    }
    r = api("POST", "/api/admin/projects?fields=id,name,shortName", body)
    if ok(r):
        print(f"  + project {short} ({name})")
        return r["id"]
    fail(r)
    return None


PROJECT_FIELD_TYPE = {
    "enum": "EnumProjectCustomField",
    "state": "StateProjectCustomField",
    "version": "VersionProjectCustomField",
    "ownedField": "OwnedProjectCustomField",
    "user": "UserProjectCustomField",
    "period": "PeriodProjectCustomField",
    "date": "DateProjectCustomField",
    "build": "BuildProjectCustomField",
}

FIELD_TYPE_BUNDLE = {"enum": "enum", "state": "state", "version": "version",
                     "ownedField": "ownedField", "build": "build"}


def get_project_field(pid, field_name):
    cur = api("GET", f"/api/admin/projects/{pid}/customFields?fields=id,$type,field(name),bundle(id,name)&$top=100")
    if ok(cur):
        for cf in cur:
            if cf.get("field", {}).get("name") == field_name:
                return cf
    return None


def populate_field_bundle(pid, field_name, values, owner_login=None, vtype="ownedField"):
    """Populate the bundle currently attached to a project field with `values`.
    Retries briefly in case the project's auto-attached fields aren't ready yet."""
    import time
    cf = None
    for _ in range(10):
        cf = get_project_field(pid, field_name)
        if cf:
            break
        time.sleep(0.5)
    if not cf or not cf.get("bundle"):
        return
    bid = cf["bundle"]["id"]
    btype = vtype
    r = api("GET", f"/api/admin/customFieldSettings/bundles/{btype}/{bid}?fields=id,values(name)&$top=200")
    existing = {v["name"] for v in (r.get("values", []) if ok(r) else [])}
    for val in values:
        if val in existing:
            continue
        body = {"name": val}
        if vtype == "ownedField":
            body["owner"] = {"login": owner_login}
        api("POST", f"/api/admin/customFieldSettings/bundles/{btype}/{bid}/values?fields=id", body)


def attach_field(project_id, field_name, bundle_name=None, can_be_empty=True,
                 empty_text=None):
    """Attach a global field to a project if not already attached."""
    f = FIELD.get(field_name)
    if not f:
        print(f"  !! unknown global field {field_name}", file=sys.stderr)
        return
    if get_project_field(project_id, field_name):
        return  # already attached
    vt = f["valueType"]
    body = {
        "$type": PROJECT_FIELD_TYPE.get(vt, "EnumProjectCustomField"),
        "field": {"id": f["id"]},
        "canBeEmpty": can_be_empty,
        "emptyFieldText": empty_text or f"No {field_name}",
    }
    r = api("POST", f"/api/admin/projects/{project_id}/customFields?fields=id", body)
    if not ok(r):
        fail(r)


def ensure_version_bundle(name, versions):
    bid = BUNDLE.get(name) or get_bundle("version", name)
    if bid:
        # ensure versions exist
        r = api("GET", f"/api/admin/customFieldSettings/bundles/version/{bid}?fields=id,values(name)&$top=100")
        existing = {v["name"] for v in (r.get("values", []) if ok(r) else [])}
        missing = [v for v in versions if v not in existing]
        if missing:
            api("POST", f"/api/admin/customFieldSettings/bundles/version/{bid}/values?fields=id",
                [{"name": m} for m in missing])
        BUNDLE[name] = bid
        return bid
    r = api("POST", "/api/admin/customFieldSettings/bundles/version?fields=id",
            {"name": name, "values": [{"name": v} for v in versions]})
    if ok(r):
        BUNDLE[name] = r["id"]
        return r["id"]
    fail(r)
    return None


def ensure_owned_bundle(name, owners, owner_login):
    bid = BUNDLE.get(name) or get_bundle("ownedField", name)
    if bid:
        r = api("GET", f"/api/admin/customFieldSettings/bundles/ownedField/{bid}?fields=id,values(name)&$top=100")
        existing = {v["name"] for v in (r.get("values", []) if ok(r) else [])}
        missing = [o for o in owners if o not in existing]
        for m in missing:
            api("POST", f"/api/admin/customFieldSettings/bundles/ownedField/{bid}/values?fields=id",
                {"name": m, "owner": {"login": owner_login}})
        BUNDLE[name] = bid
        return bid
    # create with empty values, then add them individually (owner required)
    r = api("POST", "/api/admin/customFieldSettings/bundles/ownedField?fields=id",
            {"name": name})
    if not ok(r):
        fail(r)
        return None
    bid = r["id"]
    BUNDLE[name] = bid
    for o in owners:
        api("POST", f"/api/admin/customFieldSettings/bundles/ownedField/{bid}/values?fields=id",
            {"name": o, "owner": {"login": owner_login}})
    return bid


# ---------------------------------------------------------------- issues

def create_issue(project_id, summary, desc="", fields=None, leader_login=None):
    def post(cfs):
        body = {"project": {"id": project_id}, "summary": summary, "description": desc}
        if cfs:
            body["customFields"] = cfs
        return api("POST", "/api/issues?fields=id,idReadable,summary", body)

    r = post(fields)
    if ok(r):
        return r["idReadable"]
    # YouTrack only allows assigning users who are in the project's team.
    # Fall back to the project leader, then to unassigned, so issues always create.
    body = r.get("body", {}) if isinstance(r.get("body"), dict) else {}
    is_value_err = ("Value is not allowed" in str(body))
    if is_value_err and fields:
        non_assignee = [f for f in fields if f.get("name") != "Assignee"]
        if leader_login:
            r2 = post(non_assignee + [fv("Assignee", leader_login)])
            if ok(r2):
                return r2["idReadable"]
        r3 = post(non_assignee)
        if ok(r3):
            return r3["idReadable"]
    fail(r)
    return None


def fv(field_name, value):
    """Build a customField value entry with correct YouTrack $types.
    value: str (single) or list (multi) or int (period minutes)."""
    vt = FIELD.get(field_name, {}).get("valueType", "enum")
    if vt == "state":
        return {"$type": "StateIssueCustomField", "name": field_name,
                "value": {"$type": "StateBundleElement", "name": value}}
    if vt == "user":
        return {"$type": "SingleUserIssueCustomField", "name": field_name,
                "value": {"$type": "User", "login": value}}
    if vt == "period":
        mins = int(str(value).rstrip("hHmM ")) * (60 if str(value).lower().endswith("h") else 1)
        return {"$type": "PeriodIssueCustomField", "name": field_name,
                "value": {"$type": "PeriodValue", "minutes": mins}}
    if vt == "ownedField":
        return {"$type": "SingleOwnedIssueCustomField", "name": field_name,
                "value": {"$type": "OwnedBundleElement", "name": value}}
    if vt == "version":
        vals = value if isinstance(value, list) else [value]
        return {"$type": "MultiVersionIssueCustomField", "name": field_name,
                "value": [{"$type": "VersionBundleElement", "name": v} for v in vals]}
    if vt == "build":
        return {"$type": "SingleBuildIssueCustomField", "name": field_name,
                "value": {"$type": "BuildBundleElement", "name": value}}
    if vt == "date":
        return {"$type": "DateIssueCustomField", "name": field_name, "value": value}
    # default: single enum (Priority, Type, etc.)
    return {"$type": "SingleEnumIssueCustomField", "name": field_name,
            "value": {"$type": "EnumBundleElement", "name": value}}


# ==================================================================== DATA

TEAM = [
    ("admin",            "System Administrator", "admin@example.com"),
    ("anna.smirnova",    "Anna Smirnova",        "anna.smirnova@example.com"),
    ("maxim.moss",       "Maxim Moss",           "maxim.moss@example.com"),
    ("ekaterina.saripova","Ekaterina Saripova",  "ekaterina.saripova@example.com"),
    ("vadim.gurov",      "Vadim Gurov",          "vadim.gurov@example.com"),
    ("ilya.bystrov",     "Ilya Bystrov",         "ilya.bystrov@example.com"),
    ("marina.korneva",   "Marina Korneva",       "marina.korneva@example.com"),
    ("dmitry.pavlov",    "Dmitry Pavlov",        "dmitry.pavlov@example.com"),
    ("olga.zaitseva",    "Olga Zaitseva",        "olga.zaitseva@example.com"),
    ("pavel.shirov",     "Pavel Shirov",         "pavel.shirov@example.com"),
]

GROUPS = ["Developers", "QA Engineers", "Designers", "YouTrack Team"]

# Projects mirroring youtrack.jetbrains.com
# short, name, leader, description, subsystems, versions
PROJECTS = [
    ("JT",  "YouTrack",            "anna.smirnova",
     "The YouTrack issue tracker itself (dogfooding).",
     ["Agile Boards", "API & REST", "Workflows", "Search", "Notifications", "UI", "Import", "Reports"],
     ["2026.2", "2026.3", "2027.1"]),
    ("IJPL","IntelliJ Platform",   "maxim.moss",
     "The shared IntelliJ Platform.",
     ["Editor", "VCS", "Build System", "Debugger", "Indexing", "Plugins", "UI"],
     ["2026.2", "2026.3"]),
    ("IDEA","IntelliJ IDEA",       "vadim.gurov",
     "IntelliJ IDEA — The Java IDE.",
     ["Java", "Kotlin", "Maven", "Gradle", "Code Inspection", "UI"],
     ["2026.2", "2026.3"]),
    ("KT",  "Kotlin Plugin",       "ilya.bystrov",
     "Kotlin language support in IntelliJ-based IDEs.",
     ["Compiler", "Scripting", "Debugger", "Refactorings", "Android"],
     ["2.2.0", "2.3.0"]),
    ("RID", "Rider",               "dmitry.pavlov",
     "Rider — The .NET IDE.",
     ["C# Support", "NuGet", "Unity", "Debugger", "ASP.NET"],
     ["2026.2", "2026.3"]),
    ("WEB", "WebStorm",            "marina.korneva",
     "WebStorm — The JavaScript & TypeScript IDE.",
     ["TypeScript", "Vue", "React", "CSS", "Node.js", "Debugger"],
     ["2026.2", "2026.3"]),
    ("PY",  "PyCharm",             "pavel.shirov",
     "PyCharm — The Python IDE.",
     ["Python", "Django", "Scientific", "Debugger", "Type Checking"],
     ["2026.2", "2026.3"]),
]

STATES = ["Submitted", "Open", "In Progress", "To be discussed", "Reopened",
          "Fixed", "Can't Reproduce", "Verified", "Won't fix"]
PRIORITIES = ["Show-stopper", "Critical", "Major", "Normal", "Minor"]
TYPES = ["Bug", "Feature", "Task", "Cosmetics", "Exception", "Performance Problem", "Epic"]

import itertools

ISSUE_TEMPLATES = [
    ("Crash when opening large project", "## Problem\n\n{app} crashes with an out-of-memory error when opening a project with more than 100 modules.\n\n### Steps to reproduce\n\n1. Open {app}.\n2. Create a project with 100+ modules.\n3. Restart the IDE.\n\nExpected: IDE loads.\nActual: `OutOfMemoryError` in the log.\n\n### Environment\n\n- JDK 23\n- 16 GB RAM",
     dict(Type="Bug", Priority="Critical")),
    ("Support {feat} in the {area}", "## Feature request\n\nAdd first-class support for **{feat}** within **{area}**. This would improve the daily workflow for teams using monorepos.\n\n### Use cases\n\n- Faster navigation\n- Better refactoring coverage\n- CI integration",
     dict(Type="Feature", Priority="Major")),
    ("{area} is slow on large repositories", "## Performance issue\n\nPerformance degrades roughly linearly with repository size; indexing takes several minutes on a 500k-line codebase.\n\n### Profiling notes\n\n- CPU usage is normal.\n- GC pauses are minimal.\n- Disk I/O appears to be the bottleneck.",
     dict(Type="Performance Problem", Priority="Major")),
    ("NPE in {area} when {cond}", "## Exception\n\nA `NullPointerException` is thrown at runtime when {cond}.\n\n```\njava.lang.NullPointerException: Cannot invoke ... because \"x\" is null\n    at com.example.Foo.bar(Foo.java:42)\n```",
     dict(Type="Exception", Priority="Normal")),
    ("Update documentation for {feat}", "## Documentation\n\nThe documentation for {feat} is outdated after the recent release. Several screenshots still show the old UI, and the keyboard shortcuts are wrong.\n\n### Pages to update\n\n- Quick start\n- Reference manual\n- Release notes",
     dict(Type="Task", Priority="Minor")),
    ("Improve dark theme contrast in {area}", "## UI polish\n\nText contrast is too low in the new dark theme for **{area}**. WCAG ratio is below 4.5:1 for secondary labels.",
     dict(Type="Cosmetics", Priority="Minor")),
    ("Add {feat} as an Epic for the next release", "## Epic\n\nTrack all workstreams related to {feat} under one epic.\n\n### Sub-tasks (proposed)\n\n- Backend implementation\n- UI/UX design\n- Documentation\n- QA validation",
     dict(Type="Epic", Priority="Major")),
    ("{area}: {cond}", "## Bug\n\n{cond} causes incorrect behavior in {area}. This was reported by a user on the community forum.\n\n### Impact\n\n- Breaks the default workflow.\n- Affects both new and existing projects.",
     dict(Type="Bug", Priority="Normal")),
]

FEATURES = ["GraphQL API", "dark mode", "monorepo support", "remote development",
            "AI completion", "semantic search", "offline mode", "shared indexes"]
AREAS = ["the editor", "the VCS log", "the debugger", "the project tree", "indexing"]
CONDS = ["file is read-only", "network is offline", "plugin is disabled",
         "project uses spaces in path", "JDK 23 is selected"]


def gen_issues_for(project_short, leader_login, count=14):
    """Yield (summary, description, fields) deterministically per project."""
    rng = itertools.count()
    combos = []
    seq = itertools.count(1)
    for ti, (tmpl_sum, tmpl_desc, base) in enumerate(ISSUE_TEMPLATES):
        for k in range(2):
            feat = FEATURES[(ti * 2 + k) % len(FEATURES)]
            area = AREAS[(ti + k) % len(AREAS)]
            cond = CONDS[(ti + k) % len(CONDS)]
            n = next(seq)
            summary = f"{tmpl_sum.format(app=project_short, feat=feat, area=area, cond=cond)} #{n}"
            desc = tmpl_desc.format(app=project_short, feat=feat, area=area, cond=cond)
            # rotate state/priority/assignee
            idx = next(rng)
            state = STATES[(idx) % len(STATES)]
            priority = PRIORITIES[(idx + ti) % len(PRIORITIES)]
            assignees = [u[0] for u in TEAM if u[0] != "admin"]
            assignee = assignees[(idx + k) % len(assignees)]
            flds = {"State": state, "Priority": priority, "Type": base["Type"],
                    "Assignee": assignee}
            if state in ("Fixed", "Verified"):
                flds["Fix versions"] = "2026.2"
            combos.append((summary[:140], desc, flds))
            if len(combos) >= count:
                return combos
    return combos


# ==================================================================== MAIN

def main():
    print("== loading global fields/bundles ==")
    load_globals()
    print(f"   fields: {len(FIELD)}  bundles: {len(BUNDLE)}")

    print("== users ==")
    hub_ids = {}
    for login, full, email in TEAM:
        uid = ensure_user(login, full, email)
        hub_ids[login] = uid

    print("== groups ==")
    group_ids = {}
    for g in GROUPS:
        group_ids[g] = ensure_group(g)
    # add users to groups
    devs = ["anna.smirnova", "maxim.moss", "vadim.gurov", "ilya.bystrov",
            "dmitry.pavlov", "pavel.shirov"]
    qas = ["ekaterina.saripova", "olga.zaitseva"]
    designers = ["marina.korneva"]
    for u in devs:
        if group_ids.get("Developers") and hub_ids.get(u):
            add_to_group(hub_ids[u], group_ids["Developers"])
    for u in qas:
        if group_ids.get("QA Engineers") and hub_ids.get(u):
            add_to_group(hub_ids[u], group_ids["QA Engineers"])
    for u in designers:
        if group_ids.get("Designers") and hub_ids.get(u):
            add_to_group(hub_ids[u], group_ids["Designers"])

    print("== projects ==")
    for short, name, leader, desc, subsys, versions in PROJECTS:
        pid = ensure_project(short, name, leader, desc)
        if not pid:
            continue
        import time; time.sleep(1.0)  # let auto-attached fields & bundles initialize
        # Populate the auto-created Subsystem (owned) and Fix versions (version)
        # bundles that YouTrack attaches to new projects with our data.
        populate_field_bundle(pid, "Subsystem", subsys, owner_login=leader, vtype="ownedField")
        populate_field_bundle(pid, "Fix versions", versions, vtype="version")
        # Attach any standard fields that weren't auto-attached.
        attach_field(pid, "Assignee", can_be_empty=True, empty_text="Unassigned")
        attach_field(pid, "Estimation")
        attach_field(pid, "Spent time")
        # issues
        existing = api("GET", f"/api/issues?query=project:{short}&fields=idReadable&$top=1")
        have_issues = ok(existing) and len(existing) > 0
        if have_issues:
            print(f"   {short}: issues exist, skipping creation")
            continue
        print(f"   {short}: creating issues")
        for summary, description, flds in gen_issues_for(short, leader):
            cfs = []
            cfs.append(fv("State", flds["State"]))
            cfs.append(fv("Priority", flds["Priority"]))
            cfs.append(fv("Type", flds["Type"]))
            cfs.append(fv("Subsystem", subsys[hash(summary) % len(subsys)]))
            cfs.append(fv("Assignee", flds["Assignee"]))
            if "Fix versions" in flds:
                cfs.append(fv("Fix versions", [flds["Fix versions"]]))
            create_issue(pid, summary, description, cfs, leader_login=leader)

    print("== done ==")
    # summary
    res = api("GET", "/api/admin/projects?fields=shortName,name&$top=50")
    if ok(res):
        print(f"   projects: {len(res)} -> {[p['shortName'] for p in res]}")
    iss = api("GET", "/api/issues?fields=idReadable&$top=1")
    print(f"   sample query ok: {ok(iss)}")


if __name__ == "__main__":
    main()
