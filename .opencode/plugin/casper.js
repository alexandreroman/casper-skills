/**
 * Casper integration for opencode.
 *
 * opencode has no shell hooks, so this in-process plugin observes the event
 * bus and drives the `casper` CLI. It writes nothing, anywhere: the guidance
 * file it points opencode at ships inside this plugin's own directory.
 *
 * One default export serves both opencode generations. opencode 1 calls
 * `server()`, which returns the handlers below. opencode 2 calls `setup()`,
 * the server part further down, and loads tui.js as the TUI part, which feeds
 * these same handlers from the terminal the workspace belongs to.
 *
 * Three things this has to get right, and which the tests pin down:
 *   - subagent sessions must not drive the sidebar, so only the root session
 *     is tracked;
 *   - busy/idle arrive repeatedly, so transitions are deduplicated;
 *   - nothing here may ever throw into opencode.
 *
 * Root discovery does not depend on seeing `session.created`: the plugin can
 * load after a session already exists, or miss the event entirely. So the
 * first session-scoped event seen while no root is known adopts that session
 * as root, provided a child lookup clears it. A failed lookup always reads
 * as "child" (skip), never as "adopt" — a missed update beats tracking the
 * wrong session.
 */
import { spawn, spawnSync } from "node:child_process"
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

// The skill this plugin ships, resolved the same way and for the same reason.
// Claude Code and Codex read `skills` out of the plugin manifest; opencode has
// no manifest to read, and it never looks inside an installed plugin for
// skills — it looks in a fixed set of folders, one of which the config hook
// below can add. So the skill travels with the plugin here too, instead of
// asking the user to symlink or copy it into their config.
const SKILLS_DIR = fileURLToPath(new URL("../../skills", import.meta.url))

const BLOCKED_EVENTS = new Set(["permission.asked", "permission.updated"])

