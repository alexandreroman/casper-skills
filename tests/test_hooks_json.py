import json, os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = json.load(open(os.path.join(ROOT, "hooks", "hooks.json")))["hooks"]

def commands(event):
    return [h["command"] for group in HOOKS.get(event, []) for h in group["hooks"]]

class TestHooksJson(unittest.TestCase):
    def test_declares_every_expected_event(self):
        for event in ("SessionStart", "UserPromptSubmit", "PreToolUse",
                      "PostToolUse", "Stop", "SessionEnd", "Notification",
                      "PermissionRequest"):
            self.assertIn(event, HOOKS, f"{event} missing from hooks.json")

    def test_post_tool_use_matches_both_dialects(self):
        matchers = [g.get("matcher") for g in HOOKS["PostToolUse"]]
        self.assertIn("TaskCreate|TaskUpdate", matchers)
        self.assertIn("update_plan", matchers)

    def test_both_post_tool_use_groups_route_to_tasks(self):
        for cmd in commands("PostToolUse"):
            self.assertIn("hooks/tasks.py", cmd)

    def test_notification_and_permission_request_share_one_entry_point(self):
        for event in ("Notification", "PermissionRequest"):
            for cmd in commands(event):
                self.assertIn("hooks/blocked.py", cmd)

    def test_every_command_is_workspace_guarded(self):
        for event in HOOKS:
            for cmd in commands(event):
                self.assertIn('[ -n "$CASPER_WORKSPACE_ID" ]', cmd,
                              f"{event} command is not guarded")
                self.assertTrue(cmd.rstrip().endswith("|| true"),
                                f"{event} command can fail a turn")

    def test_every_command_uses_the_portable_plugin_root(self):
        # Codex exports CLAUDE_PLUGIN_ROOT for compatibility, so one variable
        # serves both agents.
        for event in HOOKS:
            for cmd in commands(event):
                self.assertIn("${CLAUDE_PLUGIN_ROOT}", cmd)

    def test_every_hook_declares_a_timeout(self):
        for event in HOOKS:
            for group in HOOKS[event]:
                for hook in group["hooks"]:
                    self.assertEqual(hook.get("timeout"), 3,
                                     f"{event} timeout is not 3 seconds")

    def test_no_reference_to_deleted_scripts(self):
        blob = json.dumps(HOOKS)
        for gone in ("session-start.sh", "notification.py", "post-tool-use-tasks.py"):
            self.assertNotIn(gone, blob)

if __name__ == "__main__":
    unittest.main()
