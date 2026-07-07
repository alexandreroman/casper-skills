---
name: casper-diff
description: Open a Casper workspace's diff view when the user explicitly asks to see a diff, in full or for a particular file. Only useful inside a Casper terminal workspace.
allowed-tools: Bash([ -n "$CASPER_WORKSPACE_ID" ]) Bash(casper diff open *)
---

# Casper diff

When the user explicitly asks to see a diff — the full diff or one for a
particular file ("montre-moi le diff", "fais voir ce qui a changé dans ce
fichier", "je veux revoir le diff avant de commit") — open it in Casper's
diff view, in addition to or instead of printing it as text:

```bash
casper diff open          # full diff
casper diff open <file>   # scrolled to one file
```

This only works inside a terminal Casper opened — if the command fails or
`casper` isn't found, fall back to the normal `git diff` output and
continue; never let it interrupt your actual task.

There is no automatic trigger before every commit — this skill only fires
when the user asks.

## Guard rule

Only invoke this skill inside a Casper terminal workspace. The plugin sets
the `CASPER_WORKSPACE_ID` environment variable in each Casper terminal it
opens — check for its presence with the same plain test the plugin's own
hooks use, not by echoing the variable:

```bash
[ -n "$CASPER_WORKSPACE_ID" ]
```

Then call the CLI as its own command.
