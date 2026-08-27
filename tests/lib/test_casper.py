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

    def test_turn_end_is_not_in_the_table(self):
        # It left EVENT_ACTIONS when it stopped being a constant: what a turn
        # ending emits now depends on what the workspace is showing, and
        # `progress.turn_end_actions` decides it.
        with CasperStub() as stub:
            run_snippet(stub, """
                from hooks.lib import casper
                casper.emit("turn-end")
            """)
            self.assertEqual(stub.calls, [])

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

class TestReads(unittest.TestCase):
    """The read side of the boundary: a `casper` that answers, and every way
    it can fail to. A failed read must never be louder than no answer."""

    def snippet(self, expr):
        return f"""
            from hooks.lib import casper
            print(repr(casper.{expr}))
        """

    def test_agent_state_reads_the_answer(self):
        with CasperStub() as stub:
            proc = run_snippet(stub, self.snippet("agent_state()"),
                               **CasperStub.replies(status="blocked"))
            self.assertEqual(proc.stdout.strip(), "'blocked'")
            self.assertEqual(stub.calls, [["status", "get"]])

    def test_bar_is_up_reads_the_answer(self):
        with CasperStub() as stub:
            proc = run_snippet(stub, self.snippet("bar_is_up()"),
                               **CasperStub.replies(bar=True))
            self.assertEqual(proc.stdout.strip(), "True")
            self.assertEqual(stub.calls, [["progress", "get"]])

    def test_no_bar_reads_false(self):
        with CasperStub() as stub:
            proc = run_snippet(stub, self.snippet("bar_is_up()"),
                               **CasperStub.replies(bar=False))
            self.assertEqual(proc.stdout.strip(), "False")

    def test_an_unanswered_read_is_none(self):
        # A `casper` too old for the verb exits non-zero; a stopped app prints
        # nothing. Both have to read as "no answer", not as an error.
        with CasperStub() as stub:
            proc = run_snippet(stub, self.snippet("agent_state()"))
            self.assertEqual(proc.stdout.strip(), "None")
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_unparseable_output_is_none(self):
        with CasperStub() as stub:
            proc = run_snippet(stub, self.snippet("bar_is_up()"),
                               CASPER_STUB_OUT_progress_get="not json")
            self.assertEqual(proc.stdout.strip(), "False")
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_missing_binary_reads_as_no_answer(self):
        with CasperStub() as stub:
            proc = run_snippet(stub, self.snippet("agent_state()"), PATH="/nonexistent")
            self.assertEqual(proc.stdout.strip(), "None")
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_outside_a_workspace_nothing_is_read(self):
        with CasperStub() as stub:
            env = stub.env(**CasperStub.replies(status="blocked"))
            env.pop("CASPER_WORKSPACE_ID", None)
            proc = subprocess.run(
                [sys.executable, "-c",
                 "from hooks.lib import casper; print(repr(casper.agent_state()))"],
                cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(proc.stdout.strip(), "None")
            self.assertEqual(stub.calls, [])

if __name__ == "__main__":
    unittest.main()
