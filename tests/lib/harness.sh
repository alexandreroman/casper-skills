#!/usr/bin/env bash
# Shared stub-`casper` harness. Source it, call casper_stub_init, run the code
# under test, then assert on the recorded argv.

casper_stub_init() {
  STUB_DIR="$(mktemp -d)"
  CASPER_LOG="$(mktemp)"
  export CASPER_LOG
  cat > "$STUB_DIR/casper" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CASPER_LOG"
STUB
  chmod +x "$STUB_DIR/casper"
  export PATH="$STUB_DIR:$PATH"
  export CASPER_WORKSPACE_ID="${CASPER_WORKSPACE_ID:-test-ws}"
}

casper_calls() { cat "$CASPER_LOG"; }

assert_casper_calls() {
  local expected="$1" actual
  actual="$(cat "$CASPER_LOG")"
  if [ "$actual" != "$expected" ]; then
    echo "FAIL: casper calls mismatch"
    echo "--- expected ---"; printf '%s\n' "$expected"
    echo "--- actual ---";   printf '%s\n' "$actual"
    exit 1
  fi
}
