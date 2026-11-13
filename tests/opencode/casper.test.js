// The sidebar handlers in casper.js, driven with opencode's events. The event
// shapes are the ones opencode 2.3.0 sent in a real session; tui.test.js
// replays full copies of them through the TUI part.
import { test, describe, beforeEach } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import plugin, {
  createHandlers, progressActions, readSkill, reconcileActions, turnEndActions,
} from "../../.opencode/plugin/casper.js"

// The repository root, as a URL, so a manifest path like "./skills/" resolves
// the same way the agents resolve it.
const PLUGIN_ROOT = new URL("../../", import.meta.url)

let calls
// What the stubbed `casper` answers the two read verbs with. Mutate it inside
// a test to put the workspace in the state that test is about; `build` resets
// it to "a turn under way, nothing on screen".
let answers
// What the TUI part's lookup answers: skip the subagent's session.
const fakeLookup = async (sessionID) => sessionID === "child"

// Every turn end reads the workspace back first, always in this order.
const READS = [["status", "get"], ["progress", "get"]]

async function build(lookup = fakeLookup) {
  calls = []
  answers = { status: "working", bar: false }
  const handlers = createHandlers({ lookup, lookupTimeoutMs: 50 })
  plugin.__test.setRunner((args) => { calls.push(args) })
  // A read is a call too, so it is recorded alongside the writes: every
  // assertion below is then a full account of what the plugin did, and the
  // real `casper` never runs from the suite. `null` stands for a CLI that
  // cannot answer at all.
  plugin.__test.setQuerier((args) => {
    calls.push(args)
    const verb = args.join(" ")
    if (verb === "status get") {
      return answers.status === null ? null : { status: answers.status, workspace: "test-ws" }
    }
    if (verb === "progress get") {
      if (answers.bar === null) return null
      const body = answers.bar ? { total: 3, current: 2, label: "step" } : null
      return { progress: body, workspace: "test-ws" }
    }
    return null
  })
  return handlers
}

const ev = (type, data) => ({ type, data })

