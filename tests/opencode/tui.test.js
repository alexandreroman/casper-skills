// The TUI part (tui.js) and the server part (casper.js `setup`).
//
// Every event fixture below is a payload opencode 2.3.0 sent in a real session
// (2026-11-13), trimmed of fields nothing here reads. The sidebar handlers the
// TUI part feeds are tested on their own in casper.test.js.
import { test, describe, beforeEach } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import plugin, { CASPER_RPC, readSkill } from "../../.opencode/plugin/casper.js"
import tui from "../../.opencode/plugin/tui.js"

const { createTuiHandlers } = tui.__test

const DIR = "/private/tmp/ocprobe/work"
const ROOT = "ses_e2ba3338bffePhJHD0PKbMOx6P"
const CHILD = "ses_child"
const FOREIGN = "ses_elsewhere"

const GUIDANCE = readFileSync(
  fileURLToPath(new URL("../../.opencode/plugin/guidance.md", import.meta.url)), "utf8")

// --- real opencode 2.3.0 payloads -------------------------------------------

const created = (sessionID = ROOT, extra = {}) => ({
  id: "evt_1", type: "session.created", location: { directory: DIR },
  data: { sessionID, projectID: "global", location: { directory: DIR }, subpath: "",
          slug: "proud-panda", agent: "build", version: "2.3.0", ...extra },
})
const started = (sessionID = ROOT) => ({ type: "session.execution.started", data: { sessionID } })
const succeeded = (sessionID = ROOT) => ({ type: "session.execution.succeeded", data: { sessionID } })
const toolCalled = (input, sessionID = ROOT) => ({
  type: "session.tool.called",
  data: { sessionID, assistantMessageID: "msg_1", id: "call_1", input, executed: false },
})
const permissionAsked = (resources, sessionID = ROOT) => ({
  type: "permission.asked",
  data: { id: "per_1", sessionID, action: "shell", resources, save: ["ls *"],
          source: { type: "tool", messageID: "msg_1", id: "call_1" } },
})
const permissionReplied = (reply, sessionID = ROOT) => ({
  type: "permission.replied", data: { sessionID, requestID: "per_1", reply },
})
const todoSuccess = (todos, sessionID = ROOT) => ({
  type: "session.tool.success",
  data: { sessionID, assistantMessageID: "msg_1", id: "call_2",
          content: [{ type: "text", text: "Todos updated" }],
          metadata: { todos, truncated: false }, executed: false },
})

// --- harness ----------------------------------------------------------------

let calls
let answers

function stubCasper() {
  calls = []
  answers = { status: "working", bar: false }
  plugin.__test.setRunner((args) => { calls.push(args) })
  plugin.__test.setQuerier((args) => {
    calls.push(args)
    const verb = args.join(" ")
    if (verb === "status get") return { status: answers.status }
    if (verb === "progress get") return { progress: answers.bar ? { total: 2, current: 1 } : null }
    return null
  })
}

// What opencode's TUI client answers for a session.
const SESSIONS = {
  [ROOT]: { id: ROOT, location: { directory: DIR } },
  [CHILD]: { id: CHILD, parentID: ROOT, location: { directory: DIR } },
  [FOREIGN]: { id: FOREIGN, location: { directory: "/somewhere/else" } },
}

function tuiContext({ attachFails = 0 } = {}) {
  const attaches = []
  let failures = attachFails
  return {
    attaches,
    location: { directory: DIR },
    client: {
      rpc: (definition) => ({
        attach: async (input, options) => {
          attaches.push({ id: definition.id, input, options })
          if (failures-- > 0) throw { type: "rpc.unavailable" }
          return { attached: true }
        },
      }),
      // The session itself, not `{ data }`: measured on opencode 2.3.0.
      session: { get: async ({ sessionID }) => SESSIONS[sessionID] },
    },
    data: { listen: () => () => {}, location: { default: () => ({ directory: DIR }) } },
  }
}

async function feed(context, ...events) {
  const tuiHandlers = createTuiHandlers(context)
  for (const e of events) await tuiHandlers.enqueue(e)
  return tuiHandlers
}

