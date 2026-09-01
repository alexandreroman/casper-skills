#!/usr/bin/env bash
# StopFailure runs *instead of* Stop when the turn dies on an API error —
# rate limit, auth, billing, overload. Nothing about that is a judgment call,
# so unlike hooks/stop.py this reports one fixed state and reads nothing back:
# EVENT_ACTIONS["turn-error"].
#
# The bar is deliberately left where it is. A turn killed mid-step is
# genuinely paused part-way through it, so the label still says where the work
# stopped; the next Stop reconciles it and hooks/session-end.sh is the
# backstop. The state outlasts the turn on purpose and is cleared by the next
# thing that knows better — the next prompt, the next tool call, or a new
# session.
casper status set error >/dev/null 2>&1 || true
