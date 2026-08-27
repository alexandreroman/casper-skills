#!/usr/bin/env bash
# The trivial hooks stay Bash for speed on the PreToolUse hot path. This
# asserts they emit exactly what EVENT_ACTIONS says, so the fast path can
# never drift from the policy table.
#
# `turn-end` is absent here because it is absent from the table: what a turn
# ending emits depends on what the workspace is showing, which hooks/stop.py
# reads back before it decides. tests/test_stop.py covers it, and
# tests/test_cross_agent_conformance.sh pins it against the opencode plugin.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/tests/lib/harness.sh"

check() {
  local script="$1" event="$2"
  local expected
  expected="$(cd "$DIR" && python3 -c "
from hooks.lib.casper import EVENT_ACTIONS
print('\n'.join(' '.join(a) for a in EVENT_ACTIONS['$event']))
")"
  casper_stub_init
  "$DIR/hooks/$script" </dev/null
  assert_casper_calls "$expected"
  echo "  ok: $script == EVENT_ACTIONS[$event]"
}

check user-prompt-submit.sh turn-start
check pre-tool-use.sh       tool-activity
check session-end.sh        session-end
echo "PASS"
