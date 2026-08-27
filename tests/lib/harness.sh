#!/usr/bin/env bash
# Shared stub-`casper` harness. Source it, call casper_stub_init, run the code
# under test, then assert on the recorded argv. Re-initializing discards the
# previous stub rather than stacking another temp dir onto PATH.

casper_stub_init() {
  if [ -n "${STUB_DIR:-}" ]; then rm -rf "$STUB_DIR"; fi
  : "${CASPER_STUB_BASE_PATH:=$PATH}"
  STUB_DIR="$(mktemp -d)"
  CASPER_LOG="$STUB_DIR/calls.log"
  export CASPER_LOG
  : > "$CASPER_LOG"
  cat > "$STUB_DIR/casper" <<'STUB'
#!/usr/bin/env bash
printf '%s\t' "$@" >> "$CASPER_LOG"
printf '\n' >> "$CASPER_LOG"
# Canned answers for the read verbs, so a hook that asks `casper` a question
# can be driven from a test: CASPER_STUB_OUT_<verb>_<subcommand>. Unset means
# the verb answers nothing, which is what an older CLI or a stopped app looks
# like. The name is only built for plain lowercase verbs, so no argument can
# ever compose an env-var name.
if [[ "${1:-}" =~ ^[a-z]+$ && "${2:-}" =~ ^[a-z]+$ ]]; then
  reply="CASPER_STUB_OUT_$1_$2"
  [ -n "${!reply:-}" ] && printf '%s\n' "${!reply}"
fi
exit 0
STUB
  chmod +x "$STUB_DIR/casper"
  export PATH="$STUB_DIR:$CASPER_STUB_BASE_PATH"
  export CASPER_WORKSPACE_ID="${CASPER_WORKSPACE_ID:-test-ws}"
}

assert_casper_calls() {
  local expected="$1" actual
  actual="$(tr '\t' ' ' < "$CASPER_LOG" | sed 's/ *$//')"
  if [ "$actual" != "$expected" ]; then
    echo "FAIL: casper calls mismatch"
    echo "--- expected ---"; printf '%s\n' "$expected"
    echo "--- actual ---";   printf '%s\n' "$actual"
    exit 1
  fi
}
