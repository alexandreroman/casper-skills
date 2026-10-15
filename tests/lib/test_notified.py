import os, shutil, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from hooks.lib import notified

def cmd(command):
    return notified.casper_subcommands({"command": command})

class TestCasperSubcommands(unittest.TestCase):
    def test_a_plain_call(self):
        self.assertEqual(cmd('casper notify --message "x"'), ["notify"])

    def test_calls_after_separators(self):
        self.assertEqual(cmd('[ -n "$CASPER_WORKSPACE_ID" ] && casper notify -m x; '
                             'casper status set blocked || true'),
                         ["notify", "status"])

    def test_calls_inside_a_brace_group(self):
        # The form agents write most often after the bare one.
        self.assertEqual(cmd('[ -n "$CASPER_WORKSPACE_ID" ] && { casper notify --message="x"; '
                             'casper status set blocked; } || true'),
                         ["notify", "status"])

    def test_a_mention_is_not_a_call(self):
        self.assertEqual(cmd('grep -rn "casper notify" skills/'), [])
        self.assertEqual(cmd("echo casper notify"), [])

    def test_an_argv_list_is_searched_element_by_element(self):
        self.assertEqual(cmd(["bash", "-lc", "casper notify -m x"]), ["notify"])

    def test_no_command_at_all(self):
        self.assertEqual(notified.casper_subcommands({"file_path": "x"}), [])
        self.assertEqual(notified.casper_subcommands(None), [])

class TestEpisode(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        os.environ["CLAUDE_PLUGIN_DATA"] = self.dir
        self.addCleanup(os.environ.pop, "CLAUDE_PLUGIN_DATA", None)

    def tool(self, command):
        notified.observe_tool({"session_id": "s", "tool_input": {"command": command}})

    def test_notify_covers_one_real_tool_call(self):
        self.tool("casper notify -m x")
        self.assertTrue(notified.agent_notified("s"))
        self.tool("casper status set blocked")
        self.assertTrue(notified.agent_notified("s"))
        self.tool("make deploy")
        self.assertTrue(notified.agent_notified("s"))
        self.tool("make test")
        self.assertFalse(notified.agent_notified("s"))

    def test_clear(self):
        self.tool("casper notify -m x")
        notified.clear("s")
        self.assertFalse(notified.agent_notified("s"))
        notified.clear("s")  # already gone: still fine

if __name__ == "__main__":
    unittest.main()
