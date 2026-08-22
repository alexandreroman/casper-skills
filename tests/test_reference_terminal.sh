#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper/references/terminal.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "casper terminal new" "$FILE" || fail "missing casper terminal new example"
grep -q "casper terminal list" "$FILE" || fail "missing casper terminal list example"
grep -q "casper terminal close" "$FILE" || fail "missing casper terminal close example"
echo "PASS"
