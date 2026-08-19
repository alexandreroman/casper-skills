#!/usr/bin/env bash
casper status set idle >/dev/null 2>&1 || true
casper progress clear >/dev/null 2>&1 || true

# A fresh conversation starts with an empty info panel: whatever the previous
# session published there describes work this session knows nothing about.
# `resume` and `compact` continue an existing session, so they keep it.
hook_input="$(cat)"
hook_source="$(printf '%s' "$hook_input" | sed -n 's/.*"source"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
case "$hook_source" in
  resume | compact) ;;
  *) casper info clear >/dev/null 2>&1 || true ;;
esac

# Inject guidance into the session context (SessionStart stdout is added to
# Claude's context). This hook only runs inside a Casper workspace, so Casper
# is guaranteed available here.
cat <<'EOF'
Casper is available in this workspace. When you need my intervention — a
decision, a credential, an interactive login, an approval, or an
unrecoverable error you want me to notice — be explicit and tell me instead
of silently waiting. This includes ending a turn to ask me a question or
present options: that is a blocked state, not a finished one, so notify me.
Use the Casper notification mechanism:

  casper notify --message "<what you need from me>"
  casper status set blocked   # when you're waiting on me mid-turn

If your work breaks into several distinct steps and isn't over in a single
action, track it with the task tools (TaskCreate up front, then TaskUpdate to
in_progress/completed as you go) — this keeps the workspace's sidebar progress
bar in sync. See the casper-progress skill for when and how.

If `casper` isn't found or a command fails, ignore it and continue — never
let it interrupt your task.
EOF
