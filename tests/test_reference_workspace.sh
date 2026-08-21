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

# A reader who stops early must still read correctly. These three facts each
# change what a command can do, and each was got wrong by an agent that had
# the file open, so they belong before the long procedures rather than after.
head -n 30 "$FILE" | grep -q "There is no .casper workspace close. subcommand" \
  || fail "the absent close subcommand must be stated in the first 30 lines"
head -n 30 "$FILE" | grep -q -- "--workspace" \
  || fail "--workspace must be introduced in the first 30 lines, not only in a trailing section"
grep -q -- "casper workspace new <branch> \[--base <ref>\] \[--command <cmd>\] \[--workspace <id-or-name>\]" "$FILE" \
  || fail "the new synopsis must match the CLI exactly, --workspace included"

echo "PASS"
