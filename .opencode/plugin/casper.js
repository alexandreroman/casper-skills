/**
 * Casper integration for opencode.
 *
 * opencode has no shell hooks, so this in-process plugin observes the event
 * bus and drives the `casper` CLI. It writes nothing, anywhere: the guidance
 * file it points opencode at ships inside this plugin's own directory.
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
import { fileURLToPath } from "node:url"

// Regex-stable on purpose: the Casper app probes the installed plugin file for
// this exact line to decide whether the integration is current. Keep it on one
// line, double-quoted, and in sync with package.json (a test asserts this).
export const CASPER_PLUGIN_VERSION = "0.2.0"

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

  return [["progress", "set",
           "--total", String(todos.length),
           "--current", String(finished + 1),
           "--label", current.content]]
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

export function createHandlers({ client }) {
  let rootSessionID = null
  let busy = false
  // Last todo list seen, so turn end can reconcile the bar against it. Kept
  // in memory here for the same reason the Claude/Codex path keeps a mirror
  // on disk: the turn-end event carries no task state of its own.
  let todos = []

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
  }

  // A lookup that fails or hangs must not be retried on every later event on
  // this hot path, so the negative verdict is cached exactly like a real
  // one, and a hanging client is bounded by a timer that is always cleared
  // so it cannot keep the process alive.
  const CHILD_LOOKUP_TIMEOUT_MS = 250

  const childCache = new Map()
  const isChild = async (sessionID) => {
    if (!sessionID) return true
    if (childCache.has(sessionID)) return childCache.get(sessionID)
    let timer
    try {
      const timedOut = new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error("child lookup timed out")), CHILD_LOOKUP_TIMEOUT_MS)
      })
      const sessions = await Promise.race([client?.session?.list?.(), timedOut])
      const found = sessions?.data?.find((s) => s.id === sessionID)
      const result = Boolean(found?.parentID)
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

    // Fires immediately before opencode runs a tool call — including the
    // one a just-approved permission unblocked. Unconditionally reassert
    // "working" here, exactly like Claude Code and Codex's PreToolUse hook
    // does with no dedup of its own: a blocked state has nothing else that
    // clears it once the user has replied, and setting `busy` true again
    // (idempotently, if a busy event already set it) keeps the turn-end
    // path firing exactly one `done`.
    async "tool.execute.before"(input) {
      const sessionID = input?.sessionID ?? null
      if (!(await resolveRoot(sessionID))) return
      busy = true
      run(["status", "set", "working"])
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
        // session.idle also fires around an error, so report error first and
        // clear the busy latch so the later idle does not overwrite it.
        busy = false
        run(["status", "set", "error"])
        return
      }

      if (BLOCKED_EVENTS.has(type)) {
        run(["status", "set", "blocked"])
        const tool = props.tool ?? props.permission?.type ?? "an action"
        run(["notify", "--message", `The agent needs your approval: ${tool}`])
      }
    },
  }
}

// __test hangs off the default export because tests import the plugin as a
// single default — `plugin.__test.setRunner(...)` — mirroring how opencode
// path-loads the module.
const plugin = {
  id: "casper",
  server: async (input) => createHandlers(input ?? {}),
}

plugin.__test = {
  createHandlers,
  setRunner(fn) { runner = fn },
  setQuerier(fn) { querier = fn },
}

export default plugin
