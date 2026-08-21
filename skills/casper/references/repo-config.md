# Casper config

Generate and maintain a repository's `.casper.json` — the per-repo file Casper
reads to **seed a newly created workspace** (which local files to copy in) and
to **run named commands** in a workspace (`casper run <name>`, plus the buttons
Casper shows in its UI).

This skill is an active generator: inspect the repo, propose sensible commands
and copy patterns, confirm with the user, then write (or merge into)
`.casper.json` at the repo root.

## The `.casper.json` schema

The file lives at the **repo root** and is grouped under a top-level
`workspace` object. Unknown keys are ignored, so a file that already carries
other sections still decodes.

```json
{
  "workspace": {
    "copyFiles": [".env", ".env.local"],
    "scripts": {
      "setup":    "npm install",
      "teardown": "docker compose down",
      "run":      "npm run dev",
      "test":     "npm test",
      "build":    "npm run build"
    }
  }
}
```

### `workspace.scripts` — named commands and lifecycle hooks

A map of name → shell command string.

- **`setup`** and **`teardown`** are **reserved lifecycle hooks**, not runnable
  via `casper run`:
  - `setup` runs **once**, in a visible split, at workspace **creation only**
    (never on restore/reopen). Use it to install dependencies or bootstrap the
    worktree.
  - `teardown` runs in a split when the workspace is **deleted or closed**; the
    workspace is pruned regardless of the hook's exit code or a timeout, so a
    broken teardown never blocks deletion. Use it for cleanup (stop containers,
    free ports, remove scratch state).
- **Every other name is a user-invocable command.** Run it with
  `casper run <name>`; it also appears as a button in the Casper UI. The default
  command is **`run`** (`casper run` with no argument). An empty command string
  is treated as no script. Command names may use `A–Z a–z 0–9 . _ -`; Casper
  derives the button label by splitting on `-`/`_` and capitalizing, so
  `build-app` shows as "Build App".

### `workspace.copyFiles` — seed local files into new worktrees

An optional array of `fnmatch(3)` patterns. When Casper creates a workspace
(a Git worktree), it copies every untracked file whose **basename** matches a
pattern from the repo root into the new worktree, recursively, skipping `.git`
and preserving POSIX permissions. This seeds a fresh worktree with local files
Git doesn't track — env files, secrets, local overrides — so the workspace is
runnable immediately.

- Omit the key (or set `null`) → Casper uses its defaults: `.env` and
  `.env.local`.
- Set an explicit `[]` → copy nothing.
- Patterns match the last path component only: `.env` matches literally
  anywhere in the tree; `*.local` matches any file ending in `.local`.

Only add `copyFiles` to **broaden** past the defaults (e.g. `.env.*`,
`config/*.local.json`). Never copy build artifacts, `node_modules`, or large
directories.

## Port remapping in parallel workspaces

Casper users routinely run **several workspaces at once**, each a separate Git
worktree on the same machine. Any project that binds **host ports** — a dev
server, a database, `docker compose` published ports, a metrics or preview
endpoint — will otherwise have those workspaces collide: the second `run` dies
with "address already in use", or two workspaces silently share one backend.

Casper handles the base case. It injects **`CASPER_PORT`** into every
workspace's environment (available in `setup`, `run`, and every named script),
unique per workspace, and **pre-reserves a band of 10 ports** — `CASPER_PORT`
through `CASPER_PORT + 10` — so a workspace can spread its services across that
range without ever colliding with another workspace.

### The pattern

1. **Derive every port from the base by a fixed offset** — never hard-code.
   Service *N* listens on `CASPER_PORT + N`. Keep all offsets within `+0..+10`
   (the reserved band); a project needing more than 11 distinct host ports has
   outgrown it and needs a different strategy.
2. **Remap only genuinely *published* ports.** Ports reachable only inside a
   container network (Docker `expose:`, not `ports:`) never collide across
   workspaces — leave them alone. Only the host-published ones need remapping.
3. **Do the remap in the `setup` hook**, guarded so it's a no-op outside
   Casper (`CASPER_PORT` unset in a plain checkout):

   ```bash
   [ -n "$CASPER_PORT" ] && <write the remap>
   ```

4. **Make `run` read or inherit the remapped ports** so the app binds exactly
   what the remap declared. Don't recompute the ports independently in two
   places — treat the file the hook wrote as the single source of truth.

### Example (docker compose)

Have `setup` write a `compose.override.yaml` (Compose auto-merges it) that
remaps only the published ports off `CASPER_PORT`, using `!override` to replace
each service's ports list:

```yaml
services:
  gateway:
    ports: !override
      - "${CASPER_PORT}:8080"          # host CASPER_PORT+0 → container 8080
  db:
    ports: !override
      - "$((CASPER_PORT + 1)):5432"    # host CASPER_PORT+1 → container 5432
```

This is *illustrative*, not a template to emit verbatim — adapt the services,
offsets, and the write-it-from-`setup` mechanics to the project's stack.

### Gotchas

- **The `run` process must inherit the remapped ports.** Launching a service by
  hand, bypassing the hook/env that carries the remapped values, falls back to
  the default port and fails to connect.
- **Remap internal callback URLs too.** If a service embeds a hard-coded URL
  pointing at another service's *original* host port (e.g. a UI callback or
  codec endpoint), the remap must rewrite that URL to the new port, or the
  feature breaks inside a worktree.
- **Free leftover ports after a crash.** A killed process can keep its port
  bound; a relaunch then fails until the holder is freed.
- **No auto-heal.** Don't try to regenerate the remap when it's missing (e.g. a
  worktree made with a plain `git worktree add`, where `setup` never ran). Rely
  on the `setup` hook and keep it minimal.

## Where the file goes, and why it must be committed

Always write to the **repo root**:

