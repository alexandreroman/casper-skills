#!/usr/bin/env bash
# Only mark the workspace idle. Casper's detection engine derives the
# edge-triggered "task finished, unseen" notification on its own by scraping the
# terminal, so an unconditional notify here would just duplicate it.
casper status set idle >/dev/null 2>&1 || true
