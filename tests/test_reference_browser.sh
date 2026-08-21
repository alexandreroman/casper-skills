#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper/references/browser.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "casper browser open" "$FILE" || fail "missing casper browser open example"
grep -q "casper browser close" "$FILE" || fail "missing casper browser close example"
# Development helper tools for coding agents
for sub in screenshot console eval content click type wait reload load scroll-down scroll-up scroll-bottom scroll-top; do
  grep -q "casper browser $sub" "$FILE" || fail "missing casper browser $sub reference"
done
grep -qi "verify" "$FILE" || fail "missing verification framing for coding agents"

echo "PASS"
