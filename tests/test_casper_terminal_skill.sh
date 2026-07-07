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
# "terminal new" is documented as valid bare (an empty shell) or with
# --command, so both the bare and wildcard allowed-tools forms must be
# present. Anchor on the exact "Bash(...)" token so a wildcard-only file
# can't satisfy the bare-form check (and vice versa).
grep -q "^allowed-tools:.*Bash(casper terminal new)" "$FILE" || fail "missing allowed-tools pre-authorization for bare casper terminal new"
grep -q "^allowed-tools:.*Bash(casper terminal new \*)" "$FILE" || fail "missing allowed-tools pre-authorization for casper terminal new *"
# "terminal list" is also documented as callable bare (with no flags) or
# with --workspace, so both forms must be present too.
grep -q "^allowed-tools:.*Bash(casper terminal list)" "$FILE" || fail "missing allowed-tools pre-authorization for bare casper terminal list"
grep -q "^allowed-tools:.*Bash(casper terminal list \*)" "$FILE" || fail "missing allowed-tools pre-authorization for casper terminal list *"
# "terminal close" always requires an <id>, so only the wildcard form
# should exist — no bare-form assertion here.
grep -q "^allowed-tools:.*Bash(casper terminal close \*)" "$FILE" || fail "missing allowed-tools pre-authorization for casper terminal close"

echo "PASS"
