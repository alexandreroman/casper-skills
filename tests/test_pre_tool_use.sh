#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/tests/lib/harness.sh"

casper_stub_init
"$DIR/hooks/pre-tool-use.sh"
assert_casper_calls "status set working"
echo "PASS"
