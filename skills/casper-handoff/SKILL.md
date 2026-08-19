---
name: casper-handoff
description: Hand off the current in-progress session to a fresh Casper workspace so another coding-agent instance can continue THIS session's work or reasoning with no loss of information. Use when the user wants to pass the baton — "passe la main à un nouveau workspace", "continue this in a fresh space", "hand off / prolonger le travail ailleurs", "reprends ça dans un nouveau workspace", or when the context window is filling up and the work should carry on cleanly elsewhere. Distinct from offloading a separate/tangential topic (that is casper-workspace). Only useful inside a Casper terminal workspace.
user-invocable: false
allowed-tools: AskUserQuestion Bash([ -n "$CASPER_WORKSPACE_ID" ]) Bash(casper workspace current) Bash(casper workspace list) Bash(casper workspace new *) Bash(casper notify *) Bash(casper info set *) Bash(git status --porcelain*) Bash(git rev-parse *) Bash(git branch*) Bash(git add *) Bash(git commit *) Bash(git log *) Bash(mktemp *) Bash(mv *)
---

# Casper session handoff

Pass the baton: move the **current, in-progress** session into a fresh
Casper workspace where a new agent instance picks up exactly where this one
left off — same objective, same decisions, same next steps — so the user
can prolong the work or the thinking in a clean space without losing
anything.

This is **not** offloading a tangential topic (that's `casper-workspace` —
delegating something separate while this session keeps going). A handoff
*continues this session's line of work* somewhere else, usually because the
context window is filling up, or the user simply wants a fresh space to
keep going.

## The two ways information gets lost

A handoff fails silently if either of these is ignored. Guard both.

1. **Blank context window.** The new instance cannot see this
   conversation. Every decision, rationale, dead-end already ruled out,
   constraint, and next step that lives only in this chat is gone unless
   you write it down.
2. **Uncommitted work stays behind.** `casper workspace new` branches from
   a **committed** ref. Your current staged/unstaged/untracked changes do
   **not** travel to the new worktree. Anything not committed is invisible
   to the new workspace.

The handoff request itself authorizes creating the workspace (and the WIP
commit below) — you don't need a separate "may I create a branch?"
confirmation, unlike the propose-don't-act rule for offloading.

## Procedure

1. Carry the in-progress code (WIP commit on the current branch).
2. Write a self-contained handoff document to a temp file outside the repo.
3. Create the new workspace **based on the current branch**, launching a
   fresh agent instance pointed at that document.
4. Tell the user where the work continued.

### Step 1: carry the in-progress code

```bash
git status --porcelain
git rev-parse --abbrev-ref HEAD    # the current branch — the handoff base
```

If the tree is dirty, the new worktree won't see those changes. Commit
them on the current branch so the new workspace (forked from this branch's
tip) contains them:

```bash
git add -A
git commit -m "WIP: handoff snapshot"
```

Tell the user you made this WIP commit and that it is reversible here with
`git reset --soft HEAD~1` if they want to keep editing in this session
too. A single WIP commit is the reliable way to guarantee the new
workspace starts from the real current state — prefer it over trying to
describe uncommitted changes in prose (that reintroduces loss). If the tree
is already clean, skip straight to Step 2.

### Step 2: write the handoff document (the completeness contract)

Write the context to a Markdown temp file **outside any repository** (so it
can never be staged or committed), exactly as `casper-workspace` describes
for handoff prompts — `mktemp` under the system temp dir, `.md` extension,
written in **English** regardless of this conversation's language.

The document is the whole point of "no loss of information." Include every
section below — this is a recipe to fill in, not a menu to pick from:

- **Objective** — what this work is ultimately trying to achieve.
- **Current state** — what's done so far and what actually works; name the
  branch and the WIP commit from Step 1 so the new instance knows where the
  code state lives.
- **Decisions & rationale** — choices already settled and *why*, so the new
  instance doesn't relitigate them.
- **Ruled out / dead-ends** — approaches already tried and rejected, and
  why, so it doesn't waste effort repeating them.
