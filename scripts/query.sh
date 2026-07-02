#!/usr/bin/env bash
# Reference examples of YouTrack REST API calls — useful while building the CLI.
# Usage: ./scripts/query.sh [issues|issue|projects|users|fields|search|create]
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source .env
AUTH="Authorization: Bearer $YOUTRACK_TOKEN"
B="$YOUTRACK_BASE_URL"
JQ="$(command -v jq >/dev/null && echo jq || echo cat)"

get() { curl -s -H "$AUTH" "$B/$1" | $JQ; }

case "${1:-issues}" in
  issues)
    echo "# Recent issues across all projects"
    get "api/issues?\$top=5&fields=idReadable,summary,project(shortName),customFields(name,value(name,login))" ;;
  issue)
    echo "# Single issue JT-1"
    get "api/issues/JT-1?fields=idReadable,summary,description,created,project(name),customFields(name,value(name,login,minutes))" ;;
  projects)
    echo "# Projects"
    get "api/admin/projects?fields=shortName,name,leader(login),description" ;;
  users)
    echo "# Users"
    get "api/users?fields=login,fullName,email&\$top=20" ;;
  fields)
    echo "# Global custom fields"
    get "api/admin/customFieldSettings/customFields?fields=name,fieldType(valueType)" ;;
  search)
    echo "# Search: fixed issues across all projects"
    get "api/issues?query=state%3A%20Fixed&fields=idReadable,summary,project(shortName)&\$top=10" ;;
  create)
    echo "# Create an issue"
    curl -s -H "$AUTH" -H 'Content-Type: application/json' -X POST "$B/api/issues?fields=idReadable,summary" \
      --data '{"project":{"id":"0-8"},"summary":"CLI test issue","description":"created via REST","customFields":[{"$type":"StateIssueCustomField","name":"State","value":{"$type":"StateBundleElement","name":"Open"}},{"$type":"SingleEnumIssueCustomField","name":"Priority","value":{"$type":"EnumBundleElement","name":"Major"}},{"$type":"SingleEnumIssueCustomField","name":"Type","value":{"$type":"EnumBundleElement","name":"Task"}}]}' | $JQ ;;
  *) echo "usage: $0 [issues|issue|projects|users|fields|search|create]"; exit 1 ;;
esac
