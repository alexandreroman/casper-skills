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

    def test_stop_routes_to_the_reconciling_entry_point(self):
        # Stop reads the session's task mirror off stdin's session_id, so it
        # cannot be the one-line Bash script it used to be.
        for cmd in commands("Stop"):
            self.assertIn("hooks/stop.py", cmd)

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
        # Claude Code exports CLAUDE_PLUGIN_ROOT; Codex's own name is
        # PLUGIN_ROOT and CLAUDE_PLUGIN_ROOT is only its compatibility mirror.
        # Both agents expand the command through a shell, so one `:-` fallback
        # covers them without a per-agent hooks file.
        for event in HOOKS:
            for cmd in commands(event):
                self.assertIn("${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}", cmd)

    def test_every_hook_declares_a_timeout(self):
        # 3 seconds is the budget for a hook that only writes. Stop is the one
        # exception: it reads the workspace back (state, then bar) before it
        # decides what to report, so it can spend four capped calls where the
        # others spend at most two.
        budgets = {"Stop": 6}
        for event in HOOKS:
            for group in HOOKS[event]:
                for hook in group["hooks"]:
                    expected = budgets.get(event, 3)
                    self.assertEqual(hook.get("timeout"), expected,
                                     f"{event} timeout is not {expected} seconds")

    def test_no_reference_to_deleted_scripts(self):
        blob = json.dumps(HOOKS)
        for gone in ("session-start.sh", "notification.py", "post-tool-use-tasks.py",
                     "stop.sh"):
            self.assertNotIn(gone, blob)

if __name__ == "__main__":
    unittest.main()
