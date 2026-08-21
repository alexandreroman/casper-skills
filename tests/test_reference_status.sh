#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper/references/status.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "casper status set blocked" "$FILE" || fail "missing blocked example"
grep -q "casper status set error" "$FILE" || fail "missing error example"

echo "PASS"
