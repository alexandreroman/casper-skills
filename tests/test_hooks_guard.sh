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

# Case 3: the real SessionStart command, run through a shell exactly as an
# agent runs it, with only Codex's own name for the plugin root exported. The
# compatibility mirror CLAUDE_PLUGIN_ROOT is what the command names first, so
# this is the case that proves the fallback is not decorative.
REAL_CMD="$(cd "$DIR" && python3 -c "
import json
hooks = json.load(open('hooks/hooks.json'))['hooks']
print(hooks['SessionStart'][0]['hooks'][0]['command'])
")"

casper_stub_init
env -u CLAUDE_PLUGIN_ROOT PLUGIN_ROOT="$DIR" sh -c "$REAL_CMD" </dev/null
if [ ! -s "$CASPER_LOG" ]; then
  echo "FAIL: the SessionStart command did not resolve through PLUGIN_ROOT"
  exit 1
fi

echo "PASS"
