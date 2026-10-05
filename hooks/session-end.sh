#!/usr/bin/env bash
casper status set done >/dev/null 2>&1 || true
# The bar's backstop. Turn end only clears a bar the agent's task state says
# the work is done with, so a bar driven by hand survives every turn boundary
# — this is where it stops, whether or not the agent remembered to clear it.
casper progress clear >/dev/null 2>&1 || true

# The marker of the agent's own notify ends with the session too
# (hooks/lib/notified.py).
if compgen -G "${CLAUDE_PLUGIN_DATA:-/tmp/casper-skills}/*.notified" >/dev/null; then
  "$(dirname "$0")/notified.py" clear >/dev/null 2>&1 || true
fi
