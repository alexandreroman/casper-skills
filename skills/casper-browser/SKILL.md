---
name: casper-browser
description: Open a URL in a Casper workspace's browser panel, or close the panel, when the user explicitly asks. Only useful inside a Casper terminal workspace.
allowed-tools: Bash([ -n "$CASPER_WORKSPACE_ID" ]) Bash(casper browser open *) Bash(casper browser close)
---

# Casper browser

When the user explicitly asks you to show something in a browser
("montre-moi ça dans le navigateur", "open this in a browser", "let's see
the running app"), and you're inside a Casper terminal workspace, open it in
Casper's browser panel instead of a system browser or another tool:

```bash
casper browser open <url>
```

When the user explicitly asks to close it ("ferme le navigateur", "close the
browser panel", "hide the browser"), collapse it instead:

```bash
casper browser close
```

This only works inside a terminal Casper opened — if the command fails or
`casper` isn't found, fall back to telling the user the URL (or opening it
another way) and continue; never let it interrupt your actual task.

This skill doesn't change the existing guidance to verify UI/frontend
changes in a browser before declaring them done — it only changes which
browser you reach for when a Casper workspace is available and the user has
asked to see something.

## Guard rule

Only invoke this skill inside a Casper terminal workspace. The plugin sets
the `CASPER_WORKSPACE_ID` environment variable in each Casper terminal it
opens — check for its presence with the same plain test the plugin's own
hooks use, not by echoing the variable:

```bash
[ -n "$CASPER_WORKSPACE_ID" ]
```

Then call the CLI as its own command:

```bash
casper browser open <url>
```