```bash
git rev-parse --show-toplevel
```

For `setup` and `copyFiles` to affect a **newly created** workspace, the
file must be **committed on the base branch** the new worktree forks from — a
new worktree only sees what's committed on its base. So after writing, offer to
commit `.casper.json`. (The `casper run` named commands and the UI buttons are
re-read live from the worktree, so those work as soon as the file is present,
committed or not — but committing is still the right default so every workspace
shares the same config.)

## Generating `.casper.json`

1. **Locate the root** with `git rev-parse --show-toplevel`. The file goes
   there, not in a subdirectory or the current worktree's own path.
2. **Never clobber an existing file.** If `.casper.json` already exists, read it
   and **merge** — add or change individual keys, preserve everything else
   (including unknown sections). Show the user the effective result before
   writing.
3. **Detect the stack and propose commands** (see the table below). Map what you
   find to `setup` (install/deps), `run` (the dev/serve command — this becomes
   the default `casper run`), `test`, `build`, and `teardown` (only when there's
   something to tear down, e.g. a `docker-compose.yml`).
   - **If the repo publishes host ports** (a `docker-compose.yml` with `ports:`,
     a dev server on a fixed port), also **propose** folding a
     `CASPER_PORT`-based remap into the `setup` hook so parallel workspaces
     don't collide — see [Port remapping in parallel workspaces](#port-remapping-in-parallel-workspaces).
     Suggest it and confirm with the user; don't silently generate a bespoke
     remap.
4. **Propose `copyFiles` only when the repo needs more than the defaults.**
   Skim `.gitignore` for local runtime files (`.env*`, `*.local`, …). If the
   defaults (`.env`, `.env.local`) already cover it, leave the key out.
5. **Confirm the proposed JSON with the user before writing.** Present the exact
   content; use `AskUserQuestion` if you want an explicit yes. Then write the
   file and **offer to commit it**.
6. **Verify** (see below) if you're inside a Casper workspace.

## Ecosystem detection table

Use these as starting proposals — always prefer commands the project already
defines (e.g. the actual scripts in `package.json`) over guesses.

| Detected file | setup | run (default) | test | build |
|---|---|---|---|---|
| `package.json` (npm) | `npm install` | `npm run dev` / `npm start` | `npm test` | `npm run build` |
| `package.json` + `pnpm-lock.yaml` | `pnpm install` | `pnpm dev` | `pnpm test` | `pnpm build` |
| `package.json` + `yarn.lock` | `yarn install` | `yarn dev` | `yarn test` | `yarn build` |
| `pyproject.toml` + `uv.lock` | `uv sync` | `uv run <app>` | `uv run pytest` | — |
| `pyproject.toml` (poetry) | `poetry install` | `poetry run <app>` | `poetry run pytest` | `poetry build` |
| `requirements.txt` | `pip install -r requirements.txt` | `python <app>.py` | `pytest` | — |
| `go.mod` | `go mod download` | `go run .` | `go test ./...` | `go build ./...` |
| `Cargo.toml` | `cargo fetch` | `cargo run` | `cargo test` | `cargo build` |
| `pom.xml` | `./mvnw install -DskipTests` | `./mvnw spring-boot:run` | `./mvnw test` | `./mvnw package` |
| `build.gradle` / `build.gradle.kts` | `./gradlew build -x test` | `./gradlew bootRun` / `./gradlew run` | `./gradlew test` | `./gradlew build` |
| `Gemfile` | `bundle install` | `bundle exec rails server` | `bundle exec rspec` | — |
| `Makefile` | `make setup` (if present) | `make run` / `make dev` | `make test` | `make build` |
| `docker-compose.yml` present | — | — | — | teardown: `docker compose down` |

Fill in `<app>` from the project (entry point, package name, framework). Drop
any row whose command doesn't exist in the project rather than inventing one.

## Verifying (inside a Casper workspace)

To confirm Casper parses the file and sees your commands **without executing
anything**, ask for a name that doesn't exist and read the listing:

```bash
casper run __check__
```

- Valid file with commands → `{"error":"no command '__check__' (available commands: build, run, test)"}`
- Valid file, no commands → `{"error":"no command '__check__' (no named commands defined in .casper.json)"}`
- Broken file → an `Invalid .casper.json` error naming the problem.

Do **not** "verify" by running a real command name: `casper run <name>` opens a
new terminal and actually executes the command. The bogus-name probe above is
the side-effect-free check.

Running a **reserved** name is refused, which also confirms the file parsed:

```bash
casper run setup   # {"error":"'setup' is a reserved lifecycle hook, not a runnable command"}
```

## Gotchas

- **An invalid `.casper.json` aborts workspace creation.** If the file exists
  but can't be read or decoded, `casper workspace new` fails with
  `Invalid .casper.json: <reason>` and creates nothing. Keep the JSON valid;
  the bogus-name probe above catches breakage before it bites someone.
- **`setup`/`teardown` are hooks, not commands** — they can't be launched with
  `casper run`. If the user wants a runnable "setup", give it a different name
  (e.g. `reset`).
- **An empty command string is ignored** — it's the same as not defining the
  key, and it won't show up as a command or run as a hook.
- **New worktrees only see committed config.** If `setup` or `copyFiles`
  seem not to fire for a freshly created workspace, check that `.casper.json` is
  committed on the base branch.

## Guard rule (soft)

Writing `.casper.json` only needs a Git repo — it does **not** require running
inside a Casper terminal. So there's no blocking workspace check up front.

Only the **verification** step uses the `casper` CLI, which needs a Casper
terminal. Gate just that step with the same plain test the plugin's hooks use,
and skip verification gracefully (don't fail the task) when it's absent:

```bash
[ -n "$CASPER_WORKSPACE_ID" ]
```
