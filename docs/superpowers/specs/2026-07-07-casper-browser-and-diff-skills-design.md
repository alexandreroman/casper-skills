# Casper browser and diff skills

## Purpose

The plugin currently ships one fallback skill, `casper-status`, for agent
states no hook can infer automatically. Casper's CLI also exposes `browser
open` and `diff open` subcommands that this plugin doesn't surface yet. This
adds two more fallback skills so Claude uses Casper's own browser panel and
diff view — instead of a system browser or plain-text diff output — when it
would help the user, while staying a no-op everywhere else.

## Components

### `skills/casper-browser/SKILL.md`

Triggers only when the user explicitly asks to see something in a browser
("montre-moi ça dans le navigateur", "open this in a browser", "let's see the
running app"). When that happens inside a Casper terminal workspace, Claude
runs:

```bash
casper browser open <url>
```

instead of a system browser or another tool. This does not change the
existing global guidance to verify UI/frontend changes in a browser before
declaring them done — it only changes *which* browser Claude reaches for when
a Casper workspace is available and the user has asked to see something.

### `skills/casper-diff/SKILL.md`

Triggers only when the user explicitly asks to see a diff — the full diff or
one for a particular file ("montre-moi le diff", "fais voir ce qui a changé
dans ce fichier", "je veux revoir le diff avant de commit"). Claude opens the
diff view in Casper, in addition to or instead of printing the diff as text:

```bash
casper diff open          # full diff
casper diff open <file>   # scrolled to one file
```

There is no automatic trigger before every commit — this skill never fires
unless the user asks.

### Guard rule (both skills)

Identical to `casper-status`: only invoke inside a Casper terminal workspace,
checked via the `CASPER_WORKSPACE_ID` environment variable the plugin sets in
every Casper terminal. If the CLI call fails or `casper` isn't found, ignore
the failure and continue the actual task — never let it block or interrupt
normal work.

### Tests

`tests/test_casper_browser_skill.sh` and `tests/test_casper_diff_skill.sh`,
mirroring `tests/test_casper_status_skill.sh`: assert the file exists, the
frontmatter has `name`/`description`, the guard rule is mentioned
(`CASPER_WORKSPACE_ID` or "Casper terminal"), and the relevant example
commands are present (`casper browser open` / `casper diff open`).

### Documentation

Update the README paragraph that currently introduces `casper-status` as "a
fallback skill" to describe all three fallback skills and what judgment call
each one covers.

## Out of scope

- No change to any existing hook.
- No automatic diff-before-commit behavior (considered and rejected in favor
  of on-request only).
- No new plugin.json/marketplace.json fields — existing keywords already
  cover this ("casper", "terminal", "workspace").
