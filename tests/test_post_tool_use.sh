#!/usr/bin/env bash
# With no dialog marker standing — every tool call but a dialog's own — the
# hook stays on its Bash fast path and calls nothing. tests/test_blocked.py
# covers the marker side.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/tests/lib/harness.sh"

casper_stub_init
echo '{"session_id":"s","tool_name":"Bash","tool_input":{"command":"ls"}}' |
  CLAUDE_PLUGIN_DATA="$(mktemp -d)" "$DIR/hooks/post-tool-use.sh"
assert_casper_calls ""
echo "PASS"
