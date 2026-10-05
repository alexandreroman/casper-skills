#!/usr/bin/env bash
casper status set working >/dev/null 2>&1 || true

# Track the agent's own `casper notify`, so hooks/blocked.py does not notify a
# second time for the wait the agent just announced (hooks/lib/notified.py).
# Python runs only when there is something to track: a call that may run
# `casper notify`, or a marker some session left standing. Every other tool
# call, which is nearly all of them, stays on this fast path.
payload="$(cat)"
if [[ "$payload" == *casper*notify* ]] ||
   compgen -G "${CLAUDE_PLUGIN_DATA:-/tmp/casper-skills}/*.notified" >/dev/null; then
  printf '%s' "$payload" | "$(dirname "$0")/notified.py" tool >/dev/null 2>&1 || true
fi
