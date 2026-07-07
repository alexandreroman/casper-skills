#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STUB_DIR="$(mktemp -d)"
LOG="$(mktemp)"
cat > "$STUB_DIR/casper" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >> "$CASPER_LOG"
printf -- '---\n' >> "$CASPER_LOG"
EOF
chmod +x "$STUB_DIR/casper"

GUARDED_CMD="[ -n \"\$CASPER_WORKSPACE_ID\" ] && ${DIR}/hooks/session-start.sh || true"

# Case 1: no CASPER_WORKSPACE_ID -> must not call casper
env -u CASPER_WORKSPACE_ID PATH="$STUB_DIR:$PATH" CASPER_LOG="$LOG" bash -c "$GUARDED_CMD"
if [ -s "$LOG" ]; then
  echo "FAIL: casper was called without CASPER_WORKSPACE_ID set"
  exit 1
fi

# Case 2: CASPER_WORKSPACE_ID set -> must call casper
CASPER_WORKSPACE_ID=test-ws PATH="$STUB_DIR:$PATH" CASPER_LOG="$LOG" bash -c "$GUARDED_CMD"
if [ ! -s "$LOG" ]; then
  echo "FAIL: casper was not called with CASPER_WORKSPACE_ID set"
  exit 1
fi

echo "PASS"
