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

PATH="$STUB_DIR:$PATH" CASPER_LOG="$LOG" "$DIR/hooks/session-end.sh"

expected=$'status\nset\ndone\n---'
actual="$(cat "$LOG")"
if [ "$actual" != "$expected" ]; then
  echo "FAIL: expected [$expected], got [$actual]"
  exit 1
fi
echo "PASS"
