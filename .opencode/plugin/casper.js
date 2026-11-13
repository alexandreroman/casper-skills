/**
 * Casper integration for opencode.
 *
 * opencode has no shell hooks, so this plugin observes opencode's events and
 * drives the `casper` CLI. It writes nothing, anywhere: the guidance and the
 * skill it hands opencode ship inside this plugin's own directory.
 *
 * It comes in two parts. This file is the server part (`setup`, further
 * down), and holds the sidebar handlers that tui.js, the TUI part, feeds from
 * the terminal the workspace belongs to.
 *
 * Three things this has to get right, and which the tests pin down:
 *   - subagent sessions must not drive the sidebar, so only the root session
 *     is tracked;
 *   - a turn's start is seen more than once (execution start, then each
 *     tool call), so transitions are deduplicated;
 *   - nothing here may ever throw into opencode.
 *
 * Root discovery does not depend on seeing `session.created`: the plugin can
 * load after a session already exists, or miss the event entirely. So the
 * first session-scoped event seen while no root is known adopts that session
 * as root, provided a lookup clears it. A failed lookup always reads as
 * "skip", never as "adopt" — a missed update beats tracking the
 * wrong session.
 */
import { spawn } from "node:child_process"
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"

// Regex-stable on purpose: the Casper app probes the installed plugin file for
// this exact line to decide whether the integration is current. Keep it on one
// line, double-quoted, and in sync with package.json (a test asserts this).
export const CASPER_PLUGIN_VERSION = "0.3.2"

// Resolved against this module's own URL, not process.cwd(), so it works
// regardless of the process's working directory and of where opencode
// installed the plugin.
const GUIDANCE_PATH = fileURLToPath(new URL("./guidance.md", import.meta.url))

