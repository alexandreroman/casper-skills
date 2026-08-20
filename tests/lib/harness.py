import os, shutil, tempfile

STUB = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CASPER_LOG"
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

    @property
    def calls(self):
        try:
            with open(self.log) as f:
                return [line.split() for line in f.read().splitlines() if line]
        except FileNotFoundError:
            return []
