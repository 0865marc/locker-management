#!/usr/bin/env bash
# Default is the complete native check. --d1-only is supplemental evidence only.
set -euo pipefail
cd "$(dirname "$0")/../.."
mode="${1:-full}"
if [[ "$mode" != "full" && "$mode" != "--d1-only" ]]; then
  echo 'Usage: scripts/cloudflare/check.sh [--d1-only]' >&2
  exit 2
fi
export WRANGLER_SEND_METRICS=false
export PYTHONPATH="$PWD/backend:$PWD/cloudflare/tests:$PWD/scripts/cloudflare${PYTHONPATH:+:$PYTHONPATH}"
python_bin="$PWD/cloudflare/.venv/bin/python"
if [[ ! -x "$python_bin" ]]; then
  echo 'Install the locked Cloudflare dependencies: uv sync --project cloudflare --locked' >&2
  exit 1
fi
"$python_bin" scripts/cloudflare/prepare.py --check
if [[ ! -d cloudflare/node_modules/miniflare ]]; then
  echo 'Install Cloudflare Node dependencies with npm ci --ignore-scripts first.' >&2
  exit 1
fi
for required in test_d1_schema.py test_d1_repositories.py test_d1_quotations.py test_cloudflare_http.py test_acceptance.py test_schema_guard.py; do
  if [[ ! -f "cloudflare/tests/$required" ]]; then
    echo "Required Cloudflare contract test missing: $required" >&2
    exit 1
  fi
done
echo 'Supplemental tier: CPython production adapters against Miniflare/workerd D1.'
"$python_bin" -m unittest discover -s cloudflare/tests/test_support -p 'test_*.py' -v
"$python_bin" -m unittest discover -s cloudflare/tests -p 'test_d1_*.py' -v
"$python_bin" -m unittest discover -s cloudflare/tests -p test_cloudflare_http.py -v
"$python_bin" -m unittest discover -s cloudflare/tests -p test_acceptance.py -v
"$python_bin" -m unittest discover -s cloudflare/tests -p test_schema_guard.py -v
if [[ "$mode" == '--d1-only' ]]; then
  echo 'Supplemental D1 tier passed. Python Workers/Queues and Free acceptance are NOT verified.'
  exit 0
fi
echo 'Required native tier: Python Workers runtime and official Queues delivery.'
"$python_bin" cloudflare/tests/run_spike.py
if [[ ! -f cloudflare/tests/run_runtime.py ]]; then
  echo 'Production Python Workers contract harness unavailable; full Cloudflare check remains blocked.' >&2
  exit 1
fi
"$python_bin" cloudflare/tests/run_runtime.py