describe("opencode plugin", () => {
  beforeEach(() => { process.env.CASPER_WORKSPACE_ID = "test-ws" })

  test("exports an opencode plugin definition", () => {
    assert.equal(plugin.id, "casper")
    assert.equal(typeof plugin.setup, "function")
  })

  test("root session.created resets the surfaces", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    assert.deepEqual(calls, [
      ["status", "set", "idle"], ["progress", "clear"], ["info", "clear"],
    ])
  })

  test("child session.created is ignored", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "child", parentID: "root" }))
    assert.deepEqual(calls, [])
  })

  test("busy then idle reports working then done", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    calls.length = 0
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    await h.handle(ev("session.execution.succeeded", { sessionID: "root" }))
    // No todo list was ever reported, so there is no task state to judge the
    // bar by, and nothing is on screen either: the turn is over.
    assert.deepEqual(calls, [
      ["status", "set", "working"], ...READS, ["status", "set", "done"]])
  })

  test("repeated busy reports working only once", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    calls.length = 0
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    assert.deepEqual(calls, [["status", "set", "working"]])
  })

  test("idle without a preceding busy reports nothing", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    calls.length = 0
    await h.handle(ev("session.execution.succeeded", { sessionID: "root" }))
    assert.deepEqual(calls, [])
  })

  test("a failed execution reports error, not done", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    calls.length = 0
    await h.handle(ev("session.execution.failed", { sessionID: "root", error: { type: "provider", message: "overloaded" } }))
    assert.deepEqual(calls, [["status", "set", "error"]])
  })

  test("permission.asked reports blocked and notifies", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    calls.length = 0
    await h.handle(ev("permission.asked", { sessionID: "root", action: "bash" }))
    assert.deepEqual(calls[0], ["status", "set", "blocked"])
    assert.equal(calls[1][0], "notify")
    assert.ok(calls[1][1].startsWith("--message="))
  })

  test("permission.asked names the permission by its action, in opencode 2.3.0's shape", async () => {
    // `source` is a reference to the call, not a name: reading an object as
    // one sent "The agent needs your approval: [object Object]" once already.
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    calls.length = 0
    await h.handle(ev("permission.asked", {
      id: "per_1", sessionID: "root", action: "shell", resources: ["touch b.txt"],
      save: ["touch *"], source: { type: "tool", messageID: "m", id: "c" },
    }))
    assert.deepEqual(calls[1], ["notify", "--message=The agent needs your approval: shell"])
  })

  test("a permission with no action still names something", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    calls.length = 0
    await h.handle(ev("permission.asked", { sessionID: "root", action: { kind: "odd" } }))
    assert.deepEqual(calls[1], ["notify", "--message=The agent needs your approval: an action"])
  })

  test("an approved permission reports working again", async () => {
    for (const reply of ["once", "always"]) {
      const h = await build()
      await h.handle(ev("session.created", { sessionID: "root" }))
      await h.handle(ev("permission.asked", { sessionID: "root", action: "bash" }))
      calls.length = 0
      await h.handle(ev("permission.replied", { sessionID: "root", requestID: "p", reply }))
      assert.deepEqual(calls, [["status", "set", "working"]], reply)
    }
  })

  test("a rejected permission stays blocked, through turn end", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    await h.handle(ev("permission.asked", { sessionID: "root", action: "bash" }))
    calls.length = 0
    await h.handle(ev("permission.replied", { sessionID: "root", requestID: "p", reply: "reject" }))
    assert.deepEqual(calls, [])
    answers.status = "blocked"
    await h.handle(ev("session.execution.succeeded", { sessionID: "root" }))
    assert.deepEqual(calls, READS)
  })

  test("session.deleted for the root reports done and clears the bar", async () => {
    // Session end is the backstop for a bar the agent set by hand: turn end
    // leaves that one standing, so nothing after this could ever drop it.
    // Mirrors hooks/session-end.sh and EVENT_ACTIONS["session-end"].
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    calls.length = 0
    await h.handle(ev("session.deleted", { sessionID: "root" }))
    assert.deepEqual(calls, [["status", "set", "done"], ["progress", "clear"]])
  })

  test("session.deleted for an untracked session is ignored", async () => {
    const h = await build()
    // No session.created has fired, so no root is bound.
    await h.handle(ev("session.deleted", { sessionID: "stranger" }))
    assert.deepEqual(calls, [])
  })

  test("a deleted child session is dropped from the child cache", async () => {
    // The TUI part lives as long as the terminal, so a cache entry that is
    // never uncached is an unbounded leak, one entry per subagent session.
    // Observable only through the lookup: re-asking about a forgotten id has
    // to look it up again.
    let listCalls = 0
    const h = await build(async () => { listCalls++; return false })
    await h.handle(ev("session.created", { sessionID: "child", parentID: "root" }))
    await h.handle(ev("session.execution.started", { sessionID: "child" }))
    assert.equal(listCalls, 0, "session.created should have cached the verdict")

    await h.handle(ev("session.deleted", { sessionID: "child" }))
    await h.handle(ev("session.execution.started", { sessionID: "child" }))
    assert.equal(listCalls, 1, "the entry survived session.deleted")
  })

  test("outside a Casper workspace nothing is emitted", async () => {
    delete process.env.CASPER_WORKSPACE_ID
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    assert.deepEqual(calls, [])
  })

  test("an unknown event is ignored", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    calls.length = 0
    await h.handle(ev("file.edited", { sessionID: "root", file: "x" }))
    assert.deepEqual(calls, [])
  })

  // The plugin can load after a session already exists, or miss
  // session.created entirely — rootSessionID must not stay null forever in
  // that case, or every later event is silently dropped.
  describe("root recovery without a prior session.created", () => {
    test("a non-child session-scoped event is adopted as root and tracked", async () => {
      const h = await build()
      await h.handle(ev("session.execution.started", { sessionID: "root" }))
      assert.deepEqual(calls, [["status", "set", "working"]])
    })

    test("a child session-scoped event is ignored, not adopted", async () => {
      const h = await build()
      await h.handle(ev("session.execution.started", { sessionID: "child" }))
      assert.deepEqual(calls, [])
    })

    test("a failed lookup is treated as a skip, never adopted as root", async () => {
      const h = await build(async () => { throw new Error("boom") })
      await h.handle(ev("session.execution.started", { sessionID: "root" }))
      assert.deepEqual(calls, [])
    })

    test("a failed lookup is cached and attempted only once per session id", async () => {
      let listCalls = 0
      const h = await build(async () => { listCalls++; throw new Error("boom") })
      await h.handle(ev("session.execution.started", { sessionID: "root" }))
      await h.handle(ev("session.execution.started", { sessionID: "root" }))
      await h.handle(ev("session.tool.success", { sessionID: "root", metadata: { todos: [] } }))
      assert.equal(listCalls, 1)
    })

    test("a hanging lookup is bounded by a timeout, cached as a skip, and does not stall the handler", async () => {
      let listCalls = 0
      const h = await build(() => { listCalls++; return new Promise(() => {}) })
      await h.handle(ev("session.execution.started", { sessionID: "root" }))
      assert.deepEqual(calls, [])
      await h.handle(ev("session.execution.started", { sessionID: "root" }))
      assert.equal(listCalls, 1)
    })
  })
})

