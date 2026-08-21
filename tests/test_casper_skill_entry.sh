#!/usr/bin/env bash
# The entry skill is the only one an agent loads unprompted, so it has two
# jobs and must do nothing else: fire when the session is in a Casper
# terminal, and route to the reference file for the surface at hand.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$DIR/skills/casper/SKILL.md"

fail() { echo "FAIL: $1"; exit 1; }

[ -f "$FILE" ] || fail "missing $FILE"
grep -q "^name: casper\$" "$FILE" || fail "missing name in frontmatter"
grep -q "^description: " "$FILE" || fail "missing description in frontmatter"

# The trigger: the description must key on running inside a Casper terminal,
# not merely on the topic, or it only fires when the user says "Casper".
desc="$(grep -m1 "^description: " "$FILE")"
echo "$desc" | grep -q "CASPER_WORKSPACE_ID" || fail "description must name CASPER_WORKSPACE_ID as the trigger condition"
echo "$desc" | grep -qi "Casper terminal workspace" || fail "description must name the Casper terminal workspace condition"

# The notify/blocked rule is the behaviour the whole integration exists for.
# It has to work before any reference file is read, so it stays inline.
grep -q "casper notify --message" "$FILE" || fail "the notify rule must be inline, not deferred to a reference"
grep -q "casper status set blocked" "$FILE" || fail "the blocked rule must be inline, not deferred to a reference"

# The guard rule, likewise: every command below it depends on it.
grep -q "CASPER_WORKSPACE_ID" "$FILE" || fail "missing guard-rule mention in the body"
grep -qi "never allowed to interrupt\|ignore it and carry on" "$FILE" || fail "missing the never-interrupt-the-task rule"

# One reference per domain, all nine reachable from the routing table.
for ref in status progress info browser diff terminal workspace handoff repo-config; do
  grep -q "references/$ref\.md" "$FILE" || fail "routing table does not link references/$ref.md"
done

# Authorization is decided once, here: reference files carry no frontmatter.
grep -q "^allowed-tools:.*Bash(casper \*)" "$FILE" || fail "missing allowed-tools pre-authorization for the casper CLI"
grep -q '^allowed-tools:.*Bash(\[ -n "\$CASPER_WORKSPACE_ID" \])' "$FILE" || fail "missing allowed-tools pre-authorization for the workspace guard"

# Size cap: the point of the split is that this file stays resident. Without a
# cap the routing table grows back into the manual it replaced.
lines="$(wc -l < "$FILE" | tr -d ' ')"
[ "$lines" -le 80 ] || fail "entry skill is $lines lines; keep it under 80 — detail belongs in references/"

echo "PASS"
