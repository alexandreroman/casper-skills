"""Stop hook: reports done, and reconciles the progress bar.

The bar and the sidebar status are independent surfaces. Before this hook
touched progress, nothing but a session restart brought them back into
agreement, so a bar set during a turn kept advertising an in-flight step for
every later turn — including one set by hand through the CLI by an agent whose
harness exposes no task tool, which the task hook never sees at all.
"""
import json, os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from harness import CasperStub

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from hooks.lib.casper import EVENT_ACTIONS

HOOK = os.path.join(ROOT, "hooks", "stop.py")
DONE = EVENT_ACTIONS["turn-end"][0]
CLEAR = ["progress", "clear"]


class TestStop(unittest.TestCase):
    def setUp(self):
        self.data_dir = tempfile.mkdtemp()

    def fire(self, stub, session_id="s1", data_dir=None):
        return subprocess.run(
            [HOOK], input=json.dumps({"session_id": session_id}),
            env=stub.env(CLAUDE_PLUGIN_DATA=data_dir or self.data_dir),
            capture_output=True, text=True, cwd=ROOT)

    def mirror(self, session_id, state):
        with open(os.path.join(self.data_dir, f"{session_id}.json"), "w") as f:
            json.dump(state, f)

    def test_reports_done_from_the_shared_table(self):
        with CasperStub() as stub:
            self.fire(stub)
            self.assertEqual(stub.calls[0], DONE)

    def test_no_task_state_at_all_clears_a_bar_nothing_else_would(self):
        # The reported bug: an agent with no task tool drove `casper progress
        # set` by hand, so there is no mirror and the task hook never ran.
        with CasperStub() as stub:
            self.fire(stub)
            self.assertEqual(stub.calls, [DONE, CLEAR])

    def test_finished_task_list_clears(self):
        self.mirror("s1", {"1": {"label": "a", "status": "completed"}})
        with CasperStub() as stub:
            self.fire(stub)
            self.assertEqual(stub.calls, [DONE, CLEAR])

    def test_task_still_in_flight_keeps_its_bar(self):
        # A turn that ends waiting on the user should still show where the
        # work stopped, so this is the one case the bar survives.
        self.mirror("s1", {"1": {"label": "a", "status": "completed"},
                           "2": {"label": "b", "status": "in_progress"}})
        with CasperStub() as stub:
            self.fire(stub)
            self.assertEqual(stub.calls, [DONE])

    def test_unlabelled_in_flight_task_keeps_its_bar(self):
        # actions_for deliberately leaves the bar alone rather than invent a
        # label; that is still live work, so reconciliation agrees.
        self.mirror("s1", {"1": {"label": "", "status": "in_progress"}})
        with CasperStub() as stub:
            self.fire(stub)
            self.assertEqual(stub.calls, [DONE])

    def test_another_sessions_mirror_is_not_consulted(self):
        self.mirror("other", {"1": {"label": "a", "status": "in_progress"}})
        with CasperStub() as stub:
            self.fire(stub, session_id="s1")
            self.assertEqual(stub.calls, [DONE, CLEAR])

    def test_corrupt_mirror_still_reports_done(self):
        with open(os.path.join(self.data_dir, "s1.json"), "w") as f:
            f.write("{not json")
        with CasperStub() as stub:
            self.fire(stub)
            self.assertEqual(stub.calls, [DONE, CLEAR])

    def test_missing_stdin_payload_is_survivable(self):
        with CasperStub() as stub:
            proc = subprocess.run(
                [HOOK], input="", env=stub.env(CLAUDE_PLUGIN_DATA=self.data_dir),
                capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(stub.calls[0], DONE)

    def test_unusable_state_dir_never_costs_the_status_call(self):
        blocker = os.path.join(self.data_dir, "not-a-dir")
        with open(blocker, "w") as f:
            f.write("")
        with CasperStub() as stub:
            proc = self.fire(stub, data_dir=blocker)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(stub.calls, [DONE])

    def test_outside_a_casper_workspace_nothing_is_emitted(self):
        with CasperStub() as stub:
            env = stub.env(CLAUDE_PLUGIN_DATA=self.data_dir)
            env.pop("CASPER_WORKSPACE_ID", None)
            subprocess.run([HOOK], input="{}", env=env,
                           capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(stub.calls, [])


if __name__ == "__main__":
    unittest.main()
