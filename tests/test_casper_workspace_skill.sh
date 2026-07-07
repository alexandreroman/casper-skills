#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper-workspace/SKILL.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "^name: casper-workspace" "$FILE" || fail "missing name in frontmatter"
grep -q "^description:" "$FILE" || fail "missing description in frontmatter"
grep -q "CASPER_WORKSPACE_ID\|Casper terminal" "$FILE" || fail "missing guard-rule mention"
grep -q "casper workspace list" "$FILE" || fail "missing casper workspace list example"
grep -q "casper workspace current" "$FILE" || fail "missing casper workspace current example"
grep -q "casper workspace new --branch" "$FILE" || fail "missing casper workspace new example"
grep -q "casper workspace delete" "$FILE" || fail "missing casper workspace delete example"
grep -q "^allowed-tools:.*casper workspace list" "$FILE" || fail "missing allowed-tools pre-authorization for casper workspace list"
grep -q "^allowed-tools:.*casper workspace current" "$FILE" || fail "missing allowed-tools pre-authorization for casper workspace current"
grep -q "^allowed-tools:.*casper workspace new \*" "$FILE" || fail "missing allowed-tools pre-authorization for casper workspace new"
grep -q "^allowed-tools:.*casper workspace delete" "$FILE" || fail "missing allowed-tools pre-authorization for casper workspace delete"

echo "PASS"
