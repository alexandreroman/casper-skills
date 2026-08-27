import { test, describe, beforeEach } from "node:test"
import assert from "node:assert/strict"
import { existsSync, readFileSync } from "node:fs"
import { join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import plugin, { progressActions, reconcileActions } from "../../.opencode/plugin/casper.js"

// The repository root, as a URL, so a manifest path like "./skills/" resolves
// the same way the agents resolve it.
const PLUGIN_ROOT = new URL("../../", import.meta.url)

let calls
const fakeClient = {
  session: { list: async () => ({ data: [{ id: "root" }, { id: "child", parentID: "root" }] }) },
}

async function build(client = fakeClient) {
  calls = []
  const hooks = await plugin.server({ client, directory: "/tmp" })
  plugin.__test.setRunner((args) => { calls.push(args) })
  return hooks
}

const ev = (type, properties) => ({ event: { type, properties } })

describe("opencode plugin", () => {
  beforeEach(() => { process.env.CASPER_WORKSPACE_ID = "test-ws" })

  test("exports an id so it can be path-loaded", () => {
    assert.equal(plugin.id, "casper")
  })

  test("root session.created resets the surfaces", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    assert.deepEqual(calls, [
      ["status", "set", "idle"], ["progress", "clear"], ["info", "clear"],
    ])
  })

  test("child session.created is ignored", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "child", parentID: "root" } }))
    assert.deepEqual(calls, [])
  })

  test("busy then idle reports working then done", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    calls.length = 0
    await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
    await h.event(ev("session.status", { sessionID: "root", status: { type: "idle" } }))
    // No todo list was ever reported, so there is no task state to judge the
    // bar by and turn end leaves it alone.
    assert.deepEqual(calls, [
      ["status", "set", "working"], ["status", "set", "done"]])
  })

  test("repeated busy reports working only once", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    calls.length = 0
    await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
    await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
    assert.deepEqual(calls, [["status", "set", "working"]])
  })

  test("idle without a preceding busy reports nothing", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    calls.length = 0
    await h.event(ev("session.status", { sessionID: "root", status: { type: "idle" } }))
    assert.deepEqual(calls, [])
  })

  test("session.error reports error, not done", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
    calls.length = 0
    await h.event(ev("session.error", { sessionID: "root" }))
    assert.deepEqual(calls, [["status", "set", "error"]])
  })

  test("retry status changes nothing", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
    calls.length = 0
    await h.event(ev("session.status", { sessionID: "root", status: { type: "retry", attempt: 1 } }))
    assert.deepEqual(calls, [])
  })

  test("permission.asked reports blocked and notifies", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    calls.length = 0
    await h.event(ev("permission.asked", { sessionID: "root", tool: "bash" }))
    assert.deepEqual(calls[0], ["status", "set", "blocked"])
    assert.deepEqual(calls[1].slice(0, 2), ["notify", "--message"])
  })

  test("permission.updated is treated the same as permission.asked", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    calls.length = 0
    await h.event(ev("permission.updated", { sessionID: "root", tool: "bash" }))
    assert.deepEqual(calls[0], ["status", "set", "blocked"])
  })

  test("session.deleted for the root reports done and clears the bar", async () => {
    // Session end is the backstop for a bar the agent set by hand: turn end
    // leaves that one standing, so nothing after this could ever drop it.
    // Mirrors hooks/session-end.sh and EVENT_ACTIONS["session-end"].
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    calls.length = 0
    await h.event(ev("session.deleted", { sessionID: "root" }))
    assert.deepEqual(calls, [["status", "set", "done"], ["progress", "clear"]])
  })

  test("session.deleted for an untracked session is ignored", async () => {
    const h = await build()
    // No session.created has fired, so no root is bound.
    await h.event(ev("session.deleted", { sessionID: "stranger" }))
    assert.deepEqual(calls, [])
  })

  test("a deleted child session is dropped from the child cache", async () => {
    // The plugin lives for the whole opencode process, so a cache entry that
    // is never uncached is an unbounded leak, one entry per subagent session.
    // Observable only through the lookup: re-asking about a forgotten id has
    // to hit client.session.list() again.
    let listCalls = 0
    const client = {
      session: { list: async () => { listCalls++; return { data: [] } } },
    }
    const h = await build(client)
    await h.event(ev("session.created", { info: { id: "child", parentID: "root" } }))
    await h.event(ev("session.status", { sessionID: "child", status: { type: "busy" } }))
    assert.equal(listCalls, 0, "session.created should have cached the verdict")

    await h.event(ev("session.deleted", { sessionID: "child" }))
    await h.event(ev("session.status", { sessionID: "child", status: { type: "busy" } }))
    assert.equal(listCalls, 1, "the entry survived session.deleted")
  })

  test("outside a Casper workspace nothing is emitted", async () => {
    delete process.env.CASPER_WORKSPACE_ID
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    assert.deepEqual(calls, [])
  })

  test("an unknown event is ignored", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    calls.length = 0
    await h.event(ev("file.edited", { sessionID: "root", file: "x" }))
    assert.deepEqual(calls, [])
  })

  // The plugin can load after a session already exists, or miss
  // session.created entirely — rootSessionID must not stay null forever in
  // that case, or every later event is silently dropped.
  describe("root recovery without a prior session.created", () => {
    test("a non-child session-scoped event is adopted as root and tracked", async () => {
      const h = await build()
      await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
      assert.deepEqual(calls, [["status", "set", "working"]])
    })

    test("a child session-scoped event is ignored, not adopted", async () => {
      const h = await build()
      await h.event(ev("session.status", { sessionID: "child", status: { type: "busy" } }))
      assert.deepEqual(calls, [])
    })

    test("a failed child lookup is treated as a child, never adopted as root", async () => {
      const brokenClient = { session: { list: async () => { throw new Error("boom") } } }
      const h = await build(brokenClient)
      await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
      assert.deepEqual(calls, [])
    })

    test("a failed lookup is cached and attempted only once per session id", async () => {
      let listCalls = 0
      const brokenClient = { session: { list: async () => { listCalls++; throw new Error("boom") } } }
      const h = await build(brokenClient)
      await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
      await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
      await h.event(ev("todo.updated", { sessionID: "root", todos: [] }))
      assert.equal(listCalls, 1)
    })

    test("a hanging lookup is bounded by a timeout, cached as a child, and does not stall the handler", async () => {
      let listCalls = 0
      const hangingClient = { session: { list: () => { listCalls++; return new Promise(() => {}) } } }
      const h = await build(hangingClient)
      await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
      assert.deepEqual(calls, [])
      await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
      assert.equal(listCalls, 1)
    })
  })
})

