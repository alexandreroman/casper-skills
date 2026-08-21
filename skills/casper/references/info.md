# Casper info panel

Every Casper workspace has **one** info panel: a single Markdown message,
shown behind a sidebar button that only appears while the message is
non-empty. It is the workspace's noticeboard — content the user can come
back to and re-read after the terminal has scrolled past it.

```bash
casper info set --message "..."   # replace the message
casper info clear                 # empty it, hide the button
```

Both print one line of JSON naming the workspace:

```json
{"workspace":"FF868B45-..."}
```

## Not persisted — display, never storage

**The message lives only in the running Casper app's memory.** Unlike the
workspace list, the inspector tab, or the browser panel's URL, it is *not*
written to Casper's session state, so it is gone when Casper quits or
restarts — and it comes back empty, with its button hidden, as if nothing
had been published.

The plugin wipes it as well whenever a **new** conversation starts (resuming or
compacting an existing session keeps it) — a message published by a previous
session describes work the new one knows nothing about.

That makes the panel a **display surface, not a record**. The rule that
follows from it:

> Never let the info panel be the only place something exists.

Anything that must survive belongs somewhere real first — a file in the
repo, a commit message, the conversation itself — and the panel then
*shows* it. Publishing a decision, a finding, or a hand-off note **only**
to the panel is how that information gets silently lost.

In practice: keep the Markdown you published in a file (see below) and
treat that file as the source of truth. Re-publishing after a restart is
then one `casper info set --file` away; reconstructing a lost panel from
memory is not.

## One message per workspace — `set` replaces

There is no append, no history, no list of messages. `casper info set`
**overwrites** whatever was there. To add to what's displayed, re-send the
**whole** document with the new part included.

So keep the document you published in a file (see below) for as long as
the panel is live, and rewrite that file rather than trying to reconstruct
the panel's content from memory. That copy is what makes both extending
the message and restoring it after a restart cheap.

## When to publish

- **Explicit request — always.** "mets ça dans le panneau d'info", "affiche
  ce résumé", "keep this where I can find it", "note that in the info
  panel", "épingle ça". The request itself is sufficient.
- **Your own judgment — when the result is worth consulting again.**
  Publish when you produce something the user will want to look up while
  the work continues, not just read once as it flies by:
  - a plan or a checklist the work will follow;
  - a summary of what changed and why, at the end of a substantial task;
  - review findings, a test/benchmark report, a migration checklist;
  - the practical handles of something you started — a dev-server URL, a
    test account, a port, the command to re-run it;
  - what's left to do, or what you need from the user before continuing.

Don't publish routine turn-by-turn chatter, a one-line answer, or anything
the user is reading right now in the conversation anyway. A panel that
fills with noise stops being worth opening.

### Not a substitute for the other surfaces

| Need | Use |
|---|---|
| Content to keep in view and re-read | **this file** — `casper info set` |
| "I need you *now*" (attention flag) | `casper notify --message "..."` |
| Agent state (blocked / error) | `references/status.md` |
| Step-by-step advancement of the current work | `references/progress.md` (your agent's task-tracking tool) |
| Something to watch running | `references/terminal.md` |

The info panel is silent — it never grabs attention. If the user must act
on what you published, `casper notify --message "..."` **as well**, and
keep that message short (the detail lives in the panel).

## How to publish

Three input modes — pick by shape, not by habit:

```bash
casper info set --message "Dev server on http://localhost:3000"   # short, single line
casper info set --file <path>                                     # a document you wrote
printf '%s\n' "$text" | casper info set -                         # from a pipeline
```

For anything multi-line — which is nearly every real message — **write a
Markdown temp file and pass `--file`**. Quoting a multi-line document into
`--message` is fragile, and the file doubles as the copy you edit for the
next `set`.

Put the file **outside any repository** (`mktemp` under the system temp
dir) so it can never be staged or committed, and give it a `.md`
extension. This temp copy backs the panel while the session runs; if the
content matters beyond that, its home is a real file in the repo and the
panel just mirrors it.

```bash
# mktemp only substitutes trailing Xs (BSD/macOS), so add the .md after.
info_file="$(mktemp /tmp/casper-info.XXXXXX)" && mv "$info_file" "$info_file.md" && info_file="$info_file.md"
cat > "$info_file" <<'EOF'
# Dev environment

- App: <http://localhost:3000>
- API: <http://localhost:3001>

Restart with `npm run dev` in the "dev" terminal.
EOF
casper info set --file "$info_file"
```

Keep `$info_file` around while the panel is live, so extending the message
— or restoring it after Casper restarts — is an edit plus one more
`casper info set --file "$info_file"`.

## Writing the message

It renders as Markdown, in the UI, for a human — so:

- Write it in the **user's language** (the language of this conversation),
  unlike agent-facing handoff documents, which stay English.
- Lead with a `#` heading naming what this is, so the panel is
  self-explanatory to someone opening it cold.
- Prefer short sections, lists, and fenced code for commands and paths;
  make URLs real links.
- Keep it scannable. A wall of prose in a side panel goes unread — if it
  needs that much text, it probably belongs in a file in the repo, with
  the panel pointing at it.
- State facts that stay true (paths, commands, decisions) rather than
  "just ran the tests" — the panel has no timestamp of its own.

An empty message is rejected:

```json
{"error":"empty message (use 'casper info clear' to empty the panel)"}
```

## Clearing

Clear it when the content stops being true — the task it described is
done and merged, the dev server it documented is gone, the user asks
("vide le panneau", "clear the info panel"):

```bash
casper info clear
```

A stale panel is worse than an empty one: it hides its own button when
empty, so clearing costs the user nothing. Don't clear a panel you didn't
publish without asking — it may hold something the user or another agent
put there.

## Targeting another workspace

Both subcommands accept `--workspace <id-or-name>` — the message is
per-workspace, and the default is the current one (`$CASPER_WORKSPACE_ID`):

```bash
casper info set --file "$info_file" --workspace <id-or-name>
casper info clear --workspace <id-or-name>
```

Use it to leave a message in a workspace you created for someone else's
instance to find (see `references/workspace.md` and `references/handoff.md`) — the
panel belongs to the workspace, addressed by its id or name, so you never
need a terminal open there to write into it. It still does not survive a
Casper restart, so pair it with something on disk whenever it matters.
Resolve the target with `casper workspace list` when you only have a
name.

If the command fails or `casper` isn't found, report the content in the
conversation instead.