const READS = [["status", "get"], ["progress", "get"]]

// --- the TUI part -----------------------------------------------------------

describe("TUI part", () => {
  beforeEach(() => {
    process.env.CASPER_WORKSPACE_ID = "test-ws"
    stubCasper()
  })

  test("default export is a TUI definition, and the module exports nothing else", async () => {
    // opencode also loads this file as a server plugin in this repository.
    assert.equal(typeof tui.id, "string")
    assert.equal(typeof tui.setup, "function")
    const mod = await import("../../.opencode/plugin/tui.js")
    assert.deepEqual(Object.keys(mod), ["default"])
  })

  test("outside a Casper terminal it does not even listen", async () => {
    delete process.env.CASPER_WORKSPACE_ID
    let listened = false
    const ctx = tuiContext()
    ctx.data.listen = () => { listened = true; return () => {} }
    assert.equal(await tui.setup(ctx), undefined)
    assert.equal(listened, false)
    assert.deepEqual(ctx.attaches, [])
  })

  test("loaded as a server plugin (no `data`), it does nothing and never throws", async () => {
    // opencode discovers .opencode/plugin/*.js as server plugins in this
    // repository's own checkout, so setup also meets a server context.
    assert.equal(await tui.setup({ location: { directory: DIR }, session: {} }), undefined)
    assert.deepEqual(calls, [])
  })

  test("setup attaches the server part at this terminal's location", async () => {
    const ctx = tuiContext()
    const stop = await tui.setup(ctx)
    await new Promise((r) => setTimeout(r, 0))
    assert.equal(typeof stop, "function")
    assert.deepEqual(ctx.attaches, [{ id: "casper", input: {}, options: { location: { directory: DIR } } }])
  })

  test("the listener survives being called with nothing", async () => {
    const ctx = tuiContext()
    let listener
    ctx.data.listen = (fn) => { listener = fn; return () => {} }
    await tui.setup(ctx)
    listener()
    listener({})
    await new Promise((r) => setTimeout(r, 0))
    assert.deepEqual(calls, [])
  })

  test("a session lookup slower than 250 ms still adopts the session", async () => {
    // The TUI asks the shared server over HTTP; a timed-out lookup is cached
    // as "skip" for good, which would leave a resumed session untracked.
    const ctx = tuiContext()
    const get = ctx.client.session.get
    ctx.client.session.get = async (input) => { await new Promise((r) => setTimeout(r, 400)); return get(input) }
    await feed(ctx, started(), succeeded())
    assert.deepEqual(calls, [["status", "set", "working"], ...READS, ["status", "set", "done"]])
  })

  test("attach retries while the server part is not up yet", async () => {
    const ctx = tuiContext({ attachFails: 1 })
    assert.equal(await createTuiHandlers(ctx).attach(), true)
    assert.equal(ctx.attaches.length, 2)
  })

  test("a turn with an approved shell call: working, blocked + notify naming the tool, working, done", async () => {
    await feed(tuiContext(),
      created(), started(),
      toolCalled({ command: "ls -la" }),
      permissionAsked(["ls -la"]),
      permissionReplied("once"),
      succeeded())
    assert.deepEqual(calls, [
      ["status", "set", "idle"], ["progress", "clear"], ["info", "clear"],
      ["status", "set", "working"],
      ["status", "set", "working"],
      ["status", "set", "blocked"],
      ["notify", "--message=The agent needs your approval: shell"],
      ["status", "set", "working"],
      ...READS,
      ["status", "set", "done"],
    ])
    for (const [verb, arg] of calls) {
      if (verb === "notify") assert.doesNotMatch(arg, /\[object Object\]/)
    }
  })

  test("the agent's own brace-group notify is not followed by a generic one", async () => {
    // opencode splits the brace group into one resource per command, so
    // with "casper *" allowed the `[ -n … ]` test still asks for approval.
    answers.status = "blocked"
    const command = '[ -n "$CASPER_WORKSPACE_ID" ] && { casper notify --message="Need your approval for git status"; casper status set blocked; } || true'
    await feed(tuiContext(),
      created(), started(),
      toolCalled({ command }),
      permissionAsked(['[ -n "$CASPER_WORKSPACE_ID" ]', 'casper notify --message="Need your approval for git status"', "casper status set blocked", "true"]),
      permissionReplied("once"),
      toolCalled({ command: "git status" }),
      permissionAsked(["git status"]),
      permissionReplied("once"),
      succeeded())
    assert.equal(calls.filter(([verb]) => verb === "notify").length, 0)
    // The agent's own `blocked` stands at turn end: no `done` over it.
    assert.deepEqual(calls.slice(-3), [["status", "set", "working"], ...READS])
  })

  test("todowrite results drive the progress bar", async () => {
    await feed(tuiContext(), created(), started(),
      todoSuccess([{ content: "List files", status: "in_progress" }, { content: "Count files", status: "pending" }]),
      todoSuccess([{ content: "List files", status: "completed" }, { content: "Count files", status: "completed" }]))
    assert.deepEqual(calls.slice(4), [
      ["progress", "set", "--total", "2", "--current", "1", "--label=List files"],
      ["progress", "clear"],
    ])
  })

  test("a failed execution reports error, and the busy latch keeps a later end from overwriting it", async () => {
    await feed(tuiContext(), created(), started(),
      { type: "session.execution.failed", data: { sessionID: ROOT, error: { type: "provider", message: "overloaded" } } },
      succeeded())
    assert.deepEqual(calls.slice(3), [["status", "set", "working"], ["status", "set", "error"]])
  })

  test("an interrupted execution ends the turn like an answer", async () => {
    await feed(tuiContext(), created(), started(),
      { type: "session.execution.interrupted", data: { sessionID: ROOT, reason: "user" } })
    assert.deepEqual(calls.slice(-3), [...READS, ["status", "set", "done"]])
  })

  test("another location's sessions never touch this sidebar", async () => {
    // The shared server broadcasts every terminal's events to every TUI.
    const elsewhere = created(FOREIGN)
    elsewhere.data.location = { directory: "/somewhere/else" }
    await feed(tuiContext(), elsewhere, started(FOREIGN),
      permissionAsked(["rm -rf /"], FOREIGN), succeeded(FOREIGN))
    assert.deepEqual(calls, [])
  })

  test("a subagent's session is not adopted as root", async () => {
    await feed(tuiContext(), created(CHILD, { parentID: ROOT }), started(CHILD), succeeded(CHILD))
    assert.deepEqual(calls, [])
  })

  test("a resumed session (no session.created seen) is adopted on its first event", async () => {
    await feed(tuiContext(), started(), succeeded())
    assert.deepEqual(calls, [["status", "set", "working"], ...READS, ["status", "set", "done"]])
  })

  test("a root session.created re-attaches the server part", async () => {
    const ctx = tuiContext()
    await feed(ctx, created())
    await new Promise((r) => setTimeout(r, 0))
    assert.equal(ctx.attaches.length, 1)
  })

  test("the streaming events of a real turn change nothing on their own", async () => {
    // Most of what opencode 2.3.0 sends during a turn is streaming; only the
    // events above may reach the sidebar.
    const tuiHandlers = await feed(tuiContext(), created(), started())
    calls.length = 0
    for (const e of [
      { type: "session.text.delta", data: { sessionID: ROOT, delta: "hi" } },
      { type: "session.step.started", data: { sessionID: ROOT } },
      { type: "session.tool.success", data: { sessionID: ROOT, metadata: { truncated: false } } },
      { type: "session.renamed", data: { sessionID: ROOT, title: "x" } },
    ]) await tuiHandlers.enqueue(e)
    assert.deepEqual(calls, [])
  })
})

