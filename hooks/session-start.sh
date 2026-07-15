#!/usr/bin/env bash
casper status set idle >/dev/null 2>&1 || true
casper progress clear >/dev/null 2>&1 || true

# Inject guidance into the session context (SessionStart stdout is added to
# Claude's context). This hook only runs inside a Casper workspace, so Casper
# is guaranteed available here.
cat <<'EOF'
Casper is available in this workspace. When you need my intervention — a
decision, a credential, an interactive login, an approval, or an
unrecoverable error you want me to notice — be explicit and tell me instead
of silently waiting. Use the Casper notification mechanism:

  casper notify --message "<what you need from me>"
  casper status set blocked   # when you're waiting on me mid-turn

If `casper` isn't found or a command fails, ignore it and continue — never
let it interrupt your task.
EOF
