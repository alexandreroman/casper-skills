import json, os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from harness import CasperStub

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "tasks.py")

class Base(unittest.TestCase):
    def setUp(self):
        self.data_dir = tempfile.mkdtemp()

    def fire(self, stub, payload):
        return subprocess.run(
            [HOOK], input=json.dumps(payload),
            env=stub.env(CLAUDE_PLUGIN_DATA=self.data_dir),
            capture_output=True, text=True, cwd=ROOT)

class TestClaudeTaskTools(Base):
    def test_create_then_start_reports_progress(self):
        with CasperStub() as stub:
            self.fire(stub, {"session_id": "s1", "tool_name": "TaskCreate",
                             "tool_input": {"subject": "Build", "activeForm": "Building"},
                             "tool_response": {"task": {"id": "1"}}})
            self.fire(stub, {"session_id": "s1", "tool_name": "TaskCreate",
                             "tool_input": {"subject": "Test", "activeForm": "Testing"},
                             "tool_response": {"task": {"id": "2"}}})
            self.fire(stub, {"session_id": "s1", "tool_name": "TaskUpdate",
                             "tool_input": {"taskId": "1", "status": "in_progress"},
                             "tool_response": {}})
            self.assertEqual(stub.calls[-1], [
                "progress", "set", "--total", "2", "--current", "1", "--label", "Building"])

    def test_all_completed_clears(self):
        with CasperStub() as stub:
            self.fire(stub, {"session_id": "s2", "tool_name": "TaskCreate",
                             "tool_input": {"subject": "Only", "activeForm": "Doing"},
                             "tool_response": {"task": {"id": "1"}}})
            self.fire(stub, {"session_id": "s2", "tool_name": "TaskUpdate",
                             "tool_input": {"taskId": "1", "status": "completed"},
                             "tool_response": {}})
            self.assertEqual(stub.calls[-1], ["progress", "clear"])

    def test_unknown_task_id_is_ignored(self):
        with CasperStub() as stub:
            self.fire(stub, {"session_id": "s3", "tool_name": "TaskUpdate",
                             "tool_input": {"taskId": "999", "status": "in_progress"},
                             "tool_response": {}})
            self.assertEqual(stub.calls, [])

    def test_deleted_task_drops_out_of_the_total(self):
        with CasperStub() as stub:
            for i in ("1", "2"):
                self.fire(stub, {"session_id": "s4", "tool_name": "TaskCreate",
                                 "tool_input": {"subject": f"T{i}", "activeForm": f"Doing{i}"},
                                 "tool_response": {"task": {"id": i}}})
            self.fire(stub, {"session_id": "s4", "tool_name": "TaskUpdate",
                             "tool_input": {"taskId": "2", "status": "deleted"},
                             "tool_response": {}})
            self.fire(stub, {"session_id": "s4", "tool_name": "TaskUpdate",
                             "tool_input": {"taskId": "1", "status": "in_progress"},
                             "tool_response": {}})
            self.assertEqual(stub.calls[-1][3], "1")

class TestCodexUpdatePlan(Base):
    def test_plan_reports_progress_without_a_mirror(self):
        with CasperStub() as stub:
            self.fire(stub, {"session_id": "c1", "tool_name": "update_plan",
                             "tool_input": {"plan": [
                                 {"step": "Read", "status": "completed"},
                                 {"step": "Write", "status": "in_progress"},
                                 {"step": "Verify", "status": "pending"}]},
                             "tool_response": {}})
            self.assertEqual(stub.calls[-1], [
                "progress", "set", "--total", "3", "--current", "2", "--label", "Write"])

    def test_completed_plan_clears(self):
        with CasperStub() as stub:
            self.fire(stub, {"session_id": "c2", "tool_name": "update_plan",
                             "tool_input": {"plan": [{"step": "Done", "status": "completed"}]},
                             "tool_response": {}})
            self.assertEqual(stub.calls[-1], ["progress", "clear"])

class TestRobustness(Base):
    def test_other_tool_is_ignored(self):
        with CasperStub() as stub:
            self.fire(stub, {"session_id": "x", "tool_name": "Bash",
                             "tool_input": {}, "tool_response": {}})
            self.assertEqual(stub.calls, [])

    def test_malformed_stdin_exits_clean(self):
        with CasperStub() as stub:
            proc = subprocess.run([HOOK], input="}{", env=stub.env(),
                                  capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(stub.calls, [])

    def test_unusable_state_dir_does_not_fail_the_turn(self):
        import tempfile
        # CLAUDE_PLUGIN_DATA pointing at a regular FILE makes makedirs raise.
        with tempfile.NamedTemporaryFile(suffix=".notadir", delete=False) as f:
            bogus = f.name
        with CasperStub() as stub:
            proc = subprocess.run(
                [HOOK], input=json.dumps({
                    "session_id": "s", "tool_name": "TaskCreate",
                    "tool_input": {"subject": "X", "activeForm": "Doing X"},
                    "tool_response": {"task": {"id": "1"}}}),
                env=stub.env(CLAUDE_PLUGIN_DATA=bogus),
                capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(stub.calls, [])

if __name__ == "__main__":
    unittest.main()
