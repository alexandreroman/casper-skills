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

got_start="$(node --input-type=module -e '
import plugin from "./.opencode/plugin/casper.js"
process.env.CASPER_WORKSPACE_ID = "test-ws"
const calls = []
const hooks = await plugin.server({ client: { session: { list: async () => ({ data: [{ id: "root" }] }) } } })
plugin.__test.setRunner((a) => calls.push(a))
const ev = (type, properties) => ({ event: { type, properties } })
await hooks.event(ev("session.created", { info: { id: "root" } }))
calls.length = 0
await hooks.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
console.log(JSON.stringify(calls))
')"

[ "$got_start" = "$(expected_for turn-start)" ] || {
  echo "FAIL: turn-start mismatch"; echo "  expected $(expected_for turn-start)"; echo "  got      $got_start"; exit 1; }

# progressActions (JS) must agree with actions_for (Python) on the same input.
# "cancelled" only ever arrives from opencode, but the predicate that reads it
# is shared, so both sides are held to it: a status one implementation counts
# as finished and the other as live work is exactly how a bar gets stranded.
check_progress() {
  local fixture="$1" what="$2" py js
  py="$(FIXTURE="$fixture" python3 -c "
import json, os
from hooks.lib.progress import actions_for
print(json.dumps(actions_for(json.loads(os.environ['FIXTURE'])), separators=(',', ':')))
")"
  js="$(node --input-type=module -e '
import { progressActions } from "./.opencode/plugin/casper.js"
const todos = JSON.parse(process.argv[1]).map(t => ({ content: t.label, status: t.status }))
console.log(JSON.stringify(progressActions(todos)))
' "$fixture")"
  [ "$py" = "$js" ] || {
    echo "FAIL: progress mismatch ($what)"; echo "  py $py"; echo "  js $js"; exit 1; }
  echo "  ok: progressActions == actions_for, $what -> $py"
}

check_progress '[{"label":"a","status":"completed"},{"label":"b","status":"in_progress"},{"label":"c","status":"pending"}]' \
               "a step in flight"
check_progress '[{"label":"a","status":"completed"},{"label":"b","status":"cancelled"}]' \
               "every remaining step cancelled"
check_progress '[{"label":"a","status":"completed"},{"label":"b","status":"cancelled"},{"label":"c","status":"in_progress"}]' \
               "a cancelled step behind the current one"

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

# turn-end is no longer a fixed constant: it reports done and then reconciles
# the progress bar against the agent's own task state, so a bar describing no
# live work cannot outlive the turn. The status call still comes from
# EVENT_ACTIONS (asserted below), but the pair as a whole is payload-dependent,
# so it gets the same drive-both-sides-and-compare treatment as the others.

turn_end_py() {
  # $1: task list, the same fixture shape used for the progress mapping above.
  # It is written out as the on-disk session mirror hooks/stop.py reads.
  local fixture="$1" dir
  dir="$(mktemp -d)"
  FIXTURE="$fixture" MIRROR_DIR="$dir" python3 - <<'PY'
import json, os, subprocess, sys
sys.path.insert(0, "tests/lib")
from harness import CasperStub
tasks = json.loads(os.environ["FIXTURE"])
mirror = {str(i): t for i, t in enumerate(tasks)}
with open(os.path.join(os.environ["MIRROR_DIR"], "sid.json"), "w") as f:
    json.dump(mirror, f)
with CasperStub() as stub:
    subprocess.run(["hooks/stop.py"], input=json.dumps({"session_id": "sid"}),
                   env=stub.env(CLAUDE_PLUGIN_DATA=os.environ["MIRROR_DIR"]),
                   text=True, capture_output=True)
    print(json.dumps(stub.calls, separators=(",", ":")))
PY
  rm -rf "$dir"
}

turn_end_js() {
  node --input-type=module -e '
import plugin from "./.opencode/plugin/casper.js"
process.env.CASPER_WORKSPACE_ID = "test-ws"
const calls = []
const hooks = await plugin.server({ client: { session: { list: async () => ({ data: [{ id: "root" }] }) } } })
plugin.__test.setRunner((a) => calls.push(a))
const ev = (type, properties) => ({ event: { type, properties } })
const todos = JSON.parse(process.argv[1]).map(t => ({ content: t.label, status: t.status }))
await hooks.event(ev("session.created", { info: { id: "root" } }))
await hooks.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
await hooks.event(ev("todo.updated", { sessionID: "root", todos }))
calls.length = 0
await hooks.event(ev("session.status", { sessionID: "root", status: { type: "idle" } }))
console.log(JSON.stringify(calls))
' "$1"
}

check_turn_end() {
  # $1: fixture, $2: human-readable description of what it represents.
  local fixture="$1" what="$2" py js
  py="$(turn_end_py "$fixture")"
  js="$(turn_end_js "$fixture")"
  [ "$py" = "$js" ] || {
    echo "FAIL: turn-end mismatch ($what)"
    echo "  py $py"; echo "  js $js"; exit 1; }
  # Whatever the payload, the status call is still the table's.
  case "$py" in
    "$(expected_for turn-end | sed 's/]$//')"*) ;;
    *) echo "FAIL: turn-end does not start with EVENT_ACTIONS[turn-end] ($what)"
       echo "  expected prefix $(expected_for turn-end)"; echo "  got $py"; exit 1 ;;
  esac
  echo "  ok: turn-end matches, $what -> $py"
}

check_turn_end '[]'                                                        "nothing tracked at all"
check_turn_end '[{"label":"a","status":"completed"}]'                      "every step finished"
check_turn_end '[{"label":"a","status":"completed"},{"label":"b","status":"in_progress"}]' "a step still in flight"
check_turn_end '[{"label":"a","status":"completed"},{"label":"b","status":"cancelled"}]'   "the rest cancelled"

echo "PASS"
