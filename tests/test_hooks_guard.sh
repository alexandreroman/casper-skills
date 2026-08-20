#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/tests/lib/harness.sh"

casper_stub_init

GUARDED_CMD="[ -n \"\$CASPER_WORKSPACE_ID\" ] && ${DIR}/hooks/session-start.py || true"

# Case 1: no CASPER_WORKSPACE_ID -> must not call casper
env -u CASPER_WORKSPACE_ID bash -c "$GUARDED_CMD" </dev/null
if [ -s "$CASPER_LOG" ]; then
  echo "FAIL: casper was called without CASPER_WORKSPACE_ID set"
  exit 1
fi

# Case 2: CASPER_WORKSPACE_ID set -> must call casper
bash -c "$GUARDED_CMD" </dev/null
if [ ! -s "$CASPER_LOG" ]; then
  echo "FAIL: casper was not called with CASPER_WORKSPACE_ID set"
  exit 1
fi

echo "PASS"
