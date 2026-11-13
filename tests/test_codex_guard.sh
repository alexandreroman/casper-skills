#!/usr/bin/env bash
# hooks/codex-guard.sh, run the way an agent runs it: through hooks.json's own
# commands, under a real ancestor process. Codex 0.169 runs hooks from its
# shared background server, `codex app-server`, whose environment names the
# workspace of whichever terminal started it; a session from another workspace
# must not write to that sidebar (hooks/lib/codex_server.py).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DIR/tests/lib/harness.sh"

fail() { echo "FAIL: $1"; exit 1; }

T="$(mktemp -d)"
trap 'rm -rf "$T" "${STUB_DIR:-}"' EXIT
mkdir -p "$T/own/sub" "$T/other"
OWN="$(cd "$T/own" && pwd -P)"
OTHER="$(cd "$T/other" && pwd -P)"

# A stand-in for Codex's shared server: a process whose command line reads
# `.../codex app-server`, running the hook command as its child.
mkdir -p "$T/bin"
cat > "$T/bin/codex" <<'EOF'
#!/usr/bin/env bash
# usage: codex app-server <shell command>
sh -c "$2"
EOF
chmod +x "$T/bin/codex"

command_for() {
  (cd "$DIR" && python3 -c "
import json, sys
hooks = json.load(open('hooks/hooks.json'))['hooks']
print(hooks[sys.argv[1]][0]['hooks'][0]['command'])
" "$1")
}
SESSION_START="$(command_for SessionStart)"
PROMPT="$(command_for UserPromptSubmit)"

list_with_path() {
  printf '[{"workspace":"%s","name":"probe","path":"%s"}]' "$CASPER_WORKSPACE_ID" "$1"
}

# Runs a hooks.json command as Codex would: in the session's directory, with
# Codex's own name for the plugin root, under the shared server or not.
run_hook() {  # <cwd> <server|direct> <command>
  if [ "$2" = server ]; then
    (cd "$1" && env -u CLAUDE_PLUGIN_ROOT PLUGIN_ROOT="$DIR" \
       "$T/bin/codex" app-server "$3" </dev/null)
  else
    (cd "$1" && env -u CLAUDE_PLUGIN_ROOT PLUGIN_ROOT="$DIR" sh -c "$3" </dev/null)
  fi
}

# 1. Under the server, a session of another workspace: nothing reaches casper
#    but the lookup, and SessionStart warns instead of injecting the guidance.
casper_stub_init
export CASPER_STUB_OUT_workspace_list="$(list_with_path "$OWN")"
out="$(run_hook "$OTHER" server "$SESSION_START")"
assert_casper_calls "workspace list"
echo "$out" | grep -q "Casper integration is off for this session" \
  || fail "a foreign session's SessionStart must say the integration is off"
echo "$out" | grep -q -- "codex --no-daemon" || fail "the warning must name codex --no-daemon"
echo "$out" | grep -q "Casper is available" && fail "a foreign session must not get the guidance"

casper_stub_init
run_hook "$OTHER" server "$PROMPT" >/dev/null
assert_casper_calls "workspace list"

# 2. Under the server, this workspace's own session, from a subdirectory too:
#    the hook runs as before.
casper_stub_init
export CASPER_STUB_OUT_workspace_list="$(list_with_path "$OWN")"
run_hook "$T/own/sub" server "$PROMPT" >/dev/null
assert_casper_calls "workspace list
status set working"

out="$(run_hook "$OWN" server "$SESSION_START")"
echo "$out" | grep -q "Casper is available" || fail "the own session must get the guidance"

# 3. Under the server, a lookup with no answer (Casper too old, not running):
#    the check cannot be made, so it must not switch the integration off.
casper_stub_init
unset CASPER_STUB_OUT_workspace_list
run_hook "$OTHER" server "$PROMPT" >/dev/null
assert_casper_calls "workspace list
status set working"

# 4. Codex with --no-daemon: no server among the ancestors, so no lookup.
casper_stub_init
export CASPER_STUB_OUT_workspace_list="$(list_with_path "$OWN")"
run_hook "$OTHER" direct "$PROMPT" >/dev/null
assert_casper_calls "status set working"

# 5. Claude Code (no PLUGIN_ROOT), even under a process that looks like the
#    server: the guard never looks.
casper_stub_init
(cd "$OTHER" && env -u PLUGIN_ROOT CLAUDE_PLUGIN_ROOT="$DIR" \
   "$T/bin/codex" app-server "$PROMPT" </dev/null) >/dev/null
assert_casper_calls "status set working"

# 6. The guard leaves stdin to the hook behind it: Stop still reads the
#    payload (its session's dialog marker) when the session is its own.
casper_stub_init
export CASPER_STUB_OUT_workspace_list="$(list_with_path "$OWN")"
export CLAUDE_PLUGIN_DATA="$T/data"
mkdir -p "$CLAUDE_PLUGIN_DATA"
STOP="$(command_for Stop)"
export CASPER_STUB_OUT_status_get='{"status":"blocked"}'
(cd "$DIR" && python3 -c "from hooks.lib import dialog; dialog.open_('s1')")
(cd "$OWN" && printf '{"session_id":"s1","hook_event_name":"Stop"}' \
   | env -u CLAUDE_PLUGIN_ROOT PLUGIN_ROOT="$DIR" "$T/bin/codex" app-server "$STOP")
calls="$(tr '\t' ' ' < "$CASPER_LOG" | sed 's/ *$//')"
echo "$calls" | grep -qx "status set done" \
  || fail "Stop behind the guard must read its payload (a dialog's blocked ends done); got: $calls"

echo "PASS"
