/**
 * Casper integration for opencode 2: the TUI part.
 *
 * opencode 2 runs plugins' server parts in one background server shared by
 * every terminal, whose environment is not the workspace's. This part runs in
 * the terminal itself, so its CASPER_WORKSPACE_ID — and the `casper` calls it
 * spawns — belong to the workspace the user is looking at. It does two things:
 *
 *   - attaches the server part at this terminal's location, over RPC, so the
 *     guidance and the skill reach sessions there (see casper.js);
 *   - drives the sidebar by translating opencode 2's events into the events
 *     the shared handlers in casper.js already understand, so both opencode
 *     generations run one implementation, the one the conformance tests pin.
 *
 * Only root sessions at this terminal's location are tracked: the shared
 * server broadcasts every terminal's events to every TUI.
 */
import { CASPER_RPC, createHandlers } from "./casper.js"

const ATTACH_ATTEMPTS = 3
const ATTACH_BACKOFF_MS = 300
const LOOKUP_TIMEOUT_MS = 2000

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// The generated client answers `{ data }`; plugin contexts answer the value.
const unwrap = (response) => response?.data ?? response

/**
 * Map one opencode 2 event to the opencode 1 calls the shared handlers take.
 *
 * Returns `{ event }` for the `event` hook, `{ tool }` for
 * `tool.execute.before`, or null for an event that means nothing here.
 * Payload shapes are the ones opencode 2.3.0 sent in a real session; the
 * fixtures in tests/opencode/v2.test.js are copies of them.
 */
function translate(details) {
  const type = details?.type
  const data = details?.data ?? {}
  const sessionID = data.sessionID ?? null
  const v1 = (type, properties) => ({ event: { type, properties } })

  switch (type) {
    case "session.created":
      return v1("session.created", { info: { id: sessionID, parentID: data.parentID } })
    case "session.deleted":
      return v1("session.deleted", { info: { id: sessionID } })
    case "session.execution.started":
      return v1("session.status", { sessionID, status: { type: "busy" } })
    // An interruption ends the turn like an answer does: the user stopped
    // it, nothing failed.
    case "session.execution.succeeded":
    case "session.execution.interrupted":
      return v1("session.status", { sessionID, status: { type: "idle" } })
    case "session.execution.failed":
      return v1("session.error", { sessionID, error: data.error })
    // opencode 2 names the permission by its action ("shell", "edit", …).
    case "permission.asked":
      return v1("permission.asked", { sessionID, permission: data.action })
    case "permission.replied":
      return v1("permission.replied", { sessionID, reply: data.reply })
    // Fires as the call starts, before any permission it needs is asked —
    // opencode 1's tool.execute.before, with the arguments as `input`.
    case "session.tool.called":
      return { tool: [{ sessionID }, { args: data.input }] }
    // opencode 2 has no todo.updated: the todo tool's result carries the list.
    case "session.tool.success":
      if (!Array.isArray(data.metadata?.todos)) return null
      return v1("todo.updated", { sessionID, todos: data.metadata.todos })
    default:
      return null
  }
}

/**
 * The TUI part's behaviour, given its plugin context. Split from `setup` so
 * tests can feed it events and wait for each to be handled.
 */
function createTuiHandlers(context) {
  const location = context.location ?? context.data?.location?.default?.()
  const directory = location?.directory ?? null

  const attach = async () => {
    for (let attempt = 1; attempt <= ATTACH_ATTEMPTS; attempt++) {
      try {
        await context.client.rpc(CASPER_RPC).attach({}, { location })
        return true
      } catch {
        // The server part may not be up at this location yet.
        if (attempt < ATTACH_ATTEMPTS) await sleep(ATTACH_BACKOFF_MS * attempt)
      }
    }
    return false
  }

  // Skip subagents' sessions and every session of another location.
  const lookup = async (sessionID) => {
    const info = unwrap(await context.client.session.get({ sessionID }))
    return Boolean(info?.parentID) || info?.location?.directory !== directory
  }

  // Over HTTP to the shared server, not in process as on opencode 1: give the
  // lookup room, since a timed-out one is cached as "skip" for good.
  const handlers = createHandlers({ lookup, lookupTimeoutMs: LOOKUP_TIMEOUT_MS })

  const handle = async (details) => {
    if (details?.type === "session.created") {
      const data = details.data ?? {}
      // A session elsewhere is not ours, and must not reset our sidebar.
      if (data.location?.directory !== directory) return
      // Re-attach: the server part forgets it was attached when opencode
      // reloads plugins. Not awaited — the sidebar must not wait on it.
      if (!data.parentID) void attach()
    }
    const call = translate(details)
    if (!call) return
    if (call.event) await handlers.event(call)
    else await handlers["tool.execute.before"](...call.tool)
  }

  // Events are handled one at a time, in arrival order: handlers await a
  // session lookup, and a turn's end must not overtake its start.
  let queue = Promise.resolve()
  const enqueue = (details) => {
    queue = queue.then(() => handle(details)).catch(() => {})
    return queue
  }

  return { attach, enqueue }
}

async function setup(context) {
  // Outside a Casper terminal, or loaded somewhere that is not a TUI (opencode
  // also discovers this file as a server plugin in this repository's own
  // .opencode/plugin/), there is nothing to do.
  if (!process.env.CASPER_WORKSPACE_ID) return
  if (typeof context?.data?.listen !== "function") return
  try {
    const tui = createTuiHandlers(context)
    void tui.attach()
    const stop = context.data.listen((message) => { void tui.enqueue(message?.details) })
    return () => { try { stop() } catch {} }
  } catch {
    // Never throw into opencode.
  }
}

// Only a default export: opencode 1 auto-loads this file from this
// repository's own .opencode/plugin/, and gets no other export to mistake for
// a plugin. The helpers ride on `__test`, as in casper.js.
export default { id: "casper.tui", setup, __test: { translate, createTuiHandlers } }