// Mirrors hooks/lib/notified.py::_CASPER_CALL: a `casper` invocation in
// command position, so a `grep "casper notify"` does not read as one.
const CASPER_CALL = /(?:^|[;&|({\n])\s*casper\s+([a-z]+)/g

/**
 * The `casper` subcommands a tool call runs, in order. Empty for none.
 * Mirrors hooks/lib/notified.py::casper_subcommands.
 */
export function casperSubcommands(args) {
  let command = args?.command
  if (Array.isArray(command)) command = command.map(String).join("\n")
  if (typeof command !== "string") return []
  return [...command.matchAll(CASPER_CALL)].map((m) => m[1])
}

// What a permission is for, as its event names it. opencode 1.18.34 sends the
// permission's kind as a string (`permission: "bash"`) and `tool` as a
// reference to the call ({ messageID, callID }); older releases sent `tool`
// as a name, or `permission` as an object with a `type`.
function permissionName(props) {
  if (typeof props.tool === "string") return props.tool
  if (typeof props.permission === "string") return props.permission
  if (typeof props.permission?.type === "string") return props.permission.type
  return "an action"
}

// Default runner: fire-and-forget, detached, every failure swallowed.
let runner = (args) => {
  try {
    const child = spawn("casper", args, { stdio: "ignore", detached: true })
    child.on("error", () => {})
    child.unref()
  } catch {
    // spawn can throw synchronously (EACCES, ENOENT). Stay silent.
  }
}

// How long a read may block the event loop. Reads are synchronous on purpose
// (see `querier`), so this is the whole of what a wedged `casper` can cost.
const QUERY_TIMEOUT_MS = 1000

// Default querier: the read counterpart of `runner`, and blocking where that
// one is fire-and-forget, because the answer decides what the very next call
// reports. Mirrors hooks/lib/casper.py::query, including reading every failure
// — no CLI, no app, a timeout, a `casper` too old to know the verb — as "no
// answer" rather than as an error.
let querier = (args) => {
  try {
    const proc = spawnSync("casper", args, { encoding: "utf8", timeout: QUERY_TIMEOUT_MS })
    if (proc.status !== 0 || !proc.stdout) return null
    return JSON.parse(proc.stdout)
  } catch {
    return null
  }
}

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
 * The event handlers behind both opencode generations.
 *
 * opencode 1 calls them directly from its plugin hooks (`server`, below).
 * opencode 2 has no such hooks in the process that knows the workspace, so
 * its TUI part (tui.js) translates v2 events into these same calls — which is
 * why one set of handlers, pinned against the other agents by
 * tests/test_cross_agent_conformance.sh, serves both.
 *
 * `lookup(sessionID)` answers whether a session must not be adopted as root;
 * by default it asks opencode 1's `client.session.list()` whether the session
 * is a subagent's. It may throw or hang: both read as "skip", and that
 * verdict is cached, so `lookupTimeoutMs` (default 250) must cover a slow one.
 */
export function createHandlers({ client, lookup, lookupTimeoutMs } = {}) {
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
  const query = (args) => (inWorkspace() ? querier(args) : null)

  // Read the workspace back before reporting anything about it. The todo list
  // only ever describes bars this plugin set: a bar the agent drove by hand
  // with `casper progress set` is invisible to it, and so is a `blocked` the
  // agent reported for itself. Both reads always run, in this order, so the
  // argv a turn ending emits never depends on what it is about to find —
  // hooks/stop.py does the same, and the two are compared call for call.
  const endTurn = () => {
    const answer = query(["status", "get"])
    const state = answer && typeof answer === "object" ? answer.status ?? null : null
    const bar = query(["progress", "get"])
    const barUp = Boolean(bar && typeof bar === "object" && bar.progress != null)
    for (const args of turnEndActions(todos, state, barUp)) run(args)
    notified = null
  }

  // Advance `notified` for one tool call, as hooks/lib/notified.py's
  // observe_tool does. A call that only runs `casper` is bookkeeping and
  // leaves it alone. As on the other agents, tool.execute.before runs before
  // the call's permission is asked, so the dialog the agent announced lands
  // while the marker is "attached".
  const observeTool = (args) => {
    const subcommands = casperSubcommands(args)
    if (subcommands.includes("notify")) notified = "armed"
    else if (subcommands.length > 0) return
    else notified = notified === "armed" ? "attached" : null
  }

  // A lookup that fails or hangs must not be retried on every later event on
  // this hot path, so the negative verdict is cached exactly like a real
  // one, and a hanging client is bounded by a timer that is always cleared
  // so it cannot keep the process alive.
  const CHILD_LOOKUP_TIMEOUT_MS = lookupTimeoutMs ?? 250

  const skip = lookup ?? (async (sessionID) => {
    const sessions = await client?.session?.list?.()
    const found = sessions?.data?.find((s) => s.id === sessionID)
    return Boolean(found?.parentID)
  })

  const childCache = new Map()
  const isChild = async (sessionID) => {
    if (!sessionID) return true
    if (childCache.has(sessionID)) return childCache.get(sessionID)
    let timer
    try {
      const timedOut = new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error("child lookup timed out")), CHILD_LOOKUP_TIMEOUT_MS)
      })
      const result = Boolean(await Promise.race([skip(sessionID), timedOut]))
      childCache.set(sessionID, result)
      return result
    } catch {
      // On a failed or hung lookup, assume child and cache that verdict: a
      // missed update is better than driving the sidebar from a subagent,
      // and never adopting beats retrying a doomed round-trip forever.
      childCache.set(sessionID, true)
      return true
    } finally {
      clearTimeout(timer)
    }
  }

  // Resolves whether `sessionID` is the root for this run, adopting it as
  // root when none is known yet and the session is not a child. Once a root
  // is known this is a plain equality check; nothing re-triggers a lookup.
  const resolveRoot = async (sessionID) => {
    if (rootSessionID !== null) return sessionID === rootSessionID
    if (!sessionID) return false
    if (await isChild(sessionID)) return false
    rootSessionID = sessionID
    return true
  }

  return {
    async config(cfg) {
      // Point opencode at the guidance file and the skill folder this plugin
      // ships. Nothing is written: both already exist inside the plugin's own
      // directory, and cfg is mutated in memory only.
      if (!inWorkspace()) return
      try {
        cfg.instructions = [...(cfg.instructions ?? []), GUIDANCE_PATH]
        // `skills.paths` names folders *of* skill folders, so this registers
        // skills/casper as `casper`. A copy the user installed themselves
        // resolves to the same name and opencode keeps one of them, so the
        // two cannot pile up.
        cfg.skills = {
          ...(cfg.skills ?? {}),
          paths: [...(cfg.skills?.paths ?? []), SKILLS_DIR],
        }
      } catch {
        // Never let a malformed cfg object throw into opencode.
      }
    },

    // Fires as a tool call starts, before any permission it needs is asked
    // (measured on opencode 1.18.34), just like Claude Code and Codex's
    // PreToolUse. Unconditionally reassert "working" here, exactly like
    // that hook does with no dedup of its own, and set `busy` true again
    // (idempotently, if a busy event already set it) so the turn-end path
    // fires exactly one `done`. The `blocked` a permission reports is lifted
    // by permission.replied, below.
    async "tool.execute.before"(input, output) {
      const sessionID = input?.sessionID ?? null
      if (!(await resolveRoot(sessionID))) return
      busy = true
      run(["status", "set", "working"])
      observeTool(output?.args)
    },

    async event({ event }) {
      const type = event?.type
      const props = event?.properties ?? {}
      const sessionID = props.sessionID ?? props.info?.id ?? null

      if (type === "session.created") {
        const child = Boolean(props.info?.parentID)
        // Cache eagerly: by session.deleted the session is gone from list().
        if (sessionID) childCache.set(sessionID, child)
        if (child) return
        rootSessionID = sessionID
        busy = false
        todos = []
        notified = null
        run(["status", "set", "idle"])
        run(["progress", "clear"])
        run(["info", "clear"])
        return
      }

      if (type === "session.deleted") {
        // Drop the cache entry whoever the session was: this plugin lives for
        // the whole opencode process, and every subagent session that is only
        // ever cached and never uncached grows the map without bound.
        if (sessionID) childCache.delete(sessionID)
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
        busy = false
        todos = []
        notified = null
        return
      }

      if (!(await resolveRoot(sessionID))) return

      if (type === "todo.updated") {
        if (Array.isArray(props.todos)) todos = props.todos
        for (const args of progressActions(props.todos) ?? []) run(args)
        return
      }

      if (type === "session.status") {
        const kind = props.status?.type
        if (kind === "busy") {
          if (busy) return
          busy = true
          notified = null
          run(["status", "set", "working"])
        } else if (kind === "idle") {
          if (!busy) return
          busy = false
          endTurn()
        }
        // "retry" is neither a start nor an end; leave the state alone.
        return
      }

      if (type === "session.idle") {
        if (!busy) return
        busy = false
        endTurn()
        return
      }

      if (type === "session.error") {
        // The counterpart of Claude Code's StopFailure: a turn that ended on
        // an error instead of on an answer. Mirrors
        // EVENT_ACTIONS["turn-error"] — the state and nothing else, with the
        // bar left where the work stopped — and the conformance test pins the
        // two together.
        //
        // session.idle also fires around an error, so report error first and
        // clear the busy latch so the later idle does not overwrite it.
        busy = false
        notified = null
        run(["status", "set", "error"])
        return
      }

      if (BLOCKED_EVENTS.has(type)) {
        run(["status", "set", "blocked"])
        if (notified) return
        run(["notify", `--message=The agent needs your approval: ${permissionName(props)}`])
        return
      }

      // The counterpart of hooks/lib/dialog.py, with the event the hooks do
      // not get: the user answered. An approved call runs now, so the turn is
      // working again; rejected, the turn stops and waits to be told what to
      // do instead, which is still `blocked`. Turn end never writes over that.
      if (type === "permission.replied") {
        if (props.reply === "once" || props.reply === "always") {
          run(["status", "set", "working"])
        }
      }
    },
  }
}

// ---------------------------------------------------------------------------
// opencode 2
//
// opencode 2 runs plugins in one background server shared by every terminal
// on the machine, so this process's environment is whatever started that
// server, not the workspace a session runs in: the server part must never
// read CASPER_WORKSPACE_ID. The TUI part (tui.js) runs in the workspace's own
// terminal, knows the workspace, drives the sidebar, and tells this part over
// RPC that its location is a Casper workspace. Only then does this part add
// the guidance and the skill there.
// ---------------------------------------------------------------------------

// The RPC the TUI part calls. A plain object: opencode's `Rpc.define` only
// validates error names, and importing it would make this plugin depend on
// opencode's package, which opencode 1 does not ship.
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

/** Read a skill file into opencode 2's `Skill.Info`, or null if unreadable. */
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
 * opencode 2's server part. One instance per location (directory); inert
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
      // A copy the user installed themselves wins, as with opencode 1.
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
// path-loads the module.
//
// One default export serves both generations, as opencode documents: version
// 1 calls `server()`, version 2 calls `setup()` and ignores `server`.
const plugin = {
  id: "casper",
  server: async (input) => createHandlers(input ?? {}),
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
  setRunner(fn) { runner = fn },
  setQuerier(fn) { querier = fn },
}

export default plugin
