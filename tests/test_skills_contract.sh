#!/usr/bin/env bash
# Every skill must satisfy the agentskills.io frontmatter contract and stay
# free of any one agent's tool names, so all three agents read them naturally.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fail() { echo "FAIL: $1"; exit 1; }

for skill in "$DIR"/skills/*/; do
  name="$(basename "$skill")"
  file="$skill/SKILL.md"
  [ -f "$file" ] || fail "$name: missing SKILL.md"

  grep -q "^name: $name\$" "$file" || fail "$name: frontmatter name must match the directory"
  grep -q "^description: " "$file" || fail "$name: missing description"
  grep -q "^user-invocable:" "$file" && fail "$name: user-invocable is Claude-only"

  # Tool names belonging to one agent only.
  for banned in "TaskCreate" "TaskUpdate" "the Read tool" "run_in_background"; do
    grep -q "$banned" "$file" && fail "$name: names a Claude-only tool: $banned"
  done

  # "Claude" may appear only as one example among several agent CLIs.
  if grep -q "Claude" "$file" && ! grep -qi "codex" "$file"; then
    fail "$name: mentions Claude without presenting it as one option among agents"
  fi
done
echo "PASS"
