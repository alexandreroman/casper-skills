#!/usr/bin/env bash
# The four trivial hooks stay Bash for speed on the PreToolUse hot path.
# This asserts they emit exactly what EVENT_ACTIONS says, so the fast path
# can never drift from the policy table.
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
check stop.sh               turn-end
check session-end.sh        session-end
echo "PASS"
