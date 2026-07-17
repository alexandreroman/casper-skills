---
name: casper-browser
user-invocable: false
description: Open or close a URL in a Casper workspace's browser panel, and automate that page — screenshot it, read its console errors, inspect its DOM/HTML, evaluate JavaScript, click/type/press keys, and wait for conditions. Use when the user asks to see or open a URL (including a local dev server, preview, or running build), and when you (a coding agent) need to verify a frontend change end-to-end: check for console errors, capture a screenshot, or drive the running app. Only useful inside a Casper terminal workspace.
allowed-tools: Bash([ -n "$CASPER_WORKSPACE_ID" ]) Bash(casper browser *)
---

# Casper browser

Casper's browser panel is both a viewer (show the user a URL) and a
headless-automation surface you can drive from the terminal. Use the CLI
instead of a system browser or another tool whenever you're inside a Casper
terminal workspace.

## Showing a URL to the user

When the user asks to show or open a URL ("montre-moi ça dans le
navigateur", "open this in a browser", "let's see the running app"), open it
in the panel:

```bash
casper browser open <url>
```

Only `http` and `https` URLs are supported — the browser panel cannot open
`file:` (local files), `data:`, or other schemes. To view a local file,
serve it over HTTP first.

This very often concerns a **development version of an app** — a local dev
server, a preview build, or something the user is actively working on
("ouvre le serveur de dev", "open localhost:3000", "show me the preview",
"let's see it running on http://…"). Treat any request to open a dev-server
or running-app URL as a natural trigger. If you just started a dev server in
a Casper terminal, offering to open its URL here is a good default.

Close it when the user asks ("ferme le navigateur", "close the browser
panel", "hide the browser"):

```bash
casper browser close
```

## Development helper tools (for coding agents)

The panel doubles as a verification surface. After a frontend change, drive
the running app yourself instead of asking the user to eyeball it — this is
how you satisfy the standing guidance to verify UI/frontend changes in a
real browser before declaring them done.

| Command | Use it to |
|---------|-----------|
| `casper browser load <url>` | Load a URL in the background (no panel) — set up automation without disturbing the user's view. |
| `casper browser reload [--wait]` | Reload after a rebuild; `--wait` blocks until `readyState` is complete. |
| `casper browser wait [<selector>] [--js <expr>] [--visible] [--gone] [--timeout <ms>]` | Block until the DOM settles before asserting (default 5000 ms). |
| `casper browser console [--level <debug\|log\|info\|warn\|error>] [--clear]` | Read captured console output **and uncaught errors** — your primary "did it break?" signal. |
| `casper browser screenshot [--out <path>] [--url <url>] [--width <w>] [--height <h>]` | Save a PNG. Plain, it captures the visible browser panel. But as soon as you pass `--width`, `--height`, or `--url`, the capture happens **off-screen** — it renders at that viewport in a headless page without touching the user's visible panel, so responsive breakpoints render faithfully. |
| `casper browser content [--selector <sel>] [--raw]` | Print the page's HTML (whole document or one selector) to inspect rendered markup. |
| `casper browser eval <script> [--raw]` | Evaluate JavaScript and read a value back (assert state, read a store, probe globals). |
| `casper browser click <selector>` | Click the first matching element. |
| `casper browser type <selector> <text>` | Type text into the first matching element. |
| `casper browser key <key> [--selector <sel>]` | Dispatch a keydown/keyup (e.g. `Enter`, `Escape`); defaults to the focused element. |

Most commands print a JSON object (e.g. `{"result":…,"workspace":…}` or
`{"console":[…]}`); `eval` and `content` accept `--raw` to print just the
value or HTML. `wait` returns an `{"error":…}` object on timeout — treat
that as the condition not holding, not as a crash.

A typical verify loop after editing frontend code:

```bash
casper browser load http://localhost:3000       # or: reload --wait after a rebuild
casper browser wait "main" --visible
casper browser console --level warn              # any warnings/errors?
casper browser screenshot --out /tmp/after.png   # eyeball the render
```

You can then read the screenshot back with the Read tool, and drive
interactions (`click`/`type`/`key` → `wait` → `console`) to exercise a flow.

## Guard rule

Only invoke this skill inside a Casper terminal workspace. The plugin sets
the `CASPER_WORKSPACE_ID` environment variable in each Casper terminal it
opens — check for its presence with the same plain test the plugin's own
hooks use, not by echoing the variable:

```bash
[ -n "$CASPER_WORKSPACE_ID" ]
```

Every command targets that workspace by default; pass
`--workspace <id-or-name>` to address another one. This only works inside a
terminal Casper opened — if a command fails or `casper` isn't found, fall
back to telling the user the URL (or verifying another way) and continue;
never let it interrupt your actual task.
