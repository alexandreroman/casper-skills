#!/usr/bin/env python3
"""Let a hook run under Codex's shared server only for this workspace's session.

hooks/codex-guard.sh calls this once it has found that the hook is running in
Codex's shared background server (hooks/lib/codex_server.py says why that
matters). Exit 0 lets the hook run; exit 1 skips it. For SessionStart, the
skipped session gets a warning in place of the guidance instead, so the agent
does not drive another workspace's sidebar with its own `casper` calls and
can tell the user how to get this one back.

stdin is never read: it belongs to the hook this guard stands in front of.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hooks.lib import casper, codex_server


def main() -> int:
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        cwd = os.getcwd()
    except OSError:
        return 0
    workspaces = casper.query(["workspace", "list"], timeout=0.5)
    verdict = codex_server.belongs(workspaces,
                                   os.environ.get("CASPER_WORKSPACE_ID", ""), cwd)
    if verdict is not False:
        return 0
    if event == "session-start":
        sys.stdout.write(codex_server.WARNING)
    return 1


if __name__ == "__main__":
    try:
        status = main()
    except Exception:
        # A guard that cannot run must not switch the integration off.
        status = 0
    sys.exit(status)
