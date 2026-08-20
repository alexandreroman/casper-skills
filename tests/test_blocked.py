import json, os, subprocess, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from harness import CasperStub

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "blocked.py")

def fire(stub, payload):
    return subprocess.run([HOOK], input=json.dumps(payload), env=stub.env(),
                          capture_output=True, text=True, cwd=ROOT)

class TestClaudeNotification(unittest.TestCase):
    def test_permission_prompt_blocks_and_notifies(self):
        with CasperStub() as stub:
            fire(stub, {"hook_event_name": "Notification",
                        "notification_type": "permission_prompt",
                        "message": "Allow Bash?"})
            self.assertEqual(stub.calls[0], ["status", "set", "blocked"])
            self.assertEqual(stub.calls[1][:2], ["notify", "--message"])

    def test_elicitation_dialog_blocks(self):
        with CasperStub() as stub:
            fire(stub, {"hook_event_name": "Notification",
                        "notification_type": "elicitation_dialog"})
            self.assertEqual(stub.calls[0], ["status", "set", "blocked"])

    def test_idle_prompt_stays_silent(self):
        with CasperStub() as stub:
            fire(stub, {"hook_event_name": "Notification",
                        "notification_type": "idle_prompt"})
            self.assertEqual(stub.calls, [])

    def test_unknown_type_stays_silent(self):
        with CasperStub() as stub:
            fire(stub, {"hook_event_name": "Notification",
                        "notification_type": "something_future"})
            self.assertEqual(stub.calls, [])

    def test_agent_needs_input_stays_silent(self):
        # Documented policy decision: it plausibly also means "needs the
        # user", but is not confirmed to fire for a plain CLI session inside
        # a Casper terminal, so acting on it would be guesswork.
        with CasperStub() as stub:
            fire(stub, {"hook_event_name": "Notification",
                        "notification_type": "agent_needs_input"})
            self.assertEqual(stub.calls, [])

class TestOtherHookEvents(unittest.TestCase):
    def test_non_notification_non_permission_event_makes_no_call(self):
        with CasperStub() as stub:
            fire(stub, {"hook_event_name": "Stop"})
            self.assertEqual(stub.calls, [])

class TestCodexPermissionRequest(unittest.TestCase):
    def test_permission_request_needs_no_allowlist(self):
        with CasperStub() as stub:
            fire(stub, {"hook_event_name": "PermissionRequest",
                        "tool_name": "shell",
                        "tool_input": {"description": "run the test suite"}})
            self.assertEqual(stub.calls[0], ["status", "set", "blocked"])
            self.assertEqual(stub.calls[1][:2], ["notify", "--message"])

    def test_uses_the_tool_description_when_present(self):
        with CasperStub() as stub:
            fire(stub, {"hook_event_name": "PermissionRequest",
                        "tool_name": "shell",
                        "tool_input": {"description": "run the test suite"}})
            self.assertIn("run the test suite", stub.calls[1][2])

    def test_falls_back_to_the_tool_name(self):
        with CasperStub() as stub:
            fire(stub, {"hook_event_name": "PermissionRequest", "tool_name": "apply_patch"})
            self.assertIn("apply_patch", stub.calls[1][2])

class TestRobustness(unittest.TestCase):
    def test_malformed_stdin_exits_clean(self):
        with CasperStub() as stub:
            proc = subprocess.run([HOOK], input="", env=stub.env(),
                                  capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(stub.calls, [])

if __name__ == "__main__":
    unittest.main()
