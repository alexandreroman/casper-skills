# Casper Claude Code plugin

Wires Claude Code's own hook lifecycle to the [`casper`](https://github.com/alexandreroman/casper)
CLI, so a Casper workspace's sidebar state, progress bar, and notifications
update automatically while Claude works — no changes to Casper itself
required.

## What it does

| Hook | Casper action |
|---|---|
| `SessionStart` | `status set idle` + `progress clear` |
| `UserPromptSubmit` | `status set working` |
| `Stop` | `status set idle` + `notify --message "Claude is done and waiting for you"` |
| `Notification` | `notify --message "..."` |
| `SessionEnd` | `status set done` |
| `PostToolUse` (`TaskCreate`/`TaskUpdate`) | mirrors Claude's task list into `progress set`/`progress clear` |

Five fallback skills let Claude reach for the `casper` CLI itself for
judgment calls no hook can infer automatically:

- `casper-status` — call `casper status set blocked` / `casper status set
  error` for agent states no hook can detect.
- `casper-browser` — open a URL in Casper's browser panel when the user
  asks to see something in a browser, or close the panel when asked.
- `casper-diff` — open Casper's diff view when the user asks to see a diff,
  in full or for one file, or close it when asked.
- `casper-terminal` — open, list, and close terminals in the workspace,
  including on Claude's own judgment when a command should run somewhere
  visible or interactive rather than in the background.
- `casper-workspace` — list workspaces or resolve the current one anytime;
  create or delete a workspace (Git worktree) only on explicit request.

Every hook is a no-op outside a Casper terminal — it checks for
`$CASPER_WORKSPACE_ID` before doing anything, and never blocks or fails a
Claude Code turn even if Casper isn't running.

## Requirements

- [Casper](https://github.com/alexandreroman/casper) — the `casper` CLI is
  only reachable inside a terminal Casper opened.
- `python3` (ships with Xcode Command Line Tools) — needed for the
  `notification.py` and `post-tool-use-tasks.py` hooks.

## Installation

This repo self-hosts a plugin marketplace, so it can be installed directly
from Claude Code:

```
/plugin marketplace add alexandreroman/casper-claude-plugin
/plugin install casper@casper-claude-plugin
```

## Local development / testing

No marketplace or install step is needed for local development:

```bash
claude --plugin-dir /path/to/casper-claude-plugin
```

loads this plugin for that session only. Run it from inside a Casper
workspace terminal to see the hooks fire for real.

## Running the tests

```bash
for t in tests/test_*.sh; do bash "$t"; done
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
