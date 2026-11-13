/**
 * Casper integration for opencode: the TUI part.
 *
 * opencode runs plugins' server parts in one background server shared by
 * every terminal, whose environment is not the workspace's. This part runs in
 * the terminal itself, so its CASPER_WORKSPACE_ID — and the `casper` calls it
 * spawns — belong to the workspace the user is looking at. It does two things:
 *
 *   - attaches the server part at this terminal's location, over RPC, so the
 *     guidance and the skill reach sessions there (see casper.js);
 *   - feeds opencode's events to the sidebar handlers in casper.js.
 *
 * Only root sessions at this terminal's location are tracked: the shared
 * server broadcasts every terminal's events to every TUI.
 */
import { CASPER_RPC, createHandlers } from "./casper.js"

const ATTACH_ATTEMPTS = 3
const ATTACH_BACKOFF_MS = 300
// Over HTTP to the shared server: give the lookup room, since a timed-out one
// is cached as "skip" for good.
const LOOKUP_TIMEOUT_MS = 2000

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// The generated client answers `{ data }`; plugin contexts answer the value.
const unwrap = (response) => response?.data ?? response

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

  const handlers = createHandlers({ lookup, lookupTimeoutMs: LOOKUP_TIMEOUT_MS })

  const handle = async (event) => {
    if (event?.type === "session.created") {
      const data = event.data ?? {}
      // A session elsewhere is not ours, and must not reset our sidebar.
      if (data.location?.directory !== directory) return
      // Re-attach: the server part forgets it was attached when opencode
      // reloads plugins. Not awaited — the sidebar must not wait on it.
      if (!data.parentID) void attach()
    }
    await handlers.handle(event)
  }

  // Events are handled one at a time, in arrival order: handlers await a
  // session lookup, and a turn's end must not overtake its start.
  let queue = Promise.resolve()
  const enqueue = (event) => {
    queue = queue.then(() => handle(event)).catch(() => {})
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

// Only a default export, so opencode, which also discovers this file as a
// server plugin in this repository's own .opencode/plugin/, finds nothing else
// to mistake for one. The helpers ride on `__test`, as in casper.js.
export default { id: "casper.tui", setup, __test: { createTuiHandlers } }
