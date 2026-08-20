import os, subprocess, sys, textwrap, unittest
from harness import CasperStub

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_snippet(stub, code, **env):
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=ROOT, env=stub.env(**env), capture_output=True, text=True,
    )

class TestEmit(unittest.TestCase):
    def test_turn_start_sets_working(self):
        with CasperStub() as stub:
            run_snippet(stub, """
                from hooks.lib import casper
                casper.emit("turn-start")
            """)
            self.assertEqual(stub.calls, [["status", "set", "working"]])

    def test_turn_end_sets_done(self):
        with CasperStub() as stub:
            run_snippet(stub, """
                from hooks.lib import casper
                casper.emit("turn-end")
            """)
            self.assertEqual(stub.calls, [["status", "set", "done"]])

    def test_unknown_event_is_silent(self):
        with CasperStub() as stub:
            run_snippet(stub, """
                from hooks.lib import casper
                casper.emit("not-an-event")
            """)
            self.assertEqual(stub.calls, [])

    def test_missing_workspace_id_suppresses_calls(self):
        with CasperStub() as stub:
            env = stub.env()
            env.pop("CASPER_WORKSPACE_ID", None)
            subprocess.run(
                [sys.executable, "-c",
                 "from hooks.lib import casper; casper.emit('turn-start')"],
                cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(stub.calls, [])

    def test_missing_binary_does_not_raise(self):
        with CasperStub() as stub:
            env = stub.env(PATH="/nonexistent")
            proc = subprocess.run(
                [sys.executable, "-c",
                 "from hooks.lib import casper; casper.run(['status','set','done'])"],
                cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)

if __name__ == "__main__":
    unittest.main()
