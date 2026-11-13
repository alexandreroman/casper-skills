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

# Every launch names the new session after the workspace, and only with a
# flag the agent CLI really has: a made-up flag would make the CLI refuse to
# start, which is worse than an unnamed session.
grep -q "^### Naming the session after the workspace\$" "$FILE" \
  || fail "missing the session-naming section (handoff.md links it by title)"
grep -q -- '--command "<agent-cli> <name-flag> <name>"' "$FILE" \
  || fail "the bare launch must name the session"
grep -q -- '--command "<agent-cli> <name-flag> <name> \\"Read the instructions' "$FILE" \
  || fail "the launch with a task must name the session"
grep -q '^| `claude` | `-n` (long form `--name`)' "$FILE" \
  || fail "claude's name flag must be -n / --name"
for cli in codex gemini opencode aider; do
  grep -q "^| \`$cli\` | none" "$FILE" || fail "$cli has no session-name flag; the table must say none"
done
# Codex 0.169 runs sessions in a background server shared machine-wide, with
# the environment of the terminal that started it; only --no-daemon keeps the
# new instance's hooks on the new workspace (hooks/lib/codex_server.py).
grep -q 'launch it as `codex --no-daemon`' "$FILE" || fail "codex must be launched with --no-daemon"
grep -q "launched unnamed" "$FILE" || fail "must say an agent CLI without a name flag is launched unnamed"

# What the agent launched earlier is history: the user or another agent can
# merge or delete a workspace at any moment. A session that listed five
# instances "running in parallel" from memory, three of them already gone, is
# the failure this section exists for. SKILL.md and handoff.md cite its title.
grep -q "^### Reporting workspaces: check first\$" "$FILE" \
  || fail "missing the check-before-reporting section (SKILL.md and handoff.md link it by title)"
section="$(sed -n '/^### Reporting workspaces: check first$/,/^## /p' "$FILE")"
echo "$section" | grep -q "casper workspace list" || fail "the reporting section must run casper workspace list"
echo "$section" | grep -q "same turn" || fail "the check must happen in the same turn as the claim"
echo "$section" | grep -q "history" || fail "unchecked launches must be worded as history"
echo "$section" | grep -q "casper status get --workspace" \
  || fail "an instance's activity must be checked against its workspace's status"
grep -q 'Reporting workspaces: check first' "$DIR/skills/casper/references/handoff.md" \
  || fail "handoff.md must send its report through the check-first section"

echo "PASS"