describe("session.tool.called", () => {
  test("reasserts working after a permission is approved, so the turn does not stay blocked", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    await h.handle(ev("permission.asked", { sessionID: "root", action: "bash" }))
    // opencode is about to run the now-approved tool.
    calls.length = 0
    await h.handle(ev("session.tool.called", { sessionID: "root", input: {} }))
    assert.deepEqual(calls, [["status", "set", "working"]])

    // The busy latch must be true again, so a repeated execution start that
    // follows is deduplicated, and turn end fires exactly one
    // "done" rather than staying stuck or double-reporting.
    calls.length = 0
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    assert.deepEqual(calls, [])
    await h.handle(ev("session.execution.succeeded", { sessionID: "root" }))
    assert.deepEqual(calls, [...READS, ["status", "set", "done"]])
  })

  // The agent's own `casper notify` is the one notification of the wait it
  // announces; hooks/lib/notified.py keeps the same rule for the other agents.
  describe("after the agent's own casper notify", () => {
    const tool = (h, command) =>
      h.handle(ev("session.tool.called", { sessionID: "root", input: { command } }))
    const permission = async (h) => {
      calls.length = 0
      await h.handle(ev("permission.asked", { sessionID: "root", action: "bash" }))
      return calls
    }
    const started = async () => {
      const h = await build()
      await h.handle(ev("session.created", { sessionID: "root" }))
      await h.handle(ev("session.execution.started", { sessionID: "root" }))
      return h
    }

    test("a permission asked next only reports blocked", async () => {
      const h = await started()
      await tool(h, 'casper notify --message "Need your approval to deploy"')
      await tool(h, "casper status set blocked")
      assert.deepEqual(await permission(h), [["status", "set", "blocked"]])
    })

    test("a notify inside a brace group counts too", async () => {
      const h = await started()
      await tool(h, '[ -n "$CASPER_WORKSPACE_ID" ] && { casper notify --message="x"; casper status set blocked; } || true')
      assert.deepEqual(await permission(h), [["status", "set", "blocked"]])
    })

    test("the approved tool call is still covered, the one after it is not", async () => {
      const h = await started()
      await tool(h, 'casper notify --message "x"')
      await tool(h, "make deploy")
      assert.deepEqual(await permission(h), [["status", "set", "blocked"]])
      await tool(h, "make test")
      assert.equal((await permission(h)).length, 2)
    })

    test("mentioning casper notify is not notifying", async () => {
      const h = await started()
      await tool(h, 'grep -rn "casper notify" skills/')
      assert.equal((await permission(h)).length, 2)
    })

    test("turn end ends the episode", async () => {
      const h = await started()
      await tool(h, 'casper notify --message "x"')
      await h.handle(ev("session.execution.succeeded", { sessionID: "root" }))
      await h.handle(ev("session.execution.started", { sessionID: "root" }))
      assert.equal((await permission(h)).length, 2)
    })
  })

  test("on a child session it is ignored", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    calls.length = 0
    await h.handle(ev("session.tool.called", { sessionID: "child", input: {} }))
    assert.deepEqual(calls, [])
  })

  test("outside a Casper workspace nothing is emitted", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    calls.length = 0
    delete process.env.CASPER_WORKSPACE_ID
    try {
      await h.handle(ev("session.tool.called", { sessionID: "root", input: {} }))
      assert.deepEqual(calls, [])
    } finally {
      process.env.CASPER_WORKSPACE_ID = "test-ws"
    }
  })
})

