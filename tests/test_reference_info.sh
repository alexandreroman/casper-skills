#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper/references/info.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "casper info set --message" "$FILE" || fail "missing casper info set --message example"
grep -q "casper info set --file" "$FILE" || fail "missing casper info set --file example"
grep -qE "casper info set -( |$)" "$FILE" || fail "missing stdin form of casper info set"
grep -q "casper info clear" "$FILE" || fail "missing casper info clear example"
grep -q -- "--workspace" "$FILE" || fail "missing per-workspace targeting documentation"
grep -qi "overwrite\|replace" "$FILE" || fail "missing replace-not-append semantics"
grep -qi "not persist\|in-memory\|does not survive" "$FILE" || fail "missing non-persistence warning"
grep -qi "restart" "$FILE" || fail "missing Casper-restart consequence of non-persistence"

echo "PASS"
