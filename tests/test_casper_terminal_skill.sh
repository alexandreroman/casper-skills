#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper-terminal/SKILL.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "^name: casper-terminal" "$FILE" || fail "missing name in frontmatter"
grep -q "^description:" "$FILE" || fail "missing description in frontmatter"
grep -q "CASPER_WORKSPACE_ID\|Casper terminal" "$FILE" || fail "missing guard-rule mention"
grep -q "casper terminal new" "$FILE" || fail "missing casper terminal new example"
grep -q "casper terminal list" "$FILE" || fail "missing casper terminal list example"
grep -q "casper terminal close" "$FILE" || fail "missing casper terminal close example"
grep -q "^allowed-tools:.*casper terminal new \*" "$FILE" || fail "missing allowed-tools pre-authorization for casper terminal new"
grep -q "^allowed-tools:.*casper terminal list" "$FILE" || fail "missing allowed-tools pre-authorization for casper terminal list"
grep -q "^allowed-tools:.*casper terminal close \*" "$FILE" || fail "missing allowed-tools pre-authorization for casper terminal close"

echo "PASS"
