#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper/references/diff.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "casper diff open" "$FILE" || fail "missing casper diff open example"
grep -q "casper diff close" "$FILE" || fail "missing casper diff close example"

echo "PASS"
