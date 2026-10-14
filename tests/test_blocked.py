"""blocked.py: one wait on the user reaches them as one notification.

Measured on Claude Code 2.1.289, an AskUserQuestion and a Bash permission
prompt look the same to the hooks: PreToolUse, PermissionRequest about 50 ms
later as the dialog opens, then Notification(permission_prompt) about 6 s
later, only if the dialog is still unanswered. The agent has usually run its
own `casper notify` just before. Each of the three used to notify.
"""
import json, os, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from harness import CasperStub

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "hooks")
HOOK = os.path.join(HOOKS, "blocked.py")
BLOCKED = ["status", "set", "blocked"]

# Payloads shaped like the ones Claude Code actually sent.
ASK = {"session_id": "s1", "hook_event_name": "PreToolUse",
       "tool_name": "AskUserQuestion", "tool_input": {"questions": []}}
ASK_PERMISSION = {"session_id": "s1", "hook_event_name": "PermissionRequest",
                  "tool_name": "AskUserQuestion", "tool_input": {"questions": []}}
PERMISSION_PROMPT = {"session_id": "s1", "hook_event_name": "Notification",
                     "notification_type": "permission_prompt",
                     "message": "Claude needs your permission"}


def bash(command, session_id="s1"):
    return {"session_id": session_id, "hook_event_name": "PreToolUse",
            "tool_name": "Bash", "tool_input": {"command": command}}


AGENT_NOTIFY = bash('casper notify --message "Need your decision on the cache"')


class HookTest(unittest.TestCase):
    """Runs hooks the way an agent would, against one session's state dir."""

    codex = False

    def setUp(self):
        self.data_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.data_dir, ignore_errors=True)

    def env(self, stub):
        # Pinned either way, so the agent the suite itself runs under (which
        # may export either variable) cannot decide which path is tested.
        return stub.env(CLAUDE_PLUGIN_DATA=self.data_dir,
                        PLUGIN_ROOT="/plugins/casper" if self.codex else "")

    def hook(self, stub, script, payload):
        return subprocess.run([os.path.join(HOOKS, script)], input=json.dumps(payload),
                              env=self.env(stub), capture_output=True, text=True,
                              cwd=ROOT)

    def blocked(self, payload):
        """Fire blocked.py on its own stub; return just its casper calls."""
        with CasperStub() as stub:
            proc = self.hook(stub, "blocked.py", payload)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return stub.calls

    def tools(self, *payloads):
        with CasperStub() as stub:
            for payload in payloads:
                proc = self.hook(stub, "pre-tool-use.sh", payload)
                self.assertEqual(proc.returncode, 0, proc.stderr)

    def notifies(self, calls):
        return [c for c in calls if c[:1] == ["notify"]]


class TestClaudeNotification(HookTest):
    def test_permission_prompt_blocks_and_notifies(self):
        calls = self.blocked(PERMISSION_PROMPT)
        self.assertEqual(calls, [BLOCKED,
                                 ["notify", "--message=Claude needs your permission"]])

    def test_a_message_starting_with_a_dash_is_passed_attached(self):
        # casper reads a separate value that starts with `-` as an option and
        # rejects the call (exit 64), so the notification silently vanished.
        calls = self.blocked({**PERMISSION_PROMPT, "message": "- waiting on you"})
        self.assertEqual(calls, [BLOCKED, ["notify", "--message=- waiting on you"]])

    def test_elicitation_dialog_blocks(self):
        calls = self.blocked({"hook_event_name": "Notification",
                              "notification_type": "elicitation_dialog"})
        self.assertEqual(calls[0], BLOCKED)

    def test_idle_prompt_stays_silent(self):
        self.assertEqual(self.blocked({"hook_event_name": "Notification",
                                       "notification_type": "idle_prompt"}), [])

    def test_unknown_type_stays_silent(self):
        self.assertEqual(self.blocked({"hook_event_name": "Notification",
                                       "notification_type": "something_future"}), [])

    def test_agent_needs_input_stays_silent(self):
        # Documented policy decision: it plausibly also means "needs the
        # user", but is not confirmed to fire for a plain CLI session inside
        # a Casper terminal, so acting on it would be guesswork.
        self.assertEqual(self.blocked({"hook_event_name": "Notification",
                                       "notification_type": "agent_needs_input"}), [])


