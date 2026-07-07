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

A fallback skill (`casper-status`) lets Claude call `casper status set
blocked` / `casper status set error` itself for judgment calls no hook can
infer automatically.

Every hook is a no-op outside a Casper terminal — it checks for
`$CASPER_WORKSPACE_ID` before doing anything, and never blocks or fails a
Claude Code turn even if Casper isn't running.

## Requirements

- [Casper](https://github.com/alexandreroman/casper) — the `casper` CLI is
  only reachable inside a terminal Casper opened.
- `python3` (ships with Xcode Command Line Tools) — needed for the
  `notification.py` and `post-tool-use-tasks.py` hooks.

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