// Mirrors hooks/lib/notified.py::_CASPER_CALL: a `casper` invocation in
// command position, so a `grep "casper notify"` does not read as one.
const CASPER_CALL = /(?:^|[;&|({\n])\s*casper\s+([a-z]+)/g

/**
 * The `casper` subcommands a shell call runs, in order. Empty for none.
 * Mirrors hooks/lib/notified.py::casper_subcommands.
 */
function casperSubcommands(input) {
  const command = input?.command
  if (typeof command !== "string") return []
  return [...command.matchAll(CASPER_CALL)].map((m) => m[1])
}

// How long one `casper` call may hold up the ones queued behind it. The call
// itself is never killed; the queue just stops waiting for it.
const RUN_TIMEOUT_MS = 2000

/**
 * A runner that starts `casper` calls one at a time, in the order they were
 * made, without making the caller wait. Calls used to be spawned all at
 * once, and the processes raced: in a real opencode 2.3.0 session a turn's
 * `working` landed before the `idle` of the session.created just before it,
 * leaving the sidebar idle while the agent worked. `settled()` resolves once
 * every call made so far has finished or timed out. Every failure is
 * swallowed.
 */
export function serialRunner(spawnCasper, timeoutMs = RUN_TIMEOUT_MS) {
  let tail = Promise.resolve()
  const runOne = (args) => new Promise((resolve) => {
    let timer
    const done = () => { clearTimeout(timer); resolve() }
    try {
      const child = spawnCasper(args)
      child.on("error", done)
      child.on("exit", done)
      child.unref?.()
      timer = setTimeout(done, timeoutMs)
      timer.unref?.()
    } catch {
      // spawn can throw synchronously (EACCES, ENOENT). Stay silent.
      done()
    }
  })
  return {
    run(args) { tail = tail.then(() => runOne(args)) },
    settled() { return tail },
  }
}

const defaultRunner = serialRunner(
  (args) => spawn("casper", args, { stdio: "ignore", detached: true }))

let runner = defaultRunner.run
let settled = defaultRunner.settled

// How long a read may take before it reads as "no answer".
const QUERY_TIMEOUT_MS = 1000

// Default querier: the read counterpart of `runner`. Mirrors
// hooks/lib/casper.py::query, including reading every failure — no CLI, no
// app, a timeout, a `casper` too old to know the verb — as "no answer" rather
// than as an error. Asynchronous, because the TUI part runs in opencode's
// terminal UI, which a blocking read would freeze.
let querier = (args) => new Promise((resolve) => {
  let timer
  const answer = (value) => { clearTimeout(timer); resolve(value) }
  try {
    const child = spawn("casper", args, { stdio: ["ignore", "pipe", "ignore"] })
    let out = ""
    timer = setTimeout(() => { try { child.kill() } catch {} answer(null) }, QUERY_TIMEOUT_MS)
    child.stdout.on("data", (chunk) => { out += chunk })
    child.on("error", () => answer(null))
    child.on("close", (code) => {
      if (code !== 0 || !out) return answer(null)
      try { answer(JSON.parse(out)) } catch { answer(null) }
    })
  } catch {
    answer(null)
  }
})

const inWorkspace = () => Boolean(process.env.CASPER_WORKSPACE_ID)

const CLEAR = [["progress", "clear"]]

// A step the bar will never advance to again. Mirrors
// hooks/lib/progress.py::FINISHED. opencode's todo tool is the only one of
// the three that can mark a step "cancelled", and counting that as live work
// is what used to strand the bar: a list whose remaining steps were all
// cancelled had nothing in progress to relabel it with and nothing finished
// enough to clear it, so the last label stood over work that had stopped.
const FINISHED = new Set(["completed", "cancelled"])

const finishedCount = (todos) => todos.filter((t) => FINISHED.has(t.status)).length

/**
 * True when a todo list describes no work the bar could honestly show.
 *
 * Mirrors hooks/lib/progress.py::nothing_in_flight, and is the single
 * predicate behind both mappings below for the same reason it is there.
 */
const nothingInFlight = (todos) =>
  todos.length === 0 || finishedCount(todos) === todos.length

/**
 * Map an opencode todo list to casper argv.
 *
 * Mirrors hooks/lib/progress.py::actions_for. opencode sends the whole list on
 * every change, so unlike the Claude/Codex path there is no state to keep and
 * no lock to hold.
 */
export function progressActions(todos) {
  if (!Array.isArray(todos)) return null

  if (nothingInFlight(todos)) return CLEAR

  const finished = finishedCount(todos)
  const current = todos.find((t) => t.status === "in_progress" && t.content)
  if (!current) return null

  // The label is attached, as in hooks/lib/progress.py: casper 0.1.3 and
  // earlier read a separate value that starts with `-` as an option and
  // reject the call.
  return [["progress", "set",
           "--total", String(todos.length),
           "--current", String(finished + 1),
           `--label=${current.content}`]]
}

/**
 * Map a todo list to the calls that make the bar honest at a turn boundary.
 *
 * Mirrors hooks/lib/progress.py::reconcile. The turn boundary is the one
 * moment the agent is known not to be running, so a list whose every step is
 * finished loses its bar there.
 *
 * An empty list is left alone instead. `todos` starts empty and stays empty
 * for as long as no todo tool has run, which is exactly the case where the
 * agent drove `casper progress` itself — a bar this plugin has no task state
 * to judge, and which is meant to survive the turn: work outlives a turn
 * boundary, and the sidebar still reports done/idle through the agent-state
 * icon. That bar goes when the agent clears it, or when the session ends.
 */
export function reconcileActions(todos) {
  const list = Array.isArray(todos) ? todos : []
  if (list.length === 0) return []
  return nothingInFlight(list) ? CLEAR : []
}

// States the agent reached on its own, about something outside the turn.
// Mirrors hooks/lib/progress.py::ASSERTED.
const ASSERTED = new Set(["blocked", "error"])

/**
 * Everything a turn ending emits, given what the workspace is showing.
 *
 * Mirrors hooks/lib/progress.py::turn_end_actions, and the rule is the same in
 * one line: a turn ends `working` when a bar is still up once this is done
 * with it, `done` otherwise — and nothing is reported over a `blocked` or an
 * `error`, verdicts the agent reached about something a turn boundary cannot
 * see. The bar is the shared account of whether the work is over, which is why
 * an agent that leaves one up over finished work holds its workspace at
 * `working` until the session ends.
 */
export function turnEndActions(todos, state, barUp) {
  const clears = reconcileActions(todos)
  if (ASSERTED.has(state)) return clears
  const stillUp = Boolean(barUp) && clears.length === 0
  return [["status", "set", stillUp ? "working" : "done"], ...clears]
}

/**
 * The sidebar handlers: one opencode event in, `casper` calls out.
 *
 * `handle` takes opencode's events as the TUI part receives them, `{ type,
 * data }`. Payload shapes are the ones opencode 2.3.0 sent in a real session;
 * tests/opencode/v2.test.js holds copies of them.
 *
 * `lookup(sessionID)` answers whether a session must not be adopted as root
 * (a subagent's, or one at another location). It may throw or hang: both read
 * as "skip", and that verdict is cached, so `lookupTimeoutMs` must cover a
 * slow answer — the TUI part's lookup is a round-trip to the shared server.
 * Without a lookup nothing is ever adopted.
 */
export function createHandlers({ lookup, lookupTimeoutMs = 2000 } = {}) {
  let rootSessionID = null
  let busy = false
  // Last todo list seen, so turn end can reconcile the bar against it. Kept
  // in memory here for the same reason the Claude/Codex path keeps a mirror
  // on disk: the turn-end event carries no task state of its own.
  let todos = []
  // Whether the agent already ran `casper notify` for the wait it is about to
  // open: null, "armed" or "attached". The same three states, and the same
  // reason, as hooks/lib/notified.py; in memory here, since this plugin lives
  // as long as the session does. A permission asked while it stands still
  // reports blocked, but the agent's own message is the only notification.
  let notified = null

  const run = (args) => { if (inWorkspace()) runner(args) }
  const query = async (args) => (inWorkspace() ? querier(args) : null)

  // Read the workspace back before reporting anything about it. The todo list
  // only ever describes bars this plugin set: a bar the agent drove by hand
  // with `casper progress set` is invisible to it, and so is a `blocked` the
  // agent reported for itself. Both reads always run, in this order, so the
  // argv a turn ending emits never depends on what it is about to find —
  // hooks/stop.py does the same, and the two are compared call for call.
  // Every write made before has landed by then, or the reads could answer
  // what the workspace showed before this turn.
  const endTurn = async () => {
    await settled()
    const answer = await query(["status", "get"])
    const state = answer && typeof answer === "object" ? answer.status ?? null : null
    const bar = await query(["progress", "get"])
    const barUp = Boolean(bar && typeof bar === "object" && bar.progress != null)
    for (const args of turnEndActions(todos, state, barUp)) run(args)
    notified = null
  }

  // Advance `notified` for one tool call, as hooks/lib/notified.py's
  // observe_tool does. A call that only runs `casper` is bookkeeping and
  // leaves it alone. As on the other agents, a call starts before its
  // permission is asked, so the dialog the agent announced lands while the
  // marker is "attached".
  const observeTool = (args) => {
    const subcommands = casperSubcommands(args)
    if (subcommands.includes("notify")) notified = "armed"
    else if (subcommands.length > 0) return
    else notified = notified === "armed" ? "attached" : null
  }

  // A lookup that fails or hangs must not be retried on every later event on
  // this hot path, so the negative verdict is cached exactly like a real
  // one, and a hanging lookup is bounded by a timer that is always cleared
  // so it cannot keep the process alive.
  const skipCache = new Map()
  const isSkipped = async (sessionID) => {
    if (!sessionID || typeof lookup !== "function") return true
    if (skipCache.has(sessionID)) return skipCache.get(sessionID)
    let timer
    try {
      const timedOut = new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error("session lookup timed out")), lookupTimeoutMs)
      })
      const result = Boolean(await Promise.race([lookup(sessionID), timedOut]))
      skipCache.set(sessionID, result)
      return result
    } catch {
      // On a failed or hung lookup, skip and cache that verdict: a missed
      // update is better than driving the sidebar from the wrong session, and
      // never adopting beats retrying a doomed round-trip forever.
      skipCache.set(sessionID, true)
      return true
    } finally {
      clearTimeout(timer)
    }
  }

  // Resolves whether `sessionID` is the root for this run, adopting it as
  // root when none is known yet and the lookup clears it. Once a root is
  // known this is a plain equality check; nothing re-triggers a lookup.
  const resolveRoot = async (sessionID) => {
    if (rootSessionID !== null) return sessionID === rootSessionID
    if (!sessionID) return false
    if (await isSkipped(sessionID)) return false
    rootSessionID = sessionID
    return true
  }

  const reset = () => {
    busy = false
    todos = []
    notified = null
  }

  return {
    async handle(event) {
      const type = event?.type
      const data = event?.data ?? {}
      const sessionID = data.sessionID ?? null

      if (type === "session.created") {
        const child = Boolean(data.parentID)
        // Cache eagerly: by session.deleted the session may be gone.
        if (sessionID) skipCache.set(sessionID, child)
        if (child) return
        rootSessionID = sessionID
        reset()
        run(["status", "set", "idle"])
        run(["progress", "clear"])
        run(["info", "clear"])
        return
      }

      if (type === "session.deleted") {
        // Drop the cache entry whoever the session was: the TUI lives as long
        // as the terminal, and every subagent session that is only ever
        // cached and never uncached grows the map without bound.
        if (sessionID) skipCache.delete(sessionID)
        // Synchronous check only: a delete must never adopt. If this session
        // is not already the tracked root, ignore it — including the case
        // where no root is bound yet, which would otherwise flip the sidebar
        // to "done" for a session the plugin never tracked.
        if (rootSessionID === null || sessionID !== rootSessionID) return
        run(["status", "set", "done"])
        // Session end is the backstop for a bar the agent set by hand and
        // never cleared: turn end deliberately leaves that one standing, and
        // nothing after this point could ever drop it. Mirrors
        // hooks/session-end.sh and EVENT_ACTIONS["session-end"].
        run(["progress", "clear"])
        rootSessionID = null
        reset()
        return
      }

      if (!(await resolveRoot(sessionID))) return

      switch (type) {
        case "session.execution.started":
          if (busy) return
          busy = true
          notified = null
          run(["status", "set", "working"])
          return

        // An interruption ends the turn like an answer does: the user stopped
        // it, nothing failed.
        case "session.execution.succeeded":
        case "session.execution.interrupted":
          if (!busy) return
          busy = false
          await endTurn()
          return

        case "session.execution.failed":
          // The counterpart of Claude Code's StopFailure: a turn that ended
          // on an error instead of on an answer. Mirrors
          // EVENT_ACTIONS["turn-error"] — the state and nothing else, with
          // the bar left where the work stopped — and the conformance test
          // pins the two together. Clearing the busy latch keeps a later end
          // event from writing over it.
          busy = false
          notified = null
          run(["status", "set", "error"])
          return

        // Fires as a tool call starts, before any permission it needs is
        // asked (measured on opencode 2.3.0), just like Claude Code and
        // Codex's PreToolUse. Unconditionally reassert "working" here,
        // exactly like that hook does with no dedup of its own, and set
        // `busy` again so the turn end fires exactly one `done`. The
        // `blocked` a permission reports is lifted by permission.replied.
        case "session.tool.called":
          busy = true
          run(["status", "set", "working"])
          observeTool(data.input)
          return

        // opencode has no todo event: the todo tool's result carries the
        // whole list, so there is no state to keep and no lock to hold.
        case "session.tool.success":
          if (!Array.isArray(data.metadata?.todos)) return
          todos = data.metadata.todos
          for (const args of progressActions(todos) ?? []) run(args)
          return

        // opencode names the permission by its action ("shell", "edit", …).
        case "permission.asked": {
          run(["status", "set", "blocked"])
          if (notified) return
          const action = typeof data.action === "string" ? data.action : "an action"
          run(["notify", `--message=The agent needs your approval: ${action}`])
          return
        }

        // The counterpart of hooks/lib/dialog.py, with the event the hooks do
        // not get: the user answered. An approved call runs now, so the turn
        // is working again; rejected, the turn stops and waits to be told what
        // to do instead, which is still `blocked`. Turn end never writes over
        // that.
        case "permission.replied":
          if (data.reply === "once" || data.reply === "always") {
            run(["status", "set", "working"])
          }
          return
      }
    },
  }
}

