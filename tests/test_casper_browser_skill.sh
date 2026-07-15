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
grep -q "casper browser close" "$FILE" || fail "missing casper browser close example"
grep -q "^allowed-tools:.*casper browser \*" "$FILE" || fail "missing allowed-tools pre-authorization for casper browser subcommands"
# Development helper tools for coding agents
for sub in screenshot console eval content click type wait reload load; do
  grep -q "casper browser $sub" "$FILE" || fail "missing casper browser $sub reference"
done
grep -qi "verify" "$FILE" || fail "missing verification framing for coding agents"

echo "PASS"
