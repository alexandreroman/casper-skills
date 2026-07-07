#!/usr/bin/env bash
casper status set idle >/dev/null 2>&1 || true
casper progress clear >/dev/null 2>&1 || true
