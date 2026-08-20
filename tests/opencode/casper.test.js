import { test, describe, beforeEach } from "node:test"
import assert from "node:assert/strict"
import plugin, { progressActions } from "../../.opencode/plugin/casper.js"

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
    assert.deepEqual(calls, [["status", "set", "working"], ["status", "set", "done"]])
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

  test("session.deleted for the root reports done", async () => {
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    calls.length = 0
    await h.event(ev("session.deleted", { sessionID: "root" }))
    assert.deepEqual(calls, [["status", "set", "done"]])
  })

  test("session.deleted for an untracked session is ignored", async () => {
    const h = await build()
    // No session.created has fired, so no root is bound.
    await h.event(ev("session.deleted", { sessionID: "stranger" }))
    assert.deepEqual(calls, [])
  })

  test("outside a Casper workspace nothing is emitted", async () => {
    delete process.env.CASPER_WORKSPACE_ID
    const h = await build()
    await h.event(ev("session.created", { info: { id: "root" } }))
    assert.deepEqual(calls, [])
  })

  test("an unknown event is ignored", async () => {
    const h = await build()
    await h.event(ev("file.edited", { file: "x" }))
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
