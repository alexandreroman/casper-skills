// The `casper` runner: calls run one at a time, in order, and a turn's end
// reads the workspace only once every earlier write has landed.
import { test, describe } from "node:test"
import assert from "node:assert/strict"
import { EventEmitter } from "node:events"
import plugin, { serialRunner } from "../../.opencode/plugin/casper.js"

// A fake `casper` process per call, finished by hand.
function fakeSpawn() {
  const started = []
  const children = []
  const spawnCasper = (args) => {
    const child = new EventEmitter()
    started.push(args.join(" "))
    children.push(child)
    return child
  }
  return { started, children, spawnCasper }
}

const tick = () => new Promise((r) => setTimeout(r, 0))

describe("serialRunner", () => {
  test("starts each call only once the one before has exited", async () => {
    const fake = fakeSpawn()
    const runner = serialRunner(fake.spawnCasper)
    runner.run(["status", "set", "idle"])
    runner.run(["status", "set", "working"])
    await tick()
    // The regression: both were spawned at once, and in a real opencode
    // 2.3.0 session `working` landed before `idle`.
    assert.deepEqual(fake.started, ["status set idle"])
    fake.children[0].emit("exit", 0)
    await tick()
    assert.deepEqual(fake.started, ["status set idle", "status set working"])
  })

  test("a call that fails to start does not hold up the rest", async () => {
    const fake = fakeSpawn()
    let first = true
    const runner = serialRunner((args) => {
      if (first) { first = false; throw new Error("ENOENT") }
      return fake.spawnCasper(args)
    })
    runner.run(["status", "set", "idle"])
    runner.run(["status", "set", "working"])
    await tick()
    assert.deepEqual(fake.started, ["status set working"])
  })

  test("a spawn error counts as finished", async () => {
    const fake = fakeSpawn()
    const runner = serialRunner(fake.spawnCasper)
    runner.run(["a"])
    runner.run(["b"])
    await tick()
    fake.children[0].emit("error", new Error("EACCES"))
    await tick()
    assert.deepEqual(fake.started, ["a", "b"])
  })

  test("a call that never exits holds the queue only until its timeout", async () => {
    const fake = fakeSpawn()
    const runner = serialRunner(fake.spawnCasper, 20)
    runner.run(["stuck"])
    runner.run(["next"])
    await new Promise((r) => setTimeout(r, 60))
    assert.deepEqual(fake.started, ["stuck", "next"])
  })

  test("settled resolves once every call so far has finished", async () => {
    const fake = fakeSpawn()
    const runner = serialRunner(fake.spawnCasper)
    let done = false
    runner.run(["a"])
    runner.settled().then(() => { done = true })
    await tick()
    assert.equal(done, false)
    fake.children[0].emit("exit", 0)
    await tick()
    assert.equal(done, true)
  })
})

describe("turn end", () => {
  test("reads the workspace back only after earlier writes have landed", async () => {
    process.env.CASPER_WORKSPACE_ID = "test-ws"
    const fake = fakeSpawn()
    const events = []
    plugin.__test.useRunner(serialRunner(fake.spawnCasper))
    plugin.__test.setQuerier(async (args) => {
      events.push(`read ${args.join(" ")}`)
      return args[0] === "status" ? { status: "working" } : { progress: null }
    })
    try {
      const h = plugin.__test.createHandlers({ lookup: async () => false })
      await h.handle({ type: "session.execution.started", data: { sessionID: "root" } })
      const ended = h.handle({ type: "session.execution.succeeded", data: { sessionID: "root" } })
      await tick()
      // `working` is still running: no read yet, or it could answer stale.
      assert.deepEqual(events, [])
      assert.deepEqual(fake.started, ["status set working"])
      fake.children[0].emit("exit", 0)
      await ended
      assert.deepEqual(events, ["read status get", "read progress get"])
      await tick()
      assert.deepEqual(fake.started, ["status set working", "status set done"])
    } finally {
      plugin.__test.setRunner(() => {})
    }
  })
})
