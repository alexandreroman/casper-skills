"""A subagent's tool call is not the agent's own (hooks/pre-tool-use.sh).

Measured on Claude Code 2.1.300: PreToolUse fires for every tool call a
subagent makes, with `agent_id` and `agent_type` added to the payload, and a
background subagent keeps making them after the agent's turn has ended. Each
one used to report `working` and advance the agent's notify marker. So a
`blocked` the agent set while waiting on the user lasted until the subagent's
next tool call, a second later, and the turn then ended `done` over the
question it had just asked.
"""
import json, os, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from harness import CasperStub

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "hooks")
WORKING = ["status", "set", "working"]


def tool(command, **extra):
    return {"session_id": "s1", "hook_event_name": "PreToolUse",
            "tool_name": "Bash", "tool_input": {"command": command}, **extra}


def subagent_tool(command):
    return tool(command, agent_id="a3e5cff9a3fc00c48", agent_type="general-purpose")


class TestSubagentTools(unittest.TestCase):
    def setUp(self):
        self.data_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.data_dir, ignore_errors=True)

    def hook(self, script, payload):
        """Run one hook on its own stub; return its casper calls."""
        with CasperStub() as stub:
            proc = subprocess.run(
                [os.path.join(HOOKS, script)], input=json.dumps(payload),
                env=stub.env(CLAUDE_PLUGIN_DATA=self.data_dir, PLUGIN_ROOT=""),
                capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return stub.calls

    def test_a_subagent_tool_call_reports_nothing(self):
        self.assertEqual(self.hook("pre-tool-use.sh", subagent_tool("cat a.txt")), [])

    def test_the_agents_own_tool_call_still_reports_working(self):
        self.assertEqual(self.hook("pre-tool-use.sh", tool("cat a.txt")), [WORKING])

    def test_a_command_that_names_agent_id_is_still_the_agents(self):
        self.assertEqual(self.hook("pre-tool-use.sh", tool('grep -rn "agent_id": hooks')),
                         [WORKING])

    def test_a_tool_input_keyed_agent_id_is_still_the_agents(self):
        # An MCP tool may take an `agent_id` argument of its own: the key is
        # there unescaped, but not at the top of the payload.
        payload = {"session_id": "s1", "hook_event_name": "PreToolUse",
                   "tool_name": "mcp__fleet__stop", "tool_input": {"agent_id": "x"}}
        self.assertEqual(self.hook("pre-tool-use.sh", payload), [WORKING])

    def test_a_subagent_tool_call_does_not_spend_the_agents_notify(self):
        # The agent announced its question and asked it; the background
        # subagent's tool calls are not the agent moving on, so the dialog's
        # Notification stays covered by the agent's own message.
        self.hook("pre-tool-use.sh", tool('casper notify --message "Need your decision"'))
        self.hook("pre-tool-use.sh", {"session_id": "s1", "hook_event_name": "PreToolUse",
                                      "tool_name": "AskUserQuestion",
                                      "tool_input": {"questions": []}})
        self.hook("pre-tool-use.sh", subagent_tool("make test"))
        self.hook("pre-tool-use.sh", subagent_tool("make lint"))
        calls = self.hook("blocked.py", {"session_id": "s1",
                                         "hook_event_name": "Notification",
                                         "notification_type": "permission_prompt",
                                         "message": "Claude needs your permission"})
        self.assertEqual([c for c in calls if c[:1] == ["notify"]], [])

    def test_a_subagent_tool_call_still_ends_a_dialogs_blocked(self):
        # A dialog's `blocked` may be the subagent's own permission prompt,
        # denied: its next tool call is the only sign the wait is over.
        self.hook("blocked.py", {"session_id": "s1", "hook_event_name": "PermissionRequest",
                                 "tool_name": "Bash", "agent_id": "a3e5cff9a3fc00c48"})
        self.assertEqual(self.hook("pre-tool-use.sh", subagent_tool("ls")), [WORKING])
        self.assertEqual(self.hook("pre-tool-use.sh", subagent_tool("ls")), [])


if __name__ == "__main__":
    unittest.main()