- **Open questions & blockers** — what's unresolved, and anything waiting on
  the user.
- **Next steps** — the concrete immediate actions to continue, in order.
- **Key files & locations** — the files central to the work, with paths.
- **Constraints** — conventions, rules, and things it must respect or avoid.
- **How to verify** — the tests or commands that confirm progress.

```bash
prompt_file="$(mktemp /tmp/casper-handoff.XXXXXX)" && mv "$prompt_file" "$prompt_file.md" && prompt_file="$prompt_file.md"
cat > "$prompt_file" <<'EOF'
# Session handoff

## Objective
...

## Current state
Branch `<branch>`, latest commit is a WIP snapshot ("WIP: handoff snapshot").
...

## Decisions & rationale
...

## Ruled out / dead-ends
...

## Open questions & blockers
...

## Next steps
1. ...

## Key files & locations
- path/to/file — ...

## Constraints
...

## How to verify
...
EOF
```

### Step 3: create the workspace and launch the continuing instance

Base the new workspace on the **current branch** (not the Space's primary
branch) so it forks from the WIP tip and continues the same line of work.
Launch a fresh instance of your own agent CLI with a short inline prompt
that just reads the handoff file — never `cat` the document inline. This is
the same launch mechanism documented in `casper-workspace`; follow its
rules for `--command` (retyped as literal keystrokes) and temp-file
prompts.

```bash
current_branch="$(git rev-parse --abbrev-ref HEAD)"
casper workspace new <name> \
  --base "$current_branch" \
  --command "<agent-cli> \"Read the handoff in $prompt_file and continue the work.\""
```

This prints the created workspace on one line:

```json
{"workspace":"<new-id>","name":"...","branch":"...","path":"..."}
```

Keep that `workspace` id — Step 4 reports it and can target it.

Substitute the CLI you're actually running (`claude`, `codex`, `gemini`,
…); if the user named one, use that. Pick a descriptive `<name>` for the
new workspace, or ask the user if it's unclear.

### Step 4: report the handoff

Tell the user which workspace/branch the work continued in (id and path
from the `casper workspace new` output) so they can switch to it. If they
need to act on it, you may also `casper notify --message "..."`.

You can also leave that summary in the new workspace's info panel, so the
user finds it when they switch there. Target the workspace by the
`workspace` id printed by `casper workspace new` in Step 3, and write the
note to its own temp file — it is *not* the handoff document, which stays
agent-facing and in English:

```bash
note_file="$(mktemp /tmp/casper-handoff-note.XXXXXX)" && mv "$note_file" "$note_file.md" && note_file="$note_file.md"
cat > "$note_file" <<'EOF'
# <title naming what was handed off>

<...a short, user-facing summary: what was handed off, where it stands,
and what happens next — written in this conversation's language...>
EOF
casper info set --workspace <new-id> --file "$note_file"
```

See the `casper-info` skill for how that panel behaves. It is a
convenience only: the message is in-memory and lost if Casper restarts, so
it never replaces the handoff file or the WIP commit as the thing that
actually carries the work.

## Common mistakes

- **Basing on `main` instead of the current branch** — the new instance
  starts from before this session's work. Always `--base` the current
  branch (with the WIP commit).
- **Thin handoff prompt** — "continue what I was doing" tells the blank
  instance nothing. Fill in the full contract above.
- **Skipping the WIP commit on a dirty tree** — the new worktree silently
  lacks your latest changes. Commit first.
- **Inlining the document into `--command`** — multi-line/quoted context is
  fragile as literal keystrokes. Always go through the temp file.

## Guard rule

Only invoke this skill inside a Casper terminal workspace. The plugin sets
the `CASPER_WORKSPACE_ID` environment variable in each Casper terminal it
opens — check for its presence with the same plain test the plugin's own
hooks use, not by echoing the variable:

```bash
[ -n "$CASPER_WORKSPACE_ID" ]
```

If the command fails or `casper` isn't found, tell the user and continue;
never let it interrupt your actual task.