class TestClaudePermissionRequest(HookTest):
    """Claude Code fires PermissionRequest too, ahead of the Notification."""

    def test_blocks_without_notifying(self):
        # The same dialog's Notification(permission_prompt) notifies if the
        # user leaves it unanswered; one answered in time notifies nobody.
        self.assertEqual(self.blocked(ASK_PERMISSION), [BLOCKED])

    def test_a_plain_permission_prompt_notifies_exactly_once(self):
        self.tools(bash("touch x.txt"))
        calls = self.blocked({**ASK_PERMISSION, "tool_name": "Bash"})
        calls += self.blocked(PERMISSION_PROMPT)
        self.assertEqual(calls, [BLOCKED, BLOCKED,
                                 ["notify", "--message=Claude needs your permission"]])


class TestCodexPermissionRequest(HookTest):
    codex = True

    def test_permission_request_needs_no_allowlist(self):
        calls = self.blocked({"hook_event_name": "PermissionRequest", "tool_name": "shell",
                              "tool_input": {"description": "run the test suite"}})
        self.assertEqual(calls[0], BLOCKED)
        self.assertEqual(calls[1][0], "notify")
        self.assertTrue(calls[1][1].startswith("--message="))

    def test_uses_the_tool_description_when_present(self):
        calls = self.blocked({"hook_event_name": "PermissionRequest", "tool_name": "shell",
                              "tool_input": {"description": "run the test suite"}})
        self.assertIn("run the test suite", calls[1][1])

    def test_falls_back_to_the_tool_name(self):
        calls = self.blocked({"hook_event_name": "PermissionRequest",
                              "tool_name": "apply_patch"})
        self.assertIn("apply_patch", calls[1][1])


class TestClaudeAgentAlreadyNotified(HookTest):
    """The agent's own `casper notify` is the one notification of its wait."""

    def test_the_reported_sequence_notifies_only_through_the_agent(self):
        # casper notify, casper status set blocked, AskUserQuestion, and the
        # two events its dialog fires: the report that started this.
        self.tools(AGENT_NOTIFY, bash("casper status set blocked"), ASK)
        calls = self.blocked(ASK_PERMISSION) + self.blocked(PERMISSION_PROMPT)
        self.assertEqual(calls, [BLOCKED, BLOCKED])

    def test_notify_and_status_in_one_command(self):
        self.tools(bash('[ -n "$CASPER_WORKSPACE_ID" ] && casper notify --message "x" '
                        '&& casper status set blocked'), ASK)
        self.assertEqual(self.notifies(self.blocked(PERMISSION_PROMPT)), [])

    def test_a_prompt_after_the_agent_moved_on_notifies(self):
        # The announced dialog was answered in time and the agent got back to
        # work: a later prompt is a wait the user has not been told about.
        self.tools(AGENT_NOTIFY, ASK, bash("make test"))
        self.assertEqual(len(self.notifies(self.blocked(PERMISSION_PROMPT))), 1)

    def test_another_sessions_notify_covers_nothing_here(self):
        self.tools(bash('casper notify --message "x"', session_id="other"), ASK)
        self.assertEqual(len(self.notifies(self.blocked(PERMISSION_PROMPT))), 1)

    def test_mentioning_casper_notify_is_not_notifying(self):
        self.tools(bash('grep -rn "casper notify" skills/'), ASK)
        self.assertEqual(len(self.notifies(self.blocked(PERMISSION_PROMPT))), 1)

    def test_the_next_prompt_ends_the_episode(self):
        with CasperStub() as stub:
            self.hook(stub, "pre-tool-use.sh", AGENT_NOTIFY)
            self.hook(stub, "user-prompt-submit.sh", {"session_id": "s1"})
        self.assertEqual(len(self.notifies(self.blocked(PERMISSION_PROMPT))), 1)

    def test_turn_end_ends_the_episode(self):
        with CasperStub() as stub:
            self.hook(stub, "pre-tool-use.sh", AGENT_NOTIFY)
            self.hook(stub, "stop.py", {"session_id": "s1"})
        self.assertEqual(len(self.notifies(self.blocked(PERMISSION_PROMPT))), 1)

    def test_session_end_removes_the_marker(self):
        with CasperStub() as stub:
            self.hook(stub, "pre-tool-use.sh", AGENT_NOTIFY)
            self.hook(stub, "session-end.sh", {"session_id": "s1"})
        self.assertEqual(os.listdir(self.data_dir), [])


