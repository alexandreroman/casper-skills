#!/usr/bin/env bash
# Stands in front of every hook (hooks/hooks.json): exit 0 runs the hook, any
# other status skips it. The one case it ever skips is a Codex session run by
# Codex's shared background server for a workspace other than the one that
# server's environment names (hooks/lib/codex_server.py).
#
# Never reads stdin: the payload belongs to the hook that runs next.

# Not Codex: Claude Code sets only CLAUDE_PLUGIN_ROOT, Codex also PLUGIN_ROOT.
[ -n "${PLUGIN_ROOT:-}" ] || exit 0

# Is a `codex app-server` among this hook's ancestors? Codex started with
# --no-daemon runs hooks from the terminal's own process, whose environment is
# already the right one, and only pays for this one `ps`.
shared="$(ps -A -o pid= -o ppid= -o command= 2>/dev/null </dev/null | awk -v pid="$$" '
  { c = $0; sub(/^[ \t]*[0-9]+[ \t]+[0-9]+[ \t]+/, "", c); parent[$1] = $2; cmd[$1] = c }
  END {
    cur = parent[pid]
    for (i = 0; i < 8 && cur > 1; i++) {
      if (cmd[cur] ~ /(^|\/)codex app-server( |$)/) { print "yes"; exit }
      cur = parent[cur]
    }
  }')"
[ "$shared" = yes ] || exit 0

exec "$(dirname "$0")/codex-guard.py" "$@" </dev/null