describe("skill registration", () => {
  test("the skill the server part registers is the one the plugin manifests declare", () => {
    // Three agents, one skill folder. Claude Code and Codex get it from
    // .claude-plugin/plugin.json; opencode gets it from the server part, and
    // the two must not drift apart.
    const manifest = JSON.parse(
      readFileSync(new URL("../../.claude-plugin/plugin.json", import.meta.url)))
    const declared = fileURLToPath(new URL(manifest.skills, PLUGIN_ROOT))
    const skill = readSkill()
    assert.equal(skill.name, "casper")
    assert.equal(resolve(dirname(dirname(skill.path))), resolve(declared))
  })
})

describe("progress mirror", () => {
  test("empty list clears", () => {
    assert.deepEqual(progressActions([]), [["progress", "clear"]])
  })

  test("all completed clears", () => {
    assert.deepEqual(
      progressActions([{ content: "a", status: "completed" }]),
      [["progress", "clear"]])
  })

  test("reports position and label", () => {
    assert.deepEqual(progressActions([
      { content: "a", status: "completed" },
      { content: "b", status: "in_progress" },
      { content: "c", status: "pending" },
    ]), [["progress", "set", "--total", "3", "--current", "2", "--label=b"]])
  })

  // casper 0.1.3 and earlier read a separate value that starts with `-` as
  // an option and reject the whole call, so the bar silently never moved.
  test("the label is attached, so a leading dash survives", () => {
    assert.deepEqual(progressActions([{ content: "- fix x", status: "in_progress" }]),
      [["progress", "set", "--total", "1", "--current", "1", "--label=- fix x"]])
  })

  test("no labelled in-progress task is a no-op", () => {
    assert.equal(progressActions([{ content: "", status: "in_progress" }]), null)
  })

  // "cancelled" is opencode's alone — no other agent's task tool has it — and
  // it used to read as live work: a list whose remaining steps were all
  // cancelled had nothing in progress to relabel the bar with and nothing
  // finished enough to clear it, so the last label stood over stopped work.
  test("a wholly cancelled list clears rather than stranding the bar", () => {
    assert.deepEqual(progressActions([
      { content: "a", status: "completed" },
      { content: "b", status: "cancelled" },
    ]), [["progress", "clear"]])
    assert.deepEqual(progressActions([{ content: "a", status: "cancelled" }]),
      [["progress", "clear"]])
  })

  test("a cancelled step is counted as passed, not pending", () => {
    assert.deepEqual(progressActions([
      { content: "a", status: "completed" },
      { content: "b", status: "cancelled" },
      { content: "c", status: "in_progress" },
    ]), [["progress", "set", "--total", "3", "--current", "3", "--label=c"]])
  })

  test("a missing or non-array todos list is a no-op, not a throw", () => {
    assert.equal(progressActions(undefined), null)
    assert.equal(progressActions(null), null)
    assert.doesNotThrow(() => progressActions("not-an-array"))
    assert.equal(progressActions("not-an-array"), null)
  })

  test("a tool result with no todos list leaves the bar untouched", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    calls.length = 0
    await h.handle(ev("session.tool.success", { sessionID: "root", metadata: {} }))
    assert.deepEqual(calls, [])
  })

  test("the todo tool's result on the root session drives the bar", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    calls.length = 0
    await h.handle(ev("session.tool.success", { sessionID: "root", metadata: { todos: [
      { content: "a", status: "completed" },
      { content: "b", status: "in_progress" },
    ] }}))
    assert.deepEqual(calls, [
      ["progress", "set", "--total", "2", "--current", "2", "--label=b"]])
  })

  test("the todo tool's result on a child session is ignored", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    calls.length = 0
    await h.handle(ev("session.tool.success", { sessionID: "child", metadata: { todos: [
      { content: "b", status: "in_progress" }] }}))
    assert.deepEqual(calls, [])
  })
})

