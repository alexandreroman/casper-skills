#!/usr/bin/env bash
# A tool just finished. If a dialog had reported `blocked`, that was the
# dialog's tool, approved and run: report `working` again (hooks/lib/dialog.py).
# Every other tool call ends here without starting Python or calling casper.
if compgen -G "${CLAUDE_PLUGIN_DATA:-/tmp/casper-skills}/*.dialog" >/dev/null; then
  "$(dirname "$0")/markers.py" tool-done >/dev/null 2>&1 || true
fi
