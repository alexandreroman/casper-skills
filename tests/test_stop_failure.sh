#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/tests/lib/harness.sh"

casper_stub_init
"$DIR/hooks/stop-failure.sh"
# The state and nothing else. StopFailure runs instead of Stop, so the bar is
# left where the work stopped rather than reconciled here — a turn the API
# killed is paused part-way through a step, not finished with it.
assert_casper_calls "status set error"

# The payload carries the error type and the rendered message, but nothing
# here reads them: every StopFailure means the same thing to the sidebar, so
# a payload that never arrives must not cost the report.
casper_stub_init
"$DIR/hooks/stop-failure.sh" </dev/null
assert_casper_calls "status set error"
echo "PASS"