// ---------------------------------------------------------------------------
// The server part
//
// opencode runs plugins in one background server shared by every terminal
// on the machine, so this process's environment is whatever started that
// server, not the workspace a session runs in: the server part must never
// read CASPER_WORKSPACE_ID. The TUI part (tui.js) runs in the workspace's own
// terminal, knows the workspace, drives the sidebar, and tells this part over
// RPC that its location is a Casper workspace. Only then does this part add
// the guidance and the skill there.
// ---------------------------------------------------------------------------

// The RPC the TUI part calls. A plain object: opencode's `Rpc.define` only
// validates error names, and importing it would make this plugin depend on
// opencode's package: this one declares no dependencies.
export const CASPER_RPC = {
  id: "casper",
  methods: {
    attach: {
      input: { type: "object" },
      output: { type: "object" },
    },
  },
  events: {},
}

const SKILL_FILE = fileURLToPath(new URL("../../skills/casper/SKILL.md", import.meta.url))

/** Read a skill file into opencode's `Skill.Info`, or null if unreadable. */
export function readSkill(path = SKILL_FILE) {
  try {
    const text = readFileSync(path, "utf8")
    const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(text)
    if (!match) return null
    const field = (name) => new RegExp(`^${name}:[ \\t]*(.*?)\\r?$`, "m").exec(match[1])?.[1].trim()
    const name = field("name")
    if (!name) return null
    return { id: name, name, description: field("description"), path, content: match[2] }
  } catch {
    return null
  }
}

