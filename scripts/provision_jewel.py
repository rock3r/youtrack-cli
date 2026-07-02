#!/usr/bin/env python3
"""
Apply the exact custom-field schema from the official JetBrains YouTrack instance
(the "Jewel" project on youtrack.jetbrains.com) to every project.

Field layout mirrored (top-to-bottom):
  Priority            enum[1]    required, default Normal
  Type                enum[1]    required
  State               state[1]   required, default Submitted
  Subsystems          enum[*]    multi, "No Subsystems"
  Assignee            user[1]    "Unassigned"
  Target version      version[1] required, default Backlog
  Included in builds  build[*]   multi, "No included in builds"
  Available in        version[*] multi, "No available in"
  Security Severity   enum[1]    "None"
  Security Problem Type enum[1]  default Vulnerability
  QA                  user[1]    hidden, "No qa"
  Verified            enum[1]    "No verified"
  Verified in builds  build[*]   multi, "No verified in builds"

Idempotent. Reads config from ../.env.
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
    for line in open(env):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()
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
        return {"__error__": True, "status": e.code,
                "body": json.loads(e.read().decode() or "{}"), "url": url, "method": method}


def ok(r):
    return not (isinstance(r, dict) and r.get("__error__"))


def err(r):
    print(f"  !! {r['method']} {r['url']} -> {r['status']}: {json.dumps(r['body'])[:200]}", file=sys.stderr)


BUNDLE_TYPE = {"enum": "EnumBundle", "state": "StateBundle", "version": "VersionBundle",
               "build": "BuildBundle", "ownedField": "OwnedBundle"}
BUNDLE_PATH = {"enum": "enum", "state": "state", "version": "version", "build": "build",
               "ownedField": "ownedField"}
# project field $type — YouTrack uses the BASE name for both single and multi
# (the field's own fieldType encodes [1] vs [*]).
PFIELD_TYPE = {
    "enum[1]": "EnumProjectCustomField", "enum[*]": "EnumProjectCustomField",
    "state[1]": "StateProjectCustomField",
    "user[1]": "UserProjectCustomField", "user[*]": "UserProjectCustomField",
    "version[1]": "VersionProjectCustomField", "version[*]": "VersionProjectCustomField",
    "build[1]": "BuildProjectCustomField", "build[*]": "BuildProjectCustomField",
}
# element $type for defaultValues / bundle values by bundle type
EL_TYPE = {"enum": "EnumBundleElement", "state": "StateBundleElement",
           "version": "VersionBundleElement", "build": "BuildBundleElement",
           "ownedField": "OwnedBundleElement"}


def load_fields():
    res = api("GET", "/api/admin/customFieldSettings/customFields?fields=id,name,fieldType(id)&$top=100")
    return {f["name"]: f for f in (res or [])}


FIELDS = {}


def ensure_field(name, ftype):
    if name in FIELDS:
        return FIELDS[name]["id"]
    r = api("POST", "/api/admin/customFieldSettings/customFields?fields=id,name,fieldType(id)",
            {"fieldType": {"id": ftype}, "name": name, "isPublic": True,
             "isDisplayedInIssueList": True, "isAutoAttached": False})
    if ok(r):
        FIELDS[name] = r
        print(f"  + field '{name}' ({ftype}) -> {r['id']}")
        return r["id"]
    err(r)
    return None


def ensure_bundle(btype, name, values, per_project_owner=None):
    """Create a bundle with values (idempotent). Returns bundle id."""
    path = BUNDLE_PATH[btype]
    existing = api("GET", f"/api/admin/customFieldSettings/bundles/{path}?fields=id,name&$top=200")
    for b in (existing or []):
        if b["name"] == name:
            bid = b["id"]
            cur = api("GET", f"/api/admin/customFieldSettings/bundles/{path}/{bid}?fields=values(name)&$top=200")
            have = {v["name"] for v in (cur.get("values", []) if ok(cur) else [])}
            for v in values:
                if v not in have:
                    body = {"name": v}
                    if btype == "ownedField" and per_project_owner:
                        body["owner"] = {"login": per_project_owner}
                    api("POST", f"/api/admin/customFieldSettings/bundles/{path}/{bid}/values?fields=id", body)
            return bid
    body = {"name": name}
    if values:
        if btype == "ownedField":
            body["values"] = [{"name": v, "owner": {"login": per_project_owner}} for v in values]
        else:
            body["values"] = [{"name": v} for v in values]
    r = api("POST", f"/api/admin/customFieldSettings/bundles/{path}?fields=id,name", body)
    if ok(r):
        return r["id"]
    # Likely "not unique" (YouTrack dedupes bundles by content) — find it.
    existing = api("GET", f"/api/admin/customFieldSettings/bundles/{path}?fields=id,name&$top=200")
    for b in (existing or []):
        if b["name"] == name:
            return b["id"]
    err(r)
    return None


# ----- Jewel field spec -----
# Each: name, ftype, bundle_type(None if user), bundle_kind 'global'|'project',
#       bundle_name_template, values(or fn), can_be_empty, empty_text, default, visible
GLOBAL_ENUMS = {
    "Security Severities": ["Critical", "High", "Medium", "Low"],
    "Security Problem Types": ["Vulnerability", "Bug", "Misconfiguration",
                               "Privilege Escalation", "Information Disclosure", "Denial of Service"],
    "Verified States": ["Unverified", "Verified"],
}

# per-project build numbers
BUILDS = ["2026.2.17012", "2026.2.16593", "2026.1.13757"]


def project_field_config(pid, short, leader):
    """Return list of field specs for a project."""
    versions = ["Backlog", "2026.2", "2026.3", "2027.1"]
    return [
        dict(name="Priority", ftype="enum[1]", btype="enum", kind="global",
             bundle="Priorities", can_be_empty=False, empty="No Priority", default="Normal", visible=True),
        dict(name="Type", ftype="enum[1]", btype="enum", kind="global",
             bundle="Types", can_be_empty=False, empty="No Type", default=None, visible=True),
        dict(name="State", ftype="state[1]", btype="state", kind="global",
             bundle="States", can_be_empty=False, empty="No State", default="Submitted", visible=True),
        dict(name="Subsystems", ftype="enum[*]", btype="enum", kind="project",
             bundle=f"{short}: Subsystems", can_be_empty=True, empty="No Subsystems",
             default=None, visible=True),
        dict(name="Assignee", ftype="user[1]", btype=None, kind="global", bundle=None,
             can_be_empty=True, empty="Unassigned", default=None, visible=True),
        dict(name="Target version", ftype="version[1]", btype="version", kind="project",
             bundle=f"{short}: Target versions", can_be_empty=False, empty="No target version",
             default="Backlog", visible=True),
        dict(name="Included in builds", ftype="build[*]", btype="build", kind="project",
             bundle=f"{short}: Builds", can_be_empty=True, empty="No included in builds",
             default=None, visible=True),
        dict(name="Available in", ftype="version[*]", btype="version", kind="project",
             bundle=f"{short}: Target versions", can_be_empty=True, empty="No available in",
             default=None, visible=True),
        dict(name="Security Severity", ftype="enum[1]", btype="enum", kind="global",
             bundle="Security Severities", can_be_empty=True, empty="None",
             default=None, visible=True),
        dict(name="Security Problem Type", ftype="enum[1]", btype="enum", kind="global",
             bundle="Security Problem Types", can_be_empty=True, empty="No security problem type",
             default="Vulnerability", visible=True),
        dict(name="QA", ftype="user[1]", btype=None, kind="global", bundle=None,
             can_be_empty=True, empty="No qa", default=None, visible=False),
        dict(name="Verified", ftype="enum[1]", btype="enum", kind="global",
             bundle="Verified States", can_be_empty=True, empty="No verified",
             default=None, visible=True),
        dict(name="Verified in builds", ftype="build[*]", btype="build", kind="project",
             bundle=f"{short}: Builds", can_be_empty=True, empty="No verified in builds",
             default=None, visible=True),
    ]


def project_fields(pid):
    res = api("GET", f"/api/admin/projects/{pid}/customFields?fields=id,field(name)&$top=100")
    return {cf["field"]["name"]: cf["id"] for cf in (res or [])}


def attach(pid, spec, bundle_id):
    name = spec["name"]
    ftype = spec["ftype"]
    body = {
        "$type": PFIELD_TYPE[ftype],
        "field": {"$type": "CustomField", "id": FIELDS[name]["id"]},
        "canBeEmpty": spec["can_be_empty"],
        "emptyFieldText": spec["empty"],
        "isDisplayedInIssueList": spec["visible"],
    }
    if bundle_id:
        body["bundle"] = {"$type": BUNDLE_TYPE[spec["btype"]], "id": bundle_id}
    r = api("POST", f"/api/admin/projects/{pid}/customFields?fields=id", body)
    if not ok(r):
        err(r)
    return r.get("id") if ok(r) else None


def update(pid, cfid, spec, bundle_id):
    # Only update safe attributes (defaults require element ids on update — skip).
    body = {
        "canBeEmpty": spec["can_be_empty"],
        "emptyFieldText": spec["empty"],
        "isDisplayedInIssueList": spec["visible"],
    }
    if bundle_id:
        body["bundle"] = {"$type": BUNDLE_TYPE[spec["btype"]], "id": bundle_id}
    r = api("POST", f"/api/admin/projects/{pid}/customFields/{cfid}?fields=id", body)
    if not ok(r):
        err(r)


def main():
    global FIELDS
    print("== Jewel field schema ==")
    FIELDS = load_fields()
    print(f"   existing global fields: {len(FIELDS)}")

    # ensure global enum bundles + their fields
    ensure_bundle("enum", "Security Severities", GLOBAL_ENUMS["Security Severities"])
    ensure_bundle("enum", "Security Problem Types", GLOBAL_ENUMS["Security Problem Types"])
    ensure_bundle("enum", "Verified States", GLOBAL_ENUMS["Verified States"])

    # ensure all global fields exist
    for spec in project_field_config("0-0", "X", "admin"):
        ensure_field(spec["name"], spec["ftype"])

    projects = api("GET", "/api/admin/projects?fields=id,shortName,name,leader(login)&$top=50")
    for p in (projects or []):
        if p["shortName"] == "DEMO":
            continue
        short, pid, leader = p["shortName"], p["id"], (p.get("leader") or {}).get("login", "admin")
        print(f"-- {short} ({p['name']})")
        specs = project_field_config(pid, short, leader)
        # per-project bundles
        subsys = SUBSYSTEMS.get(short, SUBSYSTEMS["default"])
        ensure_bundle("enum", f"{short}: Subsystems", subsys)
        ensure_bundle("version", f"{short}: Target versions", ["Backlog", "2026.2", "2026.3", "2027.1"])
        ensure_bundle("build", f"{short}: Builds", BUILDS)
        attached = project_fields(pid)
        for spec in specs:
            bid = ensure_bundle(spec["btype"], spec["bundle"], []) if spec["btype"] else None
            if spec["name"] in attached:
                update(pid, attached[spec["name"]], spec, bid)
            else:
                attach(pid, spec, bid)
    print("== done ==")


SUBSYSTEMS = {
    "JT": ["Agile Boards", "API & REST", "Workflows", "Search", "Notifications", "UI", "Import", "Reports"],
    "IJPL": ["Editor", "VCS", "Build System", "Debugger", "Indexing", "Plugins", "UI"],
    "IDEA": ["Java", "Kotlin", "Maven", "Gradle", "Code Inspection", "UI"],
    "KT": ["Compiler", "Scripting", "Debugger", "Refactorings", "Android"],
    "RID": ["C# Support", "NuGet", "Unity", "Debugger", "ASP.NET"],
    "WEB": ["TypeScript", "Vue", "React", "CSS", "Node.js", "Debugger"],
    "PY": ["Python", "Django", "Scientific", "Debugger", "Type Checking"],
    "default": ["Backend", "Frontend", "Infrastructure", "Documentation", "Tests", "UI"],
}


if __name__ == "__main__":
    main()
