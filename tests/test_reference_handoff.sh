#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper/references/handoff.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "casper workspace new <name>" "$FILE" || fail "missing casper workspace new example"
grep -q -- "--base" "$FILE" || fail "missing --base (fork from current branch) documentation"
grep -q "git rev-parse --abbrev-ref HEAD" "$FILE" || fail "missing current-branch resolution"
grep -q "WIP" "$FILE" || fail "missing WIP-commit handling for uncommitted work"
grep -q "mktemp" "$FILE" || fail "missing temp-file handoff document"
# No placeholder may reference a file no step here creates.
grep -q -- "--file <note>" "$FILE" && fail "dangling <note> placeholder: no step creates that file"

# The continuing session is named after the new workspace, by the rules
# workspace.md states; the section it points to must exist under that title.
grep -q -- '--command "<agent-cli> <name-flag> <name> \\"Read the handoff' "$FILE" \
  || fail "the handoff launch must name the continuing session"
grep -q '"Naming the session after the workspace"' "$FILE" \
  || fail "must point to workspace.md's session-naming section"
grep -q "^### Naming the session after the workspace\$" "$DIR/skills/casper/references/workspace.md" \
  || fail "workspace.md has no section by the title handoff.md points to"

echo "PASS"