function readGuidance() {
  try {
    return readFileSync(GUIDANCE_PATH, "utf8")
  } catch {
    return null
  }
}

/**
 * The server part. One instance per location (directory); inert
 * until the TUI part attaches it. Every call into opencode is guarded: a
 * failure here leaves the session without guidance, never broken.
 */
export async function setupServer(ctx) {
  let attached = false
  const guidance = readGuidance()
  const skill = readSkill()

  try {
    await ctx.skill.transform((editor) => {
      if (!attached || !skill) return
      // A copy the user installed themselves wins.
      if (editor.get(skill.id)) return
      editor.add({ ...skill })
    })
  } catch {}

  try {
    // `context` runs before every agent-loop model request, with the system
    // prompt rebuilt each time, so pushing on every call is what keeps the
    // guidance there — and it reaches a session's very first request, which
    // an instruction entry put after `session.created` does not.
    await ctx.session.hook("context", (event) => {
      if (!attached || !guidance || !Array.isArray(event?.system)) return
      event.system.push({ type: "text", text: guidance })
    })
  } catch {}

  // Registered last: an `attach` arriving earlier would reload skills before
  // the transform above exists, and the skill would stay missing.
  try {
    await ctx.rpc.register(CASPER_RPC, {
      attach: async () => {
        if (!attached) {
          attached = true
          try { await ctx.skill.reload() } catch {}
        }
        return { attached: true }
      },
    })
  } catch {
    // Without the RPC nothing can attach; the part stays inert.
  }
}

// __test hangs off the default export because tests import the plugin as a
// single default — `plugin.__test.setRunner(...)` — mirroring how opencode
// loads the module.
const plugin = {
  id: "casper",
  setup: async (ctx) => {
    try {
      await setupServer(ctx)
    } catch {
      // Never throw into opencode.
    }
  },
}

plugin.__test = {
  createHandlers,
  setRunner(fn) { runner = fn; settled = () => Promise.resolve() },
  useRunner(serial) { runner = serial.run; settled = serial.settled },
  setQuerier(fn) { querier = fn },
}

export default plugin
