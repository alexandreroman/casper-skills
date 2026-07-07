#!/usr/bin/env python3
import json, os, subprocess, sys, tempfile, unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "hooks", "post-tool-use-tasks.py")


def make_stub_casper(stub_dir):
    stub_path = os.path.join(stub_dir, "casper")
    with open(stub_path, "w") as f:
        f.write(
            "#!/usr/bin/env bash\n"
            "printf '%s\\n' \"$@\" >> \"$CASPER_LOG\"\n"
            "printf -- '---\\n' >> \"$CASPER_LOG\"\n"
        )
    os.chmod(stub_path, 0o755)


class TestPostToolUseTasks(unittest.TestCase):
    def setUp(self):
        self.stub_dir = tempfile.mkdtemp()
        self.plugin_data = tempfile.mkdtemp()
        self.log_path = os.path.join(self.stub_dir, "log")
        make_stub_casper(self.stub_dir)
        self.env = dict(os.environ)
        self.env["PATH"] = self.stub_dir + ":" + self.env["PATH"]
        self.env["CASPER_LOG"] = self.log_path
        self.env["CLAUDE_PLUGIN_DATA"] = self.plugin_data
        self.session_id = "test-session"

    def clear_log(self):
        open(self.log_path, "w").close()

    def run_hook(self, tool_name, tool_input, tool_response):
        payload = json.dumps({
            "session_id": self.session_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_response": tool_response,
        })
        subprocess.run(
            [sys.executable, SCRIPT], input=payload, text=True,
            env=self.env, timeout=5,
        )

    def log_tail(self):
        if not os.path.exists(self.log_path):
            return ""
        with open(self.log_path) as f:
            return f.read()

    def test_create_sets_progress_with_working_label(self):
        self.run_hook(
            "TaskCreate",
            {"subject": "Write tests", "description": "d", "activeForm": "Writing tests"},
            "Task #1 created successfully: Write tests",
        )
        expected = "progress\nset\n--total\n1\n--current\n0\n--label\nworking\n---\n"
        self.assertEqual(self.log_tail(), expected)

    def test_in_progress_uses_active_form_label(self):
        self.run_hook(
            "TaskCreate",
            {"subject": "Write tests", "description": "d", "activeForm": "Writing tests"},
            "Task #1 created successfully: Write tests",
        )
        self.clear_log()
        self.run_hook("TaskUpdate", {"taskId": "1", "status": "in_progress"}, "Updated task #1 to in_progress")
        expected = "progress\nset\n--total\n1\n--current\n0\n--label\nWriting tests\n---\n"
        self.assertEqual(self.log_tail(), expected)

    def test_all_completed_clears_progress(self):
        self.run_hook(
            "TaskCreate",
            {"subject": "Write tests", "description": "d", "activeForm": "Writing tests"},
            "Task #1 created successfully: Write tests",
        )
        self.clear_log()
        self.run_hook("TaskUpdate", {"taskId": "1", "status": "completed"}, "Updated task #1 to completed")
        expected = "progress\nclear\n---\n"
        self.assertEqual(self.log_tail(), expected)

    def test_deleted_task_excluded_from_total(self):
        self.run_hook(
            "TaskCreate",
            {"subject": "Write tests", "description": "d", "activeForm": "Writing tests"},
            "Task #1 created successfully: Write tests",
        )
        self.run_hook(
            "TaskCreate",
            {"subject": "Add docs", "description": "d", "activeForm": "Adding docs"},
            "Task #2 created successfully: Add docs",
        )
        self.clear_log()
        self.run_hook("TaskUpdate", {"taskId": "1", "status": "deleted"}, "Updated task #1 deleted")
        expected = "progress\nset\n--total\n1\n--current\n0\n--label\nworking\n---\n"
        self.assertEqual(self.log_tail(), expected)

    def test_sessions_do_not_share_state(self):
        self.run_hook(
            "TaskCreate",
            {"subject": "A", "description": "d", "activeForm": "Doing A"},
            "Task #1 created successfully: A",
        )
        self.run_hook(
            "TaskCreate",
            {"subject": "B", "description": "d", "activeForm": "Doing B"},
            "Task #2 created successfully: B",
        )
        self.session_id = "other-session"
        self.clear_log()
        self.run_hook(
            "TaskCreate",
            {"subject": "C", "description": "d", "activeForm": "Doing C"},
            "Task #1 created successfully: C",
        )
        expected = "progress\nset\n--total\n1\n--current\n0\n--label\nworking\n---\n"
        self.assertEqual(self.log_tail(), expected)

    def test_unknown_tool_name_is_noop(self):
        self.run_hook("SomeOtherTool", {}, "irrelevant")
        self.assertEqual(self.log_tail(), "")


if __name__ == "__main__":
    unittest.main()
