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
import { spawn } from "node:child_process"
import { fileURLToPath } from "node:url"

// Regex-stable on purpose: the Casper app probes the installed plugin file for
// this exact line to decide whether the integration is current. Keep it on one
// line, double-quoted, and in sync with package.json (a test asserts this).
export const CASPER_PLUGIN_VERSION = "0.2.0"

// Resolved against this module's own URL, not process.cwd(), so it works
// regardless of the process's working directory and of where opencode
// installed the plugin.
const GUIDANCE_PATH = fileURLToPath(new URL("./guidance.md", import.meta.url))

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

const inWorkspace = () => Boolean(process.env.CASPER_WORKSPACE_ID)

/**
 * Map an opencode todo list to casper argv.
 *
 * Mirrors hooks/lib/progress.py::actions_for. opencode sends the whole list on
 * every change, so unlike the Claude/Codex path there is no state to keep and
 * no lock to hold.
 */
export function progressActions(todos) {
  const total = todos.length
  const completed = todos.filter((t) => t.status === "completed").length

  if (total === 0 || completed === total) return [["progress", "clear"]]

  const current = todos.find((t) => t.status === "in_progress" && t.content)
  if (!current) return null

  return [["progress", "set",
           "--total", String(total),
           "--current", String(completed + 1),
           "--label", current.content]]
}

export function createHandlers({ client }) {
  let rootSessionID = null
  let busy = false

  const run = (args) => { if (inWorkspace()) runner(args) }

  const childCache = new Map()
  const isChild = async (sessionID) => {
    if (!sessionID) return true
    if (childCache.has(sessionID)) return childCache.get(sessionID)
    try {
      const sessions = await client?.session?.list?.()
      const found = sessions?.data?.find((s) => s.id === sessionID)
      const result = Boolean(found?.parentID)
      childCache.set(sessionID, result)
      return result
    } catch {
      // On a failed lookup, assume child: a missed update is better than
      // driving the sidebar from a subagent.
      return true
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
      // Point opencode at the guidance file this plugin ships. Nothing is
      // written: the file already exists inside the plugin's own directory,
      // and the array is mutated in memory only.
      if (!inWorkspace()) return
      try {
        cfg.instructions = [...(cfg.instructions ?? []), GUIDANCE_PATH]
      } catch {
        // Never let a malformed cfg object throw into opencode.
      }
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
        run(["status", "set", "idle"])
        run(["progress", "clear"])
        run(["info", "clear"])
        return
      }

      if (type === "session.deleted") {
        // Synchronous check only: a delete must never adopt. If this session
        // is not already the tracked root, ignore it — including the case
        // where no root is bound yet, which would otherwise flip the sidebar
        // to "done" for a session the plugin never tracked.
        if (rootSessionID === null || sessionID !== rootSessionID) return
        run(["status", "set", "done"])
        childCache.delete(sessionID)
        rootSessionID = null
        busy = false
        return
      }

      if (!(await resolveRoot(sessionID))) return

      if (type === "todo.updated") {
        for (const args of progressActions(props.todos ?? []) ?? []) run(args)
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
          run(["status", "set", "done"])
        }
        // "retry" is neither a start nor an end; leave the state alone.
        return
      }

      if (type === "session.idle") {
        if (!busy) return
        busy = false
        run(["status", "set", "done"])
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

// __test is attached to the default export (not just named) because tests
// import the plugin as a single default — `plugin.__test.setRunner(...)` —
// to mirror how opencode path-loads the module.
const plugin = {
  id: "casper",
  server: async (input) => createHandlers(input ?? {}),
}

plugin.__test = {
  createHandlers,
  setRunner(fn) { runner = fn },
}

export default plugin
export const __test = plugin.__test
