#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/tests/lib/harness.sh"

casper_stub_init
"$DIR/hooks/session-end.sh"
# Session end is the backstop for a bar the agent drove by hand: turn end
# leaves that one standing, so this is where it stops.
assert_casper_calls "status set done
progress clear"
echo "PASS"
