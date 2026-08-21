#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper/references/workspace.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "casper workspace list" "$FILE" || fail "missing casper workspace list example"
grep -q "casper workspace current" "$FILE" || fail "missing casper workspace current example"
grep -q "casper workspace new <name>" "$FILE" || fail "missing casper workspace new example"
grep -q -- "--command" "$FILE" || fail "missing --command documentation"
grep -q "casper workspace delete" "$FILE" || fail "missing casper workspace delete example"

echo "PASS"
