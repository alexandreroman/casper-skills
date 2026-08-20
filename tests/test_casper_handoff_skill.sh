#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper-handoff/SKILL.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "^name: casper-handoff" "$FILE" || fail "missing name in frontmatter"
grep -q "^description:" "$FILE" || fail "missing description in frontmatter"
grep -q "CASPER_WORKSPACE_ID\|Casper terminal" "$FILE" || fail "missing guard-rule mention"
grep -q "casper workspace new <name>" "$FILE" || fail "missing casper workspace new example"
grep -q -- "--base" "$FILE" || fail "missing --base (fork from current branch) documentation"
grep -q "git rev-parse --abbrev-ref HEAD" "$FILE" || fail "missing current-branch resolution"
grep -q "WIP" "$FILE" || fail "missing WIP-commit handling for uncommitted work"
grep -q "mktemp" "$FILE" || fail "missing temp-file handoff document"
grep -q "^allowed-tools:.*casper workspace new \*" "$FILE" || fail "missing allowed-tools pre-authorization for casper workspace new"
# Every casper command the skill tells you to run must be pre-authorized.
if grep -q "casper info set" "$FILE"; then
  grep -q "^allowed-tools:.*casper info set" "$FILE" || fail "casper info set is used but not pre-authorized in allowed-tools"
fi
# No placeholder may reference a file the skill never creates.
grep -q -- "--file <note>" "$FILE" && fail "dangling <note> placeholder: no step creates that file"

echo "PASS"
