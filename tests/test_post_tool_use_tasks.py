#!/usr/bin/env python3
import json, os, subprocess, sys, tempfile, unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "hooks", "post-tool-use-tasks.py")


def make_stub_casper(stub_dir):
    stub_path = os.path.join(stub_dir, "casper")
    with open(stub_path, "w") as f:
        f.write(
            "#!/usr/bin/env bash\n"
            "# Mirror the real casper CLI: 'progress set' rejects an out-of-range\n"
            "# --current, so a regression fails loudly instead of being logged.\n"
            'if [[ "$1" == "progress" && "$2" == "set" ]]; then\n'
            "    total=0\n"
            "    current=0\n"
            '    args=("$@")\n'
            "    for ((i = 0; i < ${#args[@]}; i++)); do\n"
            '        case "${args[i]}" in\n'
            '            --total) total="${args[i + 1]}" ;;\n'
            '            --current) current="${args[i + 1]}" ;;\n'
            "        esac\n"
            "    done\n"
            "    if ((current < 1 || current > total)); then\n"
            "        printf 'error: invalid progress %s/%s (need 1 <= current <= total)\\n' "
            '"$current" "$total" >&2\n'
            "        exit 1\n"
            "    fi\n"
            "fi\n"
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

    def test_create_without_in_progress_task_is_noop(self):
        self.run_hook(
            "TaskCreate",
            {"subject": "Write tests", "description": "d", "activeForm": "Writing tests"},
            "Task #1 created successfully: Write tests",
        )
        self.assertEqual(self.log_tail(), "")

    def test_in_progress_uses_active_form_label(self):
        self.run_hook(
            "TaskCreate",
            {"subject": "Write tests", "description": "d", "activeForm": "Writing tests"},
            "Task #1 created successfully: Write tests",
        )
        self.clear_log()
        self.run_hook("TaskUpdate", {"taskId": "1", "status": "in_progress"}, "Updated task #1 to in_progress")
        expected = "progress\nset\n--total\n1\n--current\n1\n--label\nWriting tests\n---\n"
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
        self.assertEqual(self.log_tail(), "")

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
        self.assertEqual(self.log_tail(), "")

    def test_state_resets_after_batch_completes(self):
        self.run_hook(
            "TaskCreate",
            {"subject": "Old task", "description": "d", "activeForm": "Doing old task"},
            "Task #1 created successfully: Old task",
        )
        self.run_hook("TaskUpdate", {"taskId": "1", "status": "completed"}, "Updated task #1 to completed")

        # The persisted mirror must be empty once the batch completes, so a fresh
        # batch does not inherit the old completed entries.
        mirror_path = os.path.join(self.plugin_data, f"{self.session_id}.json")
        with open(mirror_path) as f:
            self.assertEqual(json.load(f), {})

        self.clear_log()
        self.run_hook(
            "TaskCreate",
            {"subject": "New task", "description": "d", "activeForm": "Doing new task"},
            "Task #2 created successfully: New task",
        )
        self.assertEqual(self.log_tail(), "")

    def test_update_for_untracked_id_creates_no_phantom(self):
        # A TaskUpdate for an id the hook never recorded (a failed/stale update
        # whose PostToolUse still fires) must not materialize a phantom entry.
        self.run_hook(
            "TaskCreate",
            {"subject": "Real task", "description": "d", "activeForm": "Doing real task"},
            "Task #6 created successfully: Real task",
        )
        self.run_hook("TaskUpdate", {"taskId": "1", "status": "in_progress"}, "Task not found")

        mirror_path = os.path.join(self.plugin_data, f"{self.session_id}.json")
        with open(mirror_path) as f:
            state = json.load(f)
        self.assertNotIn("1", state)
        self.assertEqual(set(state), {"6"})

    def test_stray_failed_update_does_not_wedge_batch_open(self):
        # Even after a stray failed update for a nonexistent id, completing the
        # real batch must still clear the bar and reset the persisted mirror.
        self.run_hook(
            "TaskCreate",
            {"subject": "Real task", "description": "d", "activeForm": "Doing real task"},
            "Task #6 created successfully: Real task",
        )
        self.run_hook("TaskUpdate", {"taskId": "1", "status": "in_progress"}, "Task not found")
        self.run_hook("TaskUpdate", {"taskId": "6", "status": "in_progress"}, "Updated task #6 to in_progress")
        self.clear_log()
        self.run_hook("TaskUpdate", {"taskId": "6", "status": "completed"}, "Updated task #6 to completed")

        self.assertEqual(self.log_tail(), "progress\nclear\n---\n")
        mirror_path = os.path.join(self.plugin_data, f"{self.session_id}.json")
        with open(mirror_path) as f:
            self.assertEqual(json.load(f), {})

    def test_unknown_tool_name_is_noop(self):
        self.run_hook("SomeOtherTool", {}, "irrelevant")
        self.assertEqual(self.log_tail(), "")


if __name__ == "__main__":
    unittest.main()
