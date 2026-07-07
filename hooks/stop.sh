#!/usr/bin/env bash
casper status set idle >/dev/null 2>&1 || true
casper notify --message "Claude is done and waiting for you" >/dev/null 2>&1 || true
