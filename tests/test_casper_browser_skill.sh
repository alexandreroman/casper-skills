#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper-browser/SKILL.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "^name: casper-browser" "$FILE" || fail "missing name in frontmatter"
grep -q "^description:" "$FILE" || fail "missing description in frontmatter"
grep -q "CASPER_WORKSPACE_ID\|Casper terminal" "$FILE" || fail "missing guard-rule mention"
grep -q "casper browser open" "$FILE" || fail "missing casper browser open example"

echo "PASS"
