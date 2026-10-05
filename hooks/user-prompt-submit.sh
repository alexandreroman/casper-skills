#!/usr/bin/env bash
casper status set working >/dev/null 2>&1 || true

# A new prompt ends any wait: the one the agent announced
# (hooks/lib/notified.py) and a dialog's `blocked` (hooks/lib/dialog.py).
data="${CLAUDE_PLUGIN_DATA:-/tmp/casper-skills}"
if compgen -G "$data/*.notified" >/dev/null || compgen -G "$data/*.dialog" >/dev/null; then
  "$(dirname "$0")/markers.py" clear >/dev/null 2>&1 || true
fi