// The bar and the sidebar status are independent surfaces. Nothing but a
// session restart used to bring them back into agreement, so a bar set during
// a turn advertised a step of a finished todo list for every later turn.
describe("turn-end reconciliation", () => {
  test("a bar the agent drove by hand survives the turn boundary", async () => {
    // The regression: with no todo tool in play, `todos` is empty and there
    // is no task state entitled to judge the bar. Clearing it here wiped a
    // bar the agent had just set, seconds after a turn that ended to let
    // background work run — and nothing was left running to set it again.
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    calls.length = 0
    answers.bar = true
    await h.handle(ev("session.execution.succeeded", { sessionID: "root" }))
    assert.deepEqual(calls, [...READS, ["status", "set", "working"]])
  })

  test("a bar left standing over a finished todo list is cleared", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    await h.handle(ev("session.tool.success", { sessionID: "root", metadata: { todos: [
      { content: "a", status: "completed" },
      { content: "b", status: "completed" },
    ] }}))
    calls.length = 0
    answers.bar = true
    await h.handle(ev("session.execution.succeeded", { sessionID: "root" }))
    assert.deepEqual(calls, [...READS, ["status", "set", "done"], ["progress", "clear"]])
  })

  test("a genuinely in-flight task keeps its bar across the boundary", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    await h.handle(ev("session.tool.success", { sessionID: "root", metadata: { todos: [
      { content: "a", status: "completed" },
      { content: "b", status: "in_progress" },
    ] }}))
    calls.length = 0
    answers.bar = true
    await h.handle(ev("session.execution.succeeded", { sessionID: "root" }))
    assert.deepEqual(calls, [...READS, ["status", "set", "working"]])
  })

  test("an interrupted turn reconciles the same way a finished one does", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    await h.handle(ev("session.tool.success", { sessionID: "root", metadata: { todos: [
      { content: "a", status: "completed" },
    ] }}))
    calls.length = 0
    answers.bar = true
    await h.handle(ev("session.execution.interrupted", { sessionID: "root", reason: "user" }))
    assert.deepEqual(calls, [...READS, ["status", "set", "done"], ["progress", "clear"]])
  })

  test("a new session forgets the previous session's todos", async () => {
    // A finished list, so the stale entries are observable: had they survived
    // the new session.created, turn end would read them as work that is over
    // and clear a bar belonging to the session that just started.
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    await h.handle(ev("session.tool.success", { sessionID: "root", metadata: { todos: [
      { content: "b", status: "completed" }] }}))
    await h.handle(ev("session.created", { sessionID: "root" }))
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    calls.length = 0
    await h.handle(ev("session.execution.interrupted", { sessionID: "root", reason: "user" }))
    assert.deepEqual(calls, [...READS, ["status", "set", "done"]])
  })

  test("reconcileActions clears a list whose every step is finished", () => {
    assert.deepEqual(reconcileActions([{ content: "a", status: "completed" }]),
      [["progress", "clear"]])
    assert.deepEqual(reconcileActions([
      { content: "a", status: "completed" },
      { content: "b", status: "cancelled" },
    ]), [["progress", "clear"]])
  })

  test("reconcileActions leaves an in-flight list alone", () => {
    assert.deepEqual(reconcileActions([{ content: "a", status: "in_progress" }]), [])
    assert.deepEqual(reconcileActions([{ content: "a", status: "pending" }]), [])
  })

  test("reconcileActions leaves a hand-driven bar alone", () => {
    // An empty list is not a list that finished — it is a todo tool that
    // never reported anything, so the bar on screen was set by the agent
    // itself and there is no task state here entitled to clear it.
    assert.deepEqual(reconcileActions([]), [])
  })

  test("a turn that ends with every remaining step cancelled drops its bar", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    await h.handle(ev("session.tool.success", { sessionID: "root", metadata: { todos: [
      { content: "a", status: "completed" },
      { content: "b", status: "cancelled" },
    ] }}))
    calls.length = 0
    answers.bar = true
    await h.handle(ev("session.execution.succeeded", { sessionID: "root" }))
    assert.deepEqual(calls, [...READS, ["status", "set", "done"], ["progress", "clear"]])
  })

  test("a blocked agent is not reported over at turn end", async () => {
    // The guidance tells an agent to report `blocked` when it ends a turn
    // waiting on the user. Turn end fires straight after and used to overwrite
    // that verdict with one inferred from the turn boundary alone — the one
    // state nothing here can reach on its own.
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    calls.length = 0
    answers.status = "blocked"
    answers.bar = true
    await h.handle(ev("session.execution.succeeded", { sessionID: "root" }))
    assert.deepEqual(calls, READS)
  })

  test("an error is not reported over, but the bar is still reconciled", async () => {
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    await h.handle(ev("session.tool.success", { sessionID: "root", metadata: { todos: [
      { content: "a", status: "completed" },
    ] }}))
    calls.length = 0
    answers.status = "error"
    answers.bar = true
    await h.handle(ev("session.execution.succeeded", { sessionID: "root" }))
    assert.deepEqual(calls, [...READS, ["progress", "clear"]])
  })

  test("a casper that cannot answer ends the turn done", async () => {
    // An older CLI without the read verbs, or a stopped app: the turn ends
    // exactly as it did before either read existed.
    const h = await build()
    await h.handle(ev("session.created", { sessionID: "root" }))
    await h.handle(ev("session.execution.started", { sessionID: "root" }))
    calls.length = 0
    answers.status = null
    answers.bar = null
    await h.handle(ev("session.execution.succeeded", { sessionID: "root" }))
    assert.deepEqual(calls, [...READS, ["status", "set", "done"]])
  })

  test("turnEndActions: a bar still up once this is done holds the turn at working", () => {
    assert.deepEqual(turnEndActions([], "working", true), [["status", "set", "working"]])
    assert.deepEqual(turnEndActions([], "working", false), [["status", "set", "done"]])
    // Up right now, but about to be cleared: judged on what will be left.
    assert.deepEqual(turnEndActions([{ content: "a", status: "completed" }], "working", true),
      [["status", "set", "done"], ["progress", "clear"]])
  })

  test("turnEndActions: an asserted state is never reported over", () => {
    for (const state of ["blocked", "error"]) {
      assert.deepEqual(turnEndActions([], state, true), [])
      assert.deepEqual(turnEndActions([{ content: "a", status: "completed" }], state, true),
        [["progress", "clear"]])
    }
    // Everything turn end is there to decide between, including no answer.
    for (const state of ["working", "idle", "done", "unknown", null, undefined]) {
      assert.deepEqual(turnEndActions([], state, true), [["status", "set", "working"]])
    }
  })

  test("reconcileActions treats a non-array as no task state, not a throw", () => {
    assert.deepEqual(reconcileActions(undefined), [])
    assert.deepEqual(reconcileActions("not-an-array"), [])
  })
})
