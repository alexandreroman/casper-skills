#!/usr/bin/env bash
# Every agent must map the same normalized event to the same casper argv.
# EVENT_ACTIONS is the authority; this asserts the opencode plugin agrees.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

expected_for() {
  # separators=(',', ':') matches JS JSON.stringify's compact output, so the
  # two languages' serializations compare byte-for-byte.
  python3 -c "
from hooks.lib.casper import EVENT_ACTIONS
import json; print(json.dumps(EVENT_ACTIONS['$1'], separators=(',', ':')))
"
}

actual="$(node --input-type=module -e '
import plugin from "./.opencode/plugin/casper.js"
process.env.CASPER_WORKSPACE_ID = "test-ws"
const calls = []
const hooks = await plugin.server({ client: { session: { list: async () => ({ data: [{ id: "root" }] }) } } })
plugin.__test.setRunner((a) => calls.push(a))
const ev = (type, properties) => ({ event: { type, properties } })
await hooks.event(ev("session.created", { info: { id: "root" } }))
calls.length = 0
await hooks.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
const turnStart = JSON.stringify(calls.splice(0))
await hooks.event(ev("session.status", { sessionID: "root", status: { type: "idle" } }))
const turnEnd = JSON.stringify(calls.splice(0))
console.log(turnStart); console.log(turnEnd)
')"

got_start="$(printf '%s\n' "$actual" | sed -n 1p)"
got_end="$(printf '%s\n' "$actual" | sed -n 2p)"

[ "$got_start" = "$(expected_for turn-start)" ] || {
  echo "FAIL: turn-start mismatch"; echo "  expected $(expected_for turn-start)"; echo "  got      $got_start"; exit 1; }
[ "$got_end" = "$(expected_for turn-end)" ] || {
  echo "FAIL: turn-end mismatch"; echo "  expected $(expected_for turn-end)"; echo "  got      $got_end"; exit 1; }

# progressActions (JS) must agree with actions_for (Python) on the same input.
fixture='[{"label":"a","status":"completed"},{"label":"b","status":"in_progress"},{"label":"c","status":"pending"}]'
py="$(python3 -c "
import json
from hooks.lib.progress import actions_for
print(json.dumps(actions_for(json.loads('$fixture')), separators=(',', ':')))
")"
js="$(node --input-type=module -e '
import { progressActions } from "./.opencode/plugin/casper.js"
const todos = JSON.parse(process.argv[1]).map(t => ({ content: t.label, status: t.status }))
console.log(JSON.stringify(progressActions(todos)))
' "$fixture")"
[ "$py" = "$js" ] || { echo "FAIL: progress mismatch"; echo "  py $py"; echo "  js $js"; exit 1; }
echo "  ok: progressActions == actions_for"

# The session-start triple and the blocked pair are payload-dependent, so
# they are not in EVENT_ACTIONS: hooks/session-start.py, hooks/blocked.py,
# and the opencode plugin's session.created/permission.asked paths each
# hardcode them independently. Drive each side with a stub `casper` on PATH
# (Python) or plugin.__test.setRunner (JS) and compare the recorded argv.

run_py_hook() {
  # $1: hook script path (relative to $DIR), $2: JSON payload on stdin.
  local script="$1" payload="$2"
  PAYLOAD="$payload" python3 - "$script" <<'PY'
import json, os, subprocess, sys
sys.path.insert(0, "tests/lib")
from harness import CasperStub
script = sys.argv[1]
payload = os.environ["PAYLOAD"]
with CasperStub() as stub:
    subprocess.run([script], input=payload, env=stub.env(), text=True, capture_output=True)
    print(json.dumps(stub.calls, separators=(",", ":")))
PY
}

py_session_start="$(run_py_hook hooks/session-start.py '{"source":"startup"}')"
js_session_start="$(node --input-type=module -e '
import plugin from "./.opencode/plugin/casper.js"
process.env.CASPER_WORKSPACE_ID = "test-ws"
const calls = []
const hooks = await plugin.server({ client: { session: { list: async () => ({ data: [{ id: "root" }] }) } } })
plugin.__test.setRunner((a) => calls.push(a))
const ev = (type, properties) => ({ event: { type, properties } })
await hooks.event(ev("session.created", { info: { id: "root" } }))
console.log(JSON.stringify(calls))
')"

[ "$py_session_start" = "$js_session_start" ] || {
  echo "FAIL: session-start triple mismatch (hooks/session-start.py vs opencode session.created)"
  echo "  py $py_session_start"; echo "  js $js_session_start"; exit 1; }
echo "  ok: session-start triple matches (hooks/session-start.py == opencode session.created)"

# Same tool name, no description, on both sides so the notify message text
# lines up too and the full argv can be compared, not just its shape.
py_blocked="$(run_py_hook hooks/blocked.py '{"hook_event_name":"PermissionRequest","tool_name":"bash"}')"
js_blocked="$(node --input-type=module -e '
import plugin from "./.opencode/plugin/casper.js"
process.env.CASPER_WORKSPACE_ID = "test-ws"
const calls = []
const hooks = await plugin.server({ client: { session: { list: async () => ({ data: [{ id: "root" }] }) } } })
plugin.__test.setRunner((a) => calls.push(a))
const ev = (type, properties) => ({ event: { type, properties } })
await hooks.event(ev("session.created", { info: { id: "root" } }))
calls.length = 0
await hooks.event(ev("permission.asked", { sessionID: "root", tool: "bash" }))
console.log(JSON.stringify(calls))
')"

[ "$py_blocked" = "$js_blocked" ] || {
  echo "FAIL: blocked pair mismatch (hooks/blocked.py vs opencode permission.asked)"
  echo "  py $py_blocked"; echo "  js $js_blocked"; exit 1; }
echo "  ok: blocked pair matches (hooks/blocked.py == opencode permission.asked)"

echo "PASS"
