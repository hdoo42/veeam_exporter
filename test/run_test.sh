#!/usr/bin/env bash
# Token refresh integration test wrapper.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x "./httpapi_exporter" ]]; then
  echo "ERROR: ./httpapi_exporter binary not found or not executable"
  echo "Expected path: $ROOT_DIR/httpapi_exporter"
  exit 1
fi

python3 test/test_token_refresh.py "$@"