describe("tool.execute.before", () => {
  test("reasserts working after a permission is approved, so the turn does not stay blocked", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
    await h.event(ev("permission.asked", { sessionID: "root", tool: "bash" }))
    // The permission is replied to (no dedicated handler for that), then
    // opencode is about to run the now-approved tool.
    calls.length = 0
    await h["tool.execute.before"]({ tool: "bash", sessionID: "root", callID: "1" })
    assert.deepEqual(calls, [["status", "set", "working"]])

    // The busy latch must be true again, so the repeated session.status
    // "busy" that follows is deduplicated, and turn end fires exactly one
    // "done" rather than staying stuck or double-reporting.
    calls.length = 0
    await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
    assert.deepEqual(calls, [])
    await h.event(ev("session.status", { sessionID: "root", status: { type: "idle" } }))
    assert.deepEqual(calls, [["status", "set", "done"]])
  })

  test("on a child session it is ignored", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    calls.length = 0
    await h["tool.execute.before"]({ tool: "bash", sessionID: "child", callID: "1" })
    assert.deepEqual(calls, [])
  })

  test("outside a Casper workspace nothing is emitted", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    calls.length = 0
    delete process.env.CASPER_WORKSPACE_ID
    try {
      await h["tool.execute.before"]({ tool: "bash", sessionID: "root", callID: "1" })
      assert.deepEqual(calls, [])
    } finally {
      process.env.CASPER_WORKSPACE_ID = "test-ws"
    }
  })
})

describe("guidance injection", () => {
  test("config hook adds the guidance file as an absolute path", async () => {
    const h = await build()
    assert.ok(h.config, "config hook is missing")
    const cfg = {}
    await h.config(cfg)
    assert.ok(cfg.instructions.some((p) => p.endsWith("guidance.md")),
      "config hook did not add the guidance file")
    assert.ok(cfg.instructions.every((p) => p.startsWith("/")),
      "instructions entry must be an absolute path")
  })

  test("existing instructions are preserved", async () => {
    const h = await build()
    assert.ok(h.config, "config hook is missing")
    const cfg = { instructions: ["/existing.md"] }
    await h.config(cfg)
    assert.ok(cfg.instructions.includes("/existing.md"))
  })

  test("outside a Casper workspace the config hook is a no-op", async () => {
    delete process.env.CASPER_WORKSPACE_ID
    try {
      const h = await build()
      assert.ok(h.config, "config hook is missing")
      const cfg = {}
      await h.config(cfg)
      assert.deepEqual(cfg, {})
    } finally {
      process.env.CASPER_WORKSPACE_ID = "test-ws"
    }
  })
})

