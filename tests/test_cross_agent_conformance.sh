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

# session.error is opencode's counterpart to Claude Code's StopFailure: a turn
# that ended on an error instead of on an answer. Both report the state and
# stop there, leaving the bar where the work stopped. The hook side is pinned
# against the table by tests/test_event_conformance.sh; this pins opencode's,
# so neither agent can start reconciling or notifying without the other.
got_error="$(node --input-type=module -e '
import plugin from "./.opencode/plugin/casper.js"
process.env.CASPER_WORKSPACE_ID = "test-ws"
const calls = []
const hooks = await plugin.server({ client: { session: { list: async () => ({ data: [{ id: "root" }] }) } } })
plugin.__test.setRunner((a) => calls.push(a))
const ev = (type, properties) => ({ event: { type, properties } })
await hooks.event(ev("session.created", { info: { id: "root" } }))
await hooks.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
calls.length = 0
await hooks.event(ev("session.error", { sessionID: "root" }))
console.log(JSON.stringify(calls))
')"

[ "$got_error" = "$(expected_for turn-error)" ] || {
  echo "FAIL: turn-error mismatch (EVENT_ACTIONS vs opencode session.error)"
  echo "  expected $(expected_for turn-error)"; echo "  got      $got_error"; exit 1; }
echo "  ok: turn-error matches (EVENT_ACTIONS == opencode session.error)"

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

# turn-end left EVENT_ACTIONS entirely: what a turn ending means depends on
# what the workspace is showing. Both agents read it back — the state, then
# whether a bar is up — and decide from that, so the reads are part of the argv
# compared here. Each side is driven with the same task state and the same
# canned answers, and the two argv streams must match call for call.

turn_end_py() {
  # $1: task list, the same fixture shape used for the progress mapping above,
  # written out as the on-disk session mirror hooks/stop.py reads. $2: what
  # `casper status get` answers. $3: 1 when `casper progress get` reports a bar.
  local fixture="$1" state="$2" bar="$3" dir
  dir="$(mktemp -d)"
  FIXTURE="$fixture" STATE="$state" BAR="$bar" MIRROR_DIR="$dir" python3 - <<'PY'
import json, os, subprocess, sys
sys.path.insert(0, "tests/lib")
from harness import CasperStub
tasks = json.loads(os.environ["FIXTURE"])
mirror = {str(i): t for i, t in enumerate(tasks)}
with open(os.path.join(os.environ["MIRROR_DIR"], "sid.json"), "w") as f:
    json.dump(mirror, f)
replies = CasperStub.replies(status=os.environ["STATE"], bar=os.environ["BAR"] == "1")
with CasperStub() as stub:
    subprocess.run(["hooks/stop.py"], input=json.dumps({"session_id": "sid"}),
                   env=stub.env(CLAUDE_PLUGIN_DATA=os.environ["MIRROR_DIR"], **replies),
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
const state = process.argv[2]
const bar = process.argv[3] === "1"
// The stub `casper` the Python side runs records the read verbs too, so this
// one has to as well, or the two streams could never compare equal.
plugin.__test.setQuerier((a) => {
  calls.push(a)
  const verb = a.join(" ")
  if (verb === "status get") return { status: state, workspace: "test-ws" }
  if (verb === "progress get") {
    return { progress: bar ? { total: 3, current: 2, label: "step" } : null, workspace: "test-ws" }
  }
  return null
})
const ev = (type, properties) => ({ event: { type, properties } })
const todos = JSON.parse(process.argv[1]).map(t => ({ content: t.label, status: t.status }))
await hooks.event(ev("session.created", { info: { id: "root" } }))
await hooks.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
await hooks.event(ev("todo.updated", { sessionID: "root", todos }))
calls.length = 0
await hooks.event(ev("session.status", { sessionID: "root", status: { type: "idle" } }))
console.log(JSON.stringify(calls))
' "$1" "$2" "$3"
}

READS_PREFIX='[["status","get"],["progress","get"]'

check_turn_end() {
  # $1: fixture, $2: state read back, $3: 1 when a bar is up, $4: what it is.
  local fixture="$1" state="$2" bar="$3" what="$4" py js
  py="$(turn_end_py "$fixture" "$state" "$bar")"
  js="$(turn_end_js "$fixture" "$state" "$bar")"
  [ "$py" = "$js" ] || {
    echo "FAIL: turn-end mismatch ($what)"
    echo "  py $py"; echo "  js $js"; exit 1; }
  # Both reads always run, in the same order, whatever they are about to find:
  # the argv a turn ending emits must not depend on the answers.
  case "$py" in
    "$READS_PREFIX"*) ;;
    *) echo "FAIL: turn-end does not read the workspace back first ($what)"
       echo "  expected prefix $READS_PREFIX"; echo "  got $py"; exit 1 ;;
  esac
  echo "  ok: turn-end matches, $what -> $py"
}

check_turn_end '[]' working 1 "no task state: a hand-driven bar holds the turn at working"
check_turn_end '[]' working 0 "no task state and no bar: the turn is over"
check_turn_end '[{"label":"a","status":"completed"}]' working 1 "every step finished"
check_turn_end '[{"label":"a","status":"completed"},{"label":"b","status":"in_progress"}]' working 1 "a step still in flight"
check_turn_end '[{"label":"a","status":"completed"},{"label":"b","status":"cancelled"}]' working 1 "the rest cancelled"
check_turn_end '[]' blocked 1 "a blocked agent is not reported over"
check_turn_end '[{"label":"a","status":"completed"}]' error 1 "an error keeps its state, the bar is still reconciled"

# session-end is a fixed constant on the hook side (test_event_conformance.sh
# pins hooks/session-end.sh against the table), but opencode reaches it through
# session.deleted, which the table cannot drive. It is the backstop for a bar
# turn-end now leaves standing, so the two agents have to agree about it.
js_session_end="$(node --input-type=module -e '
import plugin from "./.opencode/plugin/casper.js"
process.env.CASPER_WORKSPACE_ID = "test-ws"
const calls = []
const hooks = await plugin.server({ client: { session: { list: async () => ({ data: [{ id: "root" }] }) } } })
plugin.__test.setRunner((a) => calls.push(a))
const ev = (type, properties) => ({ event: { type, properties } })
await hooks.event(ev("session.created", { info: { id: "root" } }))
calls.length = 0
await hooks.event(ev("session.deleted", { sessionID: "root" }))
console.log(JSON.stringify(calls))
')"

[ "$js_session_end" = "$(expected_for session-end)" ] || {
  echo "FAIL: session-end mismatch (EVENT_ACTIONS vs opencode session.deleted)"
  echo "  expected $(expected_for session-end)"; echo "  got      $js_session_end"; exit 1; }
echo "  ok: session-end matches (EVENT_ACTIONS == opencode session.deleted)"

echo "PASS"
