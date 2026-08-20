#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
. "$DIR/tests/lib/harness.sh"

casper_stub_init
casper status set working
casper progress clear
assert_casper_calls $'status set working\nprogress clear'
echo "PASS"