// --- the server part --------------------------------------------------------

function serverContext() {
  const state = { rpc: null, transform: null, context: null, reloads: 0 }
  return {
    state,
    location: { directory: DIR },
    rpc: { register: async (definition, impl) => { state.rpc = { definition, impl } } },
    skill: {
      transform: async (fn) => { state.transform = fn },
      reload: async () => { state.reloads++ },
    },
    session: { hook: async (name, fn) => { if (name === "context") state.context = fn } },
  }
}

function runTransform(state, existing = []) {
  const skills = [...existing]
  state.transform({
    get: (id) => skills.find((s) => s.id === id),
    add: (s) => skills.push(s),
    list: () => skills,
  })
  return skills
}

describe("server part", () => {
  test("the default export is an opencode plugin definition", () => {
    assert.equal(plugin.id, "casper")
    assert.equal(typeof plugin.setup, "function")
  })

  test("it ignores the server process's CASPER_WORKSPACE_ID: inert until attached", async () => {
    // On opencode's shared server this variable belongs to whichever
    // terminal started the server (measured: ws-A while the session ran in ws-B).
    process.env.CASPER_WORKSPACE_ID = "ws-A"
    const ctx = serverContext()
    await plugin.setup(ctx)
    assert.equal(ctx.state.rpc.definition, CASPER_RPC)
    assert.deepEqual(runTransform(ctx.state), [])
    const event = { sessionID: ROOT, system: [{ type: "text", text: "core" }] }
    ctx.state.context(event)
    assert.equal(event.system.length, 1)
  })

  test("once attached: guidance on every model request and the casper skill", async () => {
    const ctx = serverContext()
    await plugin.setup(ctx)
    assert.deepEqual(await ctx.state.rpc.impl.attach({}), { attached: true })
    await ctx.state.rpc.impl.attach({})
    assert.equal(ctx.state.reloads, 1)

    const event = { sessionID: ROOT, system: [{ type: "text", text: "core" }] }
    ctx.state.context(event)
    assert.deepEqual(event.system[1], { type: "text", text: GUIDANCE })

    const [skill] = runTransform(ctx.state)
    assert.equal(skill.id, "casper")
    assert.equal(skill.name, "casper")
    assert.match(skill.description, /^Read this at the start of any session where CASPER_WORKSPACE_ID is set/)
    assert.match(skill.path, /skills\/casper\/SKILL\.md$/)
    assert.match(skill.content, /^\n?# Casper/)
  })

  test("a casper skill the user installed is kept", async () => {
    const ctx = serverContext()
    await plugin.setup(ctx)
    await ctx.state.rpc.impl.attach({})
    const mine = { id: "casper", name: "casper", path: "/mine/SKILL.md", content: "mine" }
    assert.deepEqual(runTransform(ctx.state, [mine]), [mine])
  })

  test("the RPC is registered last, so an early attach finds the transform and the hook", async () => {
    const order = []
    const ctx = serverContext()
    const { rpc, skill, session } = ctx
    ctx.rpc = { register: async (...a) => { order.push("rpc"); return rpc.register(...a) } }
    ctx.skill = { ...skill, transform: async (fn) => { order.push("transform"); return skill.transform(fn) } }
    ctx.session = { hook: async (...a) => { order.push("hook"); return session.hook(...a) } }
    await plugin.setup(ctx)
    assert.deepEqual(order, ["transform", "hook", "rpc"])
  })

  test("readSkill accepts CRLF line endings", async () => {
    const { mkdtempSync, writeFileSync } = await import("node:fs")
    const { tmpdir } = await import("node:os")
    const { join } = await import("node:path")
    const file = join(mkdtempSync(join(tmpdir(), "casper-skill-")), "SKILL.md")
    writeFileSync(file, "---\r\nname: casper\r\ndescription: Read this.\r\n---\r\n# Casper\r\n")
    const skill = readSkill(file)
    assert.equal(skill.name, "casper")
    assert.equal(skill.description, "Read this.")
    assert.match(skill.content, /^# Casper/)
  })

  test("a context that throws everywhere never throws into opencode", async () => {
    const boom = () => { throw new Error("boom") }
    await plugin.setup({ rpc: { register: boom }, skill: { transform: boom }, session: { hook: boom } })
    await plugin.setup({})
  })

  test("readSkill returns null for an unreadable file", () => {
    assert.equal(readSkill("/nonexistent/SKILL.md"), null)
  })
})
