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

OUT="$(PATH="$STUB_DIR:$PATH" CASPER_LOG="$LOG" "$DIR/hooks/session-start.sh")"

expected=$'status\nset\nidle\n---\nprogress\nclear\n---'
actual="$(cat "$LOG")"
if [ "$actual" != "$expected" ]; then
  echo "FAIL: expected [$expected], got [$actual]"
  exit 1
fi

# The hook must inject intervention guidance into the session context (stdout).
case "$OUT" in
  *"casper notify --message"*"casper status set blocked"*) ;;
  *)
    echo "FAIL: session-start stdout missing intervention guidance"
    echo "got: [$OUT]"
    exit 1
    ;;
esac

# The guidance must name the turn-end case (asking a question / presenting
# options is a blocked state), so the model does not treat it as "done".
case "$OUT" in
  *"ask me a question or"*"present options"*) ;;
  *)
    echo "FAIL: session-start stdout missing turn-end intervention guidance"
    echo "got: [$OUT]"
    exit 1
    ;;
esac

# The guidance must point at task-tools progress tracking (so the sidebar
# progress bar stays in sync) and name the casper-progress skill.
case "$OUT" in
  *"track it with the task tools"*"casper-progress skill"*) ;;
  *)
    echo "FAIL: session-start stdout missing progress-tracking guidance"
    echo "got: [$OUT]"
    exit 1
    ;;
esac
echo "PASS"
