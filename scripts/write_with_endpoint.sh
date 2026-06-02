#!/usr/bin/env bash
# Start a Together dedicated endpoint, run write.py, then stop the endpoint.
# Requires the Together CLI (`tg`) and TOGETHER_DEDICATED_ENDPOINT_ID in .env.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

ENDPOINT_ID="${TOGETHER_DEDICATED_ENDPOINT_ID:-}"
if [[ -z "$ENDPOINT_ID" ]]; then
  echo "[write_with_endpoint] TOGETHER_DEDICATED_ENDPOINT_ID is not set in .env" >&2
  exit 1
fi

if ! command -v tg >/dev/null 2>&1; then
  echo "[write_with_endpoint] Together CLI (tg) not found. Install it or run: python write.py" >&2
  exit 1
fi

echo "[write_with_endpoint] Starting $ENDPOINT_ID"
tg endpoints start "$ENDPOINT_ID" --wait

cleanup() {
  echo "[write_with_endpoint] Stopping $ENDPOINT_ID"
  tg endpoints stop "$ENDPOINT_ID" --wait || echo "[write_with_endpoint] Warning: stop failed" >&2
}
trap cleanup EXIT

export TOGETHER_SKIP_ENDPOINT_MANAGEMENT=1
python write.py "$@"
