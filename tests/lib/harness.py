import json, os, shutil, tempfile

STUB = """#!/usr/bin/env bash
printf '%s\\t' "$@" >> "$CASPER_LOG"
printf '\\n' >> "$CASPER_LOG"
# Canned answers for the read verbs, so a hook that asks `casper` a question
# can be driven from a test: CASPER_STUB_OUT_<verb>_<subcommand>. Unset means
# the verb answers nothing, which is what an older CLI or a stopped app looks
# like. The name is only built for plain lowercase verbs, so no argument can
# ever compose an env-var name.
if [[ "${1:-}" =~ ^[a-z]+$ && "${2:-}" =~ ^[a-z]+$ ]]; then
  reply="CASPER_STUB_OUT_$1_$2"
  [ -n "${!reply:-}" ] && printf '%s\\n' "${!reply}"
fi
exit 0
"""

class CasperStub:
    """Puts a recording `casper` stub on PATH. Use as a context manager."""

    def __enter__(self):
        self._dir = tempfile.mkdtemp()
        self.log = os.path.join(self._dir, "calls.log")
        stub = os.path.join(self._dir, "casper")
        with open(stub, "w") as f:
            f.write(STUB)
        os.chmod(stub, 0o755)
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self._dir, ignore_errors=True)
        return False

    def env(self, **overrides):
        env = dict(os.environ)
        env["PATH"] = self._dir + os.pathsep + env.get("PATH", "")
        env["CASPER_LOG"] = self.log
        env.setdefault("CASPER_WORKSPACE_ID", "test-ws")
        env.update(overrides)
        return env

    @staticmethod
    def replies(status=None, bar=None):
        """Env vars carrying the canned answers the read verbs give back.

        `status` is what `casper status get` reports. `bar` is whether `casper
        progress get` reports one: True for a bar mid-way, False for none.
        Either left None leaves that verb unanswered, which is how a `casper`
        too old to know it — or a stopped app — reads to a hook.
        """
        env = {}
        if status is not None:
            env["CASPER_STUB_OUT_status_get"] = json.dumps(
                {"status": status, "workspace": "test-ws"})
        if bar is not None:
            body = {"total": 3, "current": 2, "label": "step"} if bar else None
            env["CASPER_STUB_OUT_progress_get"] = json.dumps(
                {"progress": body, "workspace": "test-ws"})
        return env

    @property
    def calls(self):
        try:
            with open(self.log) as f:
                return [
                    (line[:-1] if line.endswith("\t") else line).split("\t")
                    for line in f.read().splitlines()
                    if line
                ]
        except FileNotFoundError:
            return []
