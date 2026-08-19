#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper-info/SKILL.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "^name: casper-info" "$FILE" || fail "missing name in frontmatter"
grep -q "^description:" "$FILE" || fail "missing description in frontmatter"
grep -q "^user-invocable: false" "$FILE" || fail "skill must be model-only"
grep -q "CASPER_WORKSPACE_ID\|Casper terminal" "$FILE" || fail "missing guard-rule mention"
grep -q "casper info set --message" "$FILE" || fail "missing casper info set --message example"
grep -q "casper info set --file" "$FILE" || fail "missing casper info set --file example"
grep -qE "casper info set -( |$)" "$FILE" || fail "missing stdin form of casper info set"
grep -q "casper info clear" "$FILE" || fail "missing casper info clear example"
grep -q -- "--workspace" "$FILE" || fail "missing per-workspace targeting documentation"
grep -qi "overwrite\|replace" "$FILE" || fail "missing replace-not-append semantics"
grep -qi "not persist\|in-memory\|does not survive" "$FILE" || fail "missing non-persistence warning"
grep -qi "restart" "$FILE" || fail "missing Casper-restart consequence of non-persistence"
grep -q "^allowed-tools:.*casper info set" "$FILE" || fail "missing allowed-tools pre-authorization for casper info set"
grep -q "^allowed-tools:.*casper info clear" "$FILE" || fail "missing allowed-tools pre-authorization for casper info clear"

echo "PASS"
