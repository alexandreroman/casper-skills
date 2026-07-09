#!/usr/bin/env bash
# Report done explicitly. Every workspace this plugin drives is under
# Casper's explicit-authority latch from the very first `casper status set
# working` call onward (user-prompt-submit.sh / pre-tool-use.sh) — which
# permanently suppresses Casper's terminal-scraping detector for it, so
# detection can never derive "done" here on its own. Casper collapses this
# back to idle once the workspace is selected (seen).
casper status set done >/dev/null 2>&1 || true
