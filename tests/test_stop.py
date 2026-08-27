"""Stop hook: reports where the work stands, and reconciles the progress bar.

The bar and the sidebar status are independent surfaces. Before this hook
touched progress, nothing but a session restart brought them back into
agreement, so a bar set during a turn kept advertising a step of a task list
that had finished for every later turn.

Then the two disagreed the other way. A bar with no mirror behind it was driven
by hand, by an agent whose harness exposes no task tool, and survives the turn
on purpose: the work it describes routinely outlives a turn boundary. But the
turn still reported `done` beside it — the sidebar called finished what the bar
right next to it called step 3 of 7, and the user got a completion notification
for work that was still running. So the hook now reads the workspace back
before it writes: the bar decides between `working` and `done`, and a `blocked`
or `error` the agent reported for itself is never written over.
"""
import json, os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from harness import CasperStub

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

HOOK = os.path.join(ROOT, "hooks", "stop.py")
# Both reads always run, in this order, whatever the answers are: the argv a
# turn ending emits must not depend on what it is about to find.
READS = [["status", "get"], ["progress", "get"]]
DONE = ["status", "set", "done"]
WORKING = ["status", "set", "working"]
CLEAR = ["progress", "clear"]


class TestStop(unittest.TestCase):
    def setUp(self):
        self.data_dir = tempfile.mkdtemp()

    def fire(self, stub, session_id="s1", data_dir=None, status="working", bar=False):
        return subprocess.run(
            [HOOK], input=json.dumps({"session_id": session_id}),
            env=stub.env(CLAUDE_PLUGIN_DATA=data_dir or self.data_dir,
                         **CasperStub.replies(status=status, bar=bar)),
            capture_output=True, text=True, cwd=ROOT)

    def mirror(self, session_id, state):
        with open(os.path.join(self.data_dir, f"{session_id}.json"), "w") as f:
            json.dump(state, f)

    def test_a_turn_with_nothing_left_on_screen_reports_done(self):
        with CasperStub() as stub:
            self.fire(stub)
            self.assertEqual(stub.calls, READS + [DONE])

    def test_a_hand_driven_bar_holds_the_turn_at_working(self):
        # The reported bug: an agent with no task tool drove `casper progress
        # set` by hand, so there is no mirror and the task hook never ran. The
        # bar survives the turn (that was the earlier fix); reporting `done`
        # beside it said the work was over while it ran on in a background
        # subagent, and notified the user of a completion that had not
        # happened.
        with CasperStub() as stub:
            self.fire(stub, bar=True)
            self.assertEqual(stub.calls, READS + [WORKING])

    def test_a_hand_driven_bar_is_not_cleared_at_turn_end(self):
        with CasperStub() as stub:
            self.fire(stub, bar=True)
            self.assertNotIn(CLEAR, stub.calls)

    def test_finished_task_list_clears_and_reports_done(self):
        # The bar is up at the moment of the read, and this hook is about to
        # clear it: what is left when it is done is what `done` is judged on.
        self.mirror("s1", {"1": {"label": "a", "status": "completed"}})
        with CasperStub() as stub:
            self.fire(stub, bar=True)
            self.assertEqual(stub.calls, READS + [DONE, CLEAR])

    def test_task_still_in_flight_keeps_its_bar_and_reports_working(self):
        self.mirror("s1", {"1": {"label": "a", "status": "completed"},
                           "2": {"label": "b", "status": "in_progress"}})
        with CasperStub() as stub:
            self.fire(stub, bar=True)
            self.assertEqual(stub.calls, READS + [WORKING])

    def test_unlabelled_in_flight_task_keeps_its_bar(self):
        # actions_for deliberately leaves the bar alone rather than invent a
        # label; that is still live work, so reconciliation agrees.
        self.mirror("s1", {"1": {"label": "", "status": "in_progress"}})
        with CasperStub() as stub:
            self.fire(stub, bar=True)
            self.assertEqual(stub.calls, READS + [WORKING])

    def test_a_blocked_agent_is_not_reported_over(self):
        # The guidance tells an agent to report `blocked` when it ends a turn
        # waiting on the user. This hook fires straight after and used to
        # overwrite that verdict with one inferred from the turn boundary
        # alone — the one state no hook can reach on its own.
        with CasperStub() as stub:
            self.fire(stub, status="blocked", bar=True)
            self.assertEqual(stub.calls, READS)

    def test_an_error_state_is_not_reported_over_but_the_bar_is_reconciled(self):
        self.mirror("s1", {"1": {"label": "a", "status": "completed"}})
        with CasperStub() as stub:
            self.fire(stub, status="error", bar=True)
            self.assertEqual(stub.calls, READS + [CLEAR])

    def test_an_unreadable_workspace_still_reports_done(self):
        # A `casper` too old for the read verbs, or a stopped app: both reads
        # come back empty and the turn ends exactly as it did before they
        # existed.
        with CasperStub() as stub:
            self.fire(stub, status=None, bar=None)
            self.assertEqual(stub.calls, READS + [DONE])

    def test_a_finished_mirror_is_removed_with_its_lock(self):
        # Left behind, the pair outlives every session that tracked a task.
        self.mirror("s1", {"1": {"label": "a", "status": "completed"}})
        open(os.path.join(self.data_dir, "s1.json.lock"), "w").close()
        with CasperStub() as stub:
            self.fire(stub)
            self.assertEqual(sorted(os.listdir(self.data_dir)), [])

    def test_an_in_flight_mirror_survives_the_turn(self):
        self.mirror("s1", {"1": {"label": "a", "status": "in_progress"}})
        with CasperStub() as stub:
            self.fire(stub)
            self.assertIn("s1.json", os.listdir(self.data_dir))

    def test_another_sessions_mirror_is_not_consulted(self):
        # Another session's in-flight task must not keep this session's bar,
        # and must not clear it either: with no mirror of its own this session
        # is the hand-driven case, whose bar is left alone.
        self.mirror("other", {"1": {"label": "a", "status": "in_progress"}})
        with CasperStub() as stub:
            self.fire(stub, session_id="s1", bar=True)
            self.assertEqual(stub.calls, READS + [WORKING])
            self.assertIn("other.json", os.listdir(self.data_dir))

    def test_corrupt_mirror_reads_as_the_hand_driven_case(self):
        with open(os.path.join(self.data_dir, "s1.json"), "w") as f:
            f.write("{not json")
        with CasperStub() as stub:
            self.fire(stub, bar=True)
            self.assertEqual(stub.calls, READS + [WORKING])

    def test_missing_stdin_payload_is_survivable(self):
        with CasperStub() as stub:
            proc = subprocess.run(
                [HOOK], input="", env=stub.env(CLAUDE_PLUGIN_DATA=self.data_dir),
                capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(stub.calls, READS + [DONE])

    def test_unusable_state_dir_never_costs_the_status_call(self):
        blocker = os.path.join(self.data_dir, "not-a-dir")
        with open(blocker, "w") as f:
            f.write("")
        with CasperStub() as stub:
            proc = self.fire(stub, data_dir=blocker)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(stub.calls, READS + [DONE])

    def test_outside_a_casper_workspace_nothing_is_emitted(self):
        with CasperStub() as stub:
            env = stub.env(CLAUDE_PLUGIN_DATA=self.data_dir)
            env.pop("CASPER_WORKSPACE_ID", None)
            subprocess.run([HOOK], input="{}", env=env,
                           capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(stub.calls, [])


if __name__ == "__main__":
    unittest.main()