describe("skill registration", () => {
  test("config hook registers the skill folder this plugin ships", async () => {
    const h = await build()
    const cfg = {}
    await h.config(cfg)
    assert.ok(cfg.skills?.paths?.length, "config hook registered no skill path")
    assert.ok(cfg.skills.paths.every((p) => p.startsWith("/")),
      "a skill path must be absolute")
  })

  test("the folder it registers really holds the casper skill", async () => {
    // opencode reads `skills.paths` entries as folders *of* skill folders, so
    // the thing that has to exist is <path>/casper/SKILL.md. Registering a
    // path that resolves to nothing fails silently at runtime: the skill is
    // simply never offered, which is the failure this pins.
    const h = await build()
    const cfg = {}
    await h.config(cfg)
    const registered = cfg.skills.paths.at(-1)
    assert.ok(existsSync(join(registered, "casper", "SKILL.md")),
      `no casper skill under ${registered}`)
  })

  test("it is the same folder the plugin manifests declare", async () => {
    // Three agents, one skill folder. Claude Code and Codex get it from
    // .claude-plugin/plugin.json; opencode gets it from the hook above, and
    // the two must not drift apart.
    const manifest = JSON.parse(
      readFileSync(new URL("../../.claude-plugin/plugin.json", import.meta.url)))
    const declared = fileURLToPath(new URL(manifest.skills, PLUGIN_ROOT))
    const h = await build()
    const cfg = {}
    await h.config(cfg)
    assert.equal(resolve(cfg.skills.paths.at(-1)), resolve(declared))
  })

  test("skill paths and other skill settings are preserved", async () => {
    const h = await build()
    const cfg = { skills: { paths: ["/existing/skills"], urls: ["https://example.com"] } }
    await h.config(cfg)
    assert.ok(cfg.skills.paths.includes("/existing/skills"))
    assert.deepEqual(cfg.skills.urls, ["https://example.com"])
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
    ]), [["progress", "set", "--total", "3", "--current", "2", "--label", "b"]])
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
    ]), [["progress", "set", "--total", "3", "--current", "3", "--label", "c"]])
  })

  test("a missing or non-array todos list is a no-op, not a throw", () => {
    assert.equal(progressActions(undefined), null)
    assert.equal(progressActions(null), null)
    assert.doesNotThrow(() => progressActions("not-an-array"))
    assert.equal(progressActions("not-an-array"), null)
  })

  test("todo.updated with a missing todos list leaves the bar untouched", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    calls.length = 0
    await h.event(ev("todo.updated", { sessionID: "root" }))
    assert.deepEqual(calls, [])
  })

  test("todo.updated on the root session drives the bar", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    calls.length = 0
    await h.event(ev("todo.updated", { sessionID: "root", todos: [
      { content: "a", status: "completed" },
      { content: "b", status: "in_progress" },
    ]}))
    assert.deepEqual(calls, [
      ["progress", "set", "--total", "2", "--current", "2", "--label", "b"]])
  })

  test("todo.updated on a child session is ignored", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    calls.length = 0
    await h.event(ev("todo.updated", { sessionID: "child", todos: [
      { content: "b", status: "in_progress" }]}))
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
    await h.event(ev("session.created", { info: { id: "root" } }))
    await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
    calls.length = 0
    await h.event(ev("session.status", { sessionID: "root", status: { type: "idle" } }))
    assert.deepEqual(calls, [["status", "set", "done"]])
  })

  test("a bar left standing over a finished todo list is cleared", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
    await h.event(ev("todo.updated", { sessionID: "root", todos: [
      { content: "a", status: "completed" },
      { content: "b", status: "completed" },
    ]}))
    calls.length = 0
    await h.event(ev("session.status", { sessionID: "root", status: { type: "idle" } }))
    assert.deepEqual(calls, [["status", "set", "done"], ["progress", "clear"]])
  })

  test("a genuinely in-flight task keeps its bar across the boundary", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
    await h.event(ev("todo.updated", { sessionID: "root", todos: [
      { content: "a", status: "completed" },
      { content: "b", status: "in_progress" },
    ]}))
    calls.length = 0
    await h.event(ev("session.status", { sessionID: "root", status: { type: "idle" } }))
    assert.deepEqual(calls, [["status", "set", "done"]])
  })

  test("session.idle reconciles the same way session.status idle does", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
    await h.event(ev("todo.updated", { sessionID: "root", todos: [
      { content: "a", status: "completed" },
    ]}))
    calls.length = 0
    await h.event(ev("session.idle", { sessionID: "root" }))
    assert.deepEqual(calls, [["status", "set", "done"], ["progress", "clear"]])
  })

  test("a new session forgets the previous session's todos", async () => {
    // A finished list, so the stale entries are observable: had they survived
    // the new session.created, turn end would read them as work that is over
    // and clear a bar belonging to the session that just started.
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
    await h.event(ev("todo.updated", { sessionID: "root", todos: [
      { content: "b", status: "completed" }]}))
    await h.event(ev("session.created", { info: { id: "root" } }))
    await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
    calls.length = 0
    await h.event(ev("session.idle", { sessionID: "root" }))
    assert.deepEqual(calls, [["status", "set", "done"]])
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
    await h.event(ev("session.created", { info: { id: "root" } }))
    await h.event(ev("session.status", { sessionID: "root", status: { type: "busy" } }))
    await h.event(ev("todo.updated", { sessionID: "root", todos: [
      { content: "a", status: "completed" },
      { content: "b", status: "cancelled" },
    ]}))
    calls.length = 0
    await h.event(ev("session.status", { sessionID: "root", status: { type: "idle" } }))
    assert.deepEqual(calls, [["status", "set", "done"], ["progress", "clear"]])
  })

  test("reconcileActions treats a non-array as no task state, not a throw", () => {
    assert.deepEqual(reconcileActions(undefined), [])
    assert.deepEqual(reconcileActions("not-an-array"), [])
  })
})
