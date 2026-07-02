#!/usr/bin/env bash
# One-shot setup: install Apple Container, run YouTrack, complete the wizard
# headlessly, mint an API token, and provision realistic JetBrains-style data.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE=jetbrains/youtrack:2026.2.17012
NAME=youtrack
HOST_PORT=8080
ADMIN_PW='Yt-Admin-2026!'
BASE="$(pwd)/.youtrack-server"
CONTAINER=/opt/homebrew/bin/container

echo "==> 1/6  Apple Container"
if ! command -v container >/dev/null 2>&1 && [ ! -x "$CONTAINER" ]; then
  brew install container
fi
"$CONTAINER" system start >/dev/null 2>&1 || true
"$CONTAINER" system kernel set --recommended >/dev/null 2>&1 || true

echo "==> 2/6  Data directories"
mkdir -p -m 777 "$BASE"/{data,conf,logs,backups}

echo "==> 3/6  YouTrack container (image is ~3 GB on first run)"
if "$CONTAINER" list 2>/dev/null | awk '$1=="'"$NAME"'"{found=1} END{exit !found}'; then
  echo "      container already exists"
else
  "$CONTAINER" run -d --name "$NAME" -p ${HOST_PORT}:8080 \
    -v "$BASE/data:/opt/youtrack/data" -v "$BASE/conf:/opt/youtrack/conf" \
    -v "$BASE/logs:/opt/youtrack/logs" -v "$BASE/backups:/opt/youtrack/backups" \
    --cpus 4 -m 4G "$IMAGE"
fi

echo "==> 4/6  Configure (wizard → admin password → token)"
python3 scripts/configure.py

echo "==> 5/6  Wait for YouTrack service"
for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${HOST_PORT}/api/users/me" || true)
  { [ "$code" = "200" ] || [ "$code" = "401" ] || [ "$code" = "403" ]; } && break
  sleep 5
done

echo "==> 6/6  Provision seed data"
python3 scripts/provision.py
python3 scripts/provision_jewel.py   # apply the youtrack.jetbrains.com field schema
python3 scripts/provision_enrichment.py  # add comments/links for workflow variety

echo
echo "✓ Done. YouTrack: http://localhost:${HOST_PORT}  (admin / $ADMIN_PW)"
echo "  Token & config in .env"