class TestCodexAgentAlreadyNotified(HookTest):
    codex = True

    def test_permission_request_after_the_agents_notify_only_blocks(self):
        self.tools(AGENT_NOTIFY)
        self.assertEqual(self.blocked({"session_id": "s1",
                                       "hook_event_name": "PermissionRequest",
                                       "tool_name": "shell"}), [BLOCKED])

    def test_an_argv_command_counts(self):
        self.tools(bash(["bash", "-lc", 'casper notify --message "x"']))
        self.assertEqual(self.blocked({"session_id": "s1",
                                       "hook_event_name": "PermissionRequest",
                                       "tool_name": "shell"}), [BLOCKED])


class TestDialogBlocked(HookTest):
    """A dialog's `blocked` ends with the dialog (hooks/lib/dialog.py).

    Nothing fires when the user answers: an approved tool reports back only
    through its PostToolUse once it has run, a denial not at all.
    """

    def run_hook(self, script, payload):
        with CasperStub() as stub:
            proc = self.hook(stub, script, payload)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return stub.calls

    def test_the_approved_tool_finishing_reports_working(self):
        self.blocked({**ASK_PERMISSION, "tool_name": "Bash"})
        self.assertEqual(self.run_hook("post-tool-use.sh", bash("make deploy")),
                         [["status", "set", "working"]])
        # Once only: the next tool to finish has no dialog behind it.
        self.assertEqual(self.run_hook("post-tool-use.sh", bash("make test")), [])

    def test_an_answered_question_reports_working(self):
        self.blocked(ASK_PERMISSION)
        self.blocked(PERMISSION_PROMPT)
        self.assertEqual(self.run_hook("post-tool-use.sh", ASK),
                         [["status", "set", "working"]])

    def test_a_tool_with_no_dialog_finishing_does_nothing(self):
        # The agent's own `casper status set blocked` opens no dialog marker,
        # so the call that set it finishing must leave it standing.
        self.assertEqual(self.run_hook("post-tool-use.sh",
                                       bash("casper status set blocked")), [])

    def test_the_next_tool_call_closes_the_dialog(self):
        self.blocked(ASK_PERMISSION)
        self.tools(bash("ls"))
        self.assertEqual(self.run_hook("post-tool-use.sh", bash("ls")), [])

    def test_the_next_prompt_closes_the_dialog(self):
        self.blocked(ASK_PERMISSION)
        self.run_hook("user-prompt-submit.sh", {"session_id": "s1"})
        self.assertEqual(self.run_hook("post-tool-use.sh", bash("ls")), [])

    def test_another_sessions_dialog_is_not_this_one(self):
        self.blocked({**ASK_PERMISSION, "session_id": "other"})
        self.assertEqual(self.run_hook("post-tool-use.sh", bash("ls")), [])

    def test_session_end_removes_the_marker(self):
        self.blocked(ASK_PERMISSION)
        self.run_hook("session-end.sh", {"session_id": "s1"})
        self.assertEqual(os.listdir(self.data_dir), [])


class TestCodexDialogBlocked(TestDialogBlocked):
    codex = True

    def test_an_approved_casper_status_call_keeps_its_own_state(self):
        # Codex asks approval for the agent's own `casper status set blocked`
        # until `casper` is allowed for good. Once it has run, its `blocked`
        # is the agent's verdict, newer than the dialog's.
        call = bash("casper status set blocked")
        self.blocked({"session_id": "s1", "hook_event_name": "PermissionRequest",
                      "tool_name": "Bash", "tool_input": call["tool_input"]})
        self.assertEqual(self.run_hook("post-tool-use.sh", call), [])
        # The dialog is over all the same: nothing left to lift later.
        self.assertEqual(self.run_hook("post-tool-use.sh", bash("ls")), [])


class TestOtherHookEvents(HookTest):
    def test_non_notification_non_permission_event_makes_no_call(self):
        self.assertEqual(self.blocked({"hook_event_name": "Stop"}), [])


class TestRobustness(unittest.TestCase):
    def test_malformed_stdin_exits_clean(self):
        with CasperStub() as stub:
            proc = subprocess.run([HOOK], input="", env=stub.env(),
                                  capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(stub.calls, [])

    def test_an_unwritable_state_dir_still_notifies(self):
        with CasperStub() as stub:
            proc = subprocess.run([HOOK], input=json.dumps(PERMISSION_PROMPT),
                                  env=stub.env(CLAUDE_PLUGIN_DATA="/dev/null/nope",
                                               PLUGIN_ROOT=""),
                                  capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(stub.calls[1][1].startswith("--message="))

if __name__ == "__main__":
    unittest.main()
