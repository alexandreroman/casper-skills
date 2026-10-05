#!/usr/bin/env bash
casper status set working >/dev/null 2>&1 || true

# A new prompt ends any wait the agent announced (hooks/lib/notified.py).
if compgen -G "${CLAUDE_PLUGIN_DATA:-/tmp/casper-skills}/*.notified" >/dev/null; then
  "$(dirname "$0")/notified.py" clear >/dev/null 2>&1 || true
fi
