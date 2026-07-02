#!/usr/bin/env bash
# Manage the local YouTrack instance running in Apple Container.
# Usage: ./scripts/youtrack.sh {start|stop|status|logs|restart|url|reset-data}
set -euo pipefail

CONTAINER=/opt/homebrew/bin/container
NAME=youtrack
IMAGE=jetbrains/youtrack:2026.2.17012
BASE="$(cd "$(dirname "$0")/.." && pwd)/.youtrack-server"
HOST_PORT=8080

running() { "$CONTAINER" list 2>/dev/null | awk -v n="$NAME" '$1==n && $5=="running"{found=1} END{exit !found}'; }

case "${1:-help}" in
  start)
    if running; then echo "✓ $NAME already running"; else
      # exists but stopped? resume it; otherwise create fresh.
      exists=$("$CONTAINER" list 2>/dev/null | awk -v n="$NAME" '$1==n{print $1}')
      if [ -n "$exists" ]; then
        echo "› resuming $NAME …"
        "$CONTAINER" start "$NAME" >/dev/null
      else
        echo "› starting $NAME …"
        "$CONTAINER" run -d --name "$NAME" -p ${HOST_PORT}:8080 \
          -v "$BASE/data:/opt/youtrack/data" \
          -v "$BASE/conf:/opt/youtrack/conf" \
          -v "$BASE/logs:/opt/youtrack/logs" \
          -v "$BASE/backups:/opt/youtrack/backups" \
          --cpus 4 -m 4G "$IMAGE" >/dev/null
      fi
      echo "✓ started — waiting for service…"
      for i in $(seq 1 60); do
        code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${HOST_PORT}/api/users/me" || true)
        { [ "$code" = "200" ] || [ "$code" = "401" ] || [ "$code" = "403" ]; } && { echo "✓ YouTrack is up at http://localhost:${HOST_PORT}"; exit 0; }
        sleep 5
      done
      echo "⚠ service still warming up — check: $0 logs"
    fi
    ;;
  stop)
    "$CONTAINER" stop "$NAME" 2>/dev/null && echo "✓ stopped $NAME" || echo "• $NAME not running"
    ;;
  restart)
    "$0" stop || true; "$0" start
    ;;
  status)
    "$CONTAINER" list 2>/dev/null | awk 'NR==1 || $1=="'"$NAME"'"'
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${HOST_PORT}/api/users/me" || true)
    echo "http://localhost:${HOST_PORT}/api/users/me -> HTTP $code"
    ;;
  logs)
    "$CONTAINER" logs "$NAME" "${2:-50}" 2>&1 | tail -n "${2:-50}"
    ;;
  url)
    echo "http://localhost:${HOST_PORT}"
    ;;
  shell)
    "$CONTAINER" exec -it "$NAME" /bin/bash
    ;;
  reset-data)
    echo "This deletes ALL YouTrack data and forces a fresh setup. Continue? [y/N]"
    read -r r; [ "$r" = "y" ] || { echo "aborted"; exit 0; }
    "$CONTAINER" stop "$NAME" 2>/dev/null || true
    "$CONTAINER" delete "$NAME" 2>/dev/null || true
    rm -rf "$BASE"/{data,conf,logs,backups}
    mkdir -p -m 777 "$BASE"/{data,conf,logs,backups}
    echo "✓ data wiped. Run: $0 start   then re-run the wizard/provision."
    ;;
  *)
    cat <<EOF
YouTrack (Apple Container) helper

  start        Start the YouTrack container (pulls image if needed)
  stop         Stop the container
  restart      Stop then start
  status       Show container + HTTP health
  logs [N]     Show last N log lines (default 50)
  url          Print the base URL
  shell        Open a shell inside the container
  reset-data   ⚠ Wipe all data (fresh install)

Base URL : http://localhost:${HOST_PORT}
Admin    : admin / Yt-Admin-2026!
Data dir : $BASE
EOF
    ;;
esac
