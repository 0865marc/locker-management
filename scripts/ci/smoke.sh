#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."
project="${CI_SMOKE_PROJECT:-backend-ci-$(date +%s)-${RANDOM}-$$}"
if [[ ! "$project" =~ ^backend-ci-[a-z0-9-]+$ ]]; then
  echo "CI_SMOKE_PROJECT must start with backend-ci- and contain lowercase letters, digits or hyphens." >&2
  exit 2
fi
compose=(docker compose --project-name "$project" -f compose.yaml -f compose.ci.yaml)
docker info > /dev/null

# Refuse to adopt any existing stack, including an earlier interrupted smoke.
if [[ -n "$(docker ps -aq --filter "label=com.docker.compose.project=$project")" ||
      -n "$(docker volume ls -q --filter "label=com.docker.compose.project=$project")" ||
      -n "$(docker network ls -q --filter "label=com.docker.compose.project=$project")" ]]; then
  echo "Compose project already exists: $project; refusing to touch it." >&2
  exit 2
fi

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  if (( status != 0 )); then
    "${compose[@]}" ps --all || true
    "${compose[@]}" logs --no-color --tail 200 api migrate db rabbitmq || true
  fi
  echo "Cleaning disposable Compose project: $project"
  if ! "${compose[@]}" down --volumes --remove-orphans --timeout 10; then
    echo "Cleanup failed for $project" >&2
    status=1
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "Docker smoke project: $project"
"${compose[@]}" build api migrate
"${compose[@]}" up --detach --wait --wait-timeout 120 api
"${compose[@]}" exec -T api python - <<'PY'
import json
import time
import urllib.error
import urllib.request

deadline = time.monotonic() + 60
last_error = "No response received"
while time.monotonic() < deadline:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/lockers", timeout=3) as response:
            status = response.status
            body = json.load(response)
        if status != 200 or body != []:
            raise SystemExit(f"Unexpected GET /lockers: HTTP {status}, body={body!r}")
        print("GET /lockers: HTTP 200, []")
        break
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        last_error = str(error)
        time.sleep(1)
else:
    raise SystemExit(f"GET /lockers did not succeed within 60 seconds: {last_error}")
PY
