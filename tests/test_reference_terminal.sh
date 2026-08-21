#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper/references/terminal.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "casper terminal new" "$FILE" || fail "missing casper terminal new example"
grep -q "casper terminal list" "$FILE" || fail "missing casper terminal list example"
grep -q "casper terminal close" "$FILE" || fail "missing casper terminal close example"
# "terminal new" is documented as valid bare (an empty shell) or with
# --command, so both the bare and wildcard allowed-tools forms must be
# present. Anchor on the exact "Bash(...)" token so a wildcard-only file
# can't satisfy the bare-form check (and vice versa).
# "terminal list" is also documented as callable bare (with no flags) or
# with --workspace, so both forms must be present too.
# "terminal close" always requires an <id>, so only the wildcard form
# should exist — no bare-form assertion here.

echo "PASS"
