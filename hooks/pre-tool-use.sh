#!/usr/bin/env bash
payload="$(cat)"
data="${CLAUDE_PLUGIN_DATA:-/tmp/casper-skills}"

# A subagent's tool call (Claude Code adds `agent_id` to its payload) is not
# the agent's: a background one keeps calling tools after the agent's turn
# ended `done` or `blocked`, and must not report over that. markers.py handles
# it and succeeds only once the parsed payload confirms it; an `agent_id` that
# turns out to sit in the tool's input falls through to the agent's path.
if [[ "$payload" =~ \"agent_id\"[[:space:]]*: ]] &&
   printf '%s' "$payload" | "$(dirname "$0")/markers.py" subagent-tool >/dev/null 2>&1; then
  exit 0
fi

casper status set working >/dev/null 2>&1 || true

# Track the agent's own `casper notify`, so hooks/blocked.py does not notify a
# second time for the wait the agent just announced (hooks/lib/notified.py),
# and close a dialog's `blocked` (hooks/lib/dialog.py). Python runs only when
# there is something to track: a call that may run `casper notify`, or a
# marker some session left standing. Every other tool call, which is nearly
# all of them, stays on this fast path.
if [[ "$payload" == *casper*notify* ]] ||
   compgen -G "$data/*.notified" >/dev/null || compgen -G "$data/*.dialog" >/dev/null; then
  printf '%s' "$payload" | "$(dirname "$0")/markers.py" tool >/dev/null 2>&1 || true
fi
