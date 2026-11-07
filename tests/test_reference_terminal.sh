#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper/references/terminal.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "casper terminal new" "$FILE" || fail "missing casper terminal new example"
grep -q "casper terminal list" "$FILE" || fail "missing casper terminal list example"
grep -q "casper terminal close" "$FILE" || fail "missing casper terminal close example"
# Every agent launch names the new session after the workspace plus a purpose.
grep -q -- '--command "<agent-cli> <name-flag> <session-name>"' "$FILE" \
  || fail "the bare agent launch must name the session"
grep -q -- '--command "<agent-cli> <name-flag> <session-name> \\"Read the instructions' "$FILE" \
  || fail "the agent launch with a task must name the session"
grep -q '<workspace>-<purpose>' "$FILE" || fail "missing the <workspace>-<purpose> session name"
grep -q '`<name-flag>` is `-n` (long form `--name`)' "$FILE" \
  || fail "claude's name flag must be -n / --name"
grep -q "launch them unnamed" "$FILE" || fail "must say an agent CLI without a name flag is launched unnamed"
echo "PASS"
