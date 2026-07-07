#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper-diff/SKILL.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "^name: casper-diff" "$FILE" || fail "missing name in frontmatter"
grep -q "^description:" "$FILE" || fail "missing description in frontmatter"
grep -q "CASPER_WORKSPACE_ID\|Casper terminal" "$FILE" || fail "missing guard-rule mention"
grep -q "casper diff open" "$FILE" || fail "missing casper diff open example"
grep -q "^allowed-tools:.*casper diff open" "$FILE" || fail "missing allowed-tools pre-authorization for casper diff open"

echo "PASS"
