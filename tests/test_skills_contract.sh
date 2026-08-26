#!/usr/bin/env bash
# The plugin ships one entry skill whose reference files carry the per-domain
# detail. The entry skill must satisfy the agentskills.io frontmatter
# contract; every file, entry or reference, must stay free of any one agent's
# tool names so all three agents read them naturally.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fail() { echo "FAIL: $1"; exit 1; }

# Exactly one skill: the collapse into a single entry point is the contract,
# so a stray sibling directory is a regression, not an addition.
count="$(find "$DIR/skills" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
[ "$count" = "1" ] || fail "expected exactly one skill directory, found $count"
[ -d "$DIR/skills/casper" ] || fail "the entry skill must live in skills/casper"

ENTRY="$DIR/skills/casper/SKILL.md"
[ -f "$ENTRY" ] || fail "missing skills/casper/SKILL.md"
grep -q "^name: casper\$" "$ENTRY" || fail "frontmatter name must match the directory"
grep -q "^description: " "$ENTRY" || fail "missing description"
# The skill is model-facing only: an agent loads it when a Casper surface is
# involved, and a user typing /casper would get a routing table, not an action.
# The key is Claude-only; the other agents ignore an unknown frontmatter key.
grep -q "^user-invocable: false\$" "$ENTRY" || fail "the entry skill must set user-invocable: false"

# Tool names belonging to one agent only.
for file in "$ENTRY" "$DIR"/skills/casper/references/*.md; do
  rel="${file#$DIR/}"
  for banned in "TaskCreate" "TaskUpdate" "the Read tool" "run_in_background" "Bash tool"; do
    grep -q "$banned" "$file" && fail "$rel: names a Claude-only tool: $banned"
  done

  # "Claude" may appear only as one example among several agent CLIs.
  if grep -q "Claude" "$file" && ! grep -qi "codex" "$file"; then
    fail "$rel: mentions Claude without presenting it as one option among agents"
  fi
done

# Reference files are loaded as plain prose, never registered as skills, so a
# frontmatter block there would be dead weight an agent might act on.
for ref in "$DIR"/skills/casper/references/*.md; do
  head -n 1 "$ref" | grep -q "^---$" && fail "${ref#$DIR/}: reference files must have no frontmatter"
  head -n 1 "$ref" | grep -q "^# " || fail "${ref#$DIR/}: reference files must open with an H1"
done

# A reference file is unreachable except through the entry skill's routing
# table, so the entry skill is always in context when one is read. Restating
# its guard rule there is dead weight that drifts out of sync. Only
# repo-config.md may carry a guard section, because its rule contradicts the
# general one: writing .casper.json needs no Casper terminal at all.
for ref in "$DIR"/skills/casper/references/*.md; do
  name="$(basename "$ref")"
  [ "$name" = "repo-config.md" ] && continue
  grep -q "^## Guard rule\b" "$ref" && fail "references/$name: the entry skill already states the guard rule; keep only what differs from it"
  grep -q "Only run these commands inside a Casper terminal workspace" "$ref" && fail "references/$name: restates the entry skill's guard rule verbatim"
  grep -q "never let it interrupt your actual task" "$ref" && fail "references/$name: restates the entry skill's never-interrupt rule"
done

# The routing table and the files on disk must agree in both directions: a
# reference nobody links to is unreachable, a link with no file is a dead end.
linked="$(grep -o 'references/[a-z-]*\.md' "$ENTRY" | sort -u)"
[ -n "$linked" ] || fail "the entry skill links no reference file"
for name in $linked; do
  [ -f "$DIR/skills/casper/$name" ] || fail "entry skill links a missing file: $name"
done
for ref in "$DIR"/skills/casper/references/*.md; do
  name="references/$(basename "$ref")"
  echo "$linked" | grep -qx "$name" || fail "$name is orphaned: nothing in the entry skill links it"
done

echo "PASS"
