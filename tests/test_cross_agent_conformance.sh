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

echo "PASS"
