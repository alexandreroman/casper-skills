import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from hooks.lib.guidance import TEXT

class TestGuidance(unittest.TestCase):
    def test_mentions_the_notify_mechanism(self):
        self.assertIn("casper notify --message", TEXT)

    def test_mentions_blocked_status(self):
        self.assertIn("casper status set blocked", TEXT)

    def test_is_agent_neutral(self):
        lowered = TEXT.lower()
        for banned in ("claude", "codex", "opencode", "taskcreate", "taskupdate"):
            self.assertNotIn(banned, lowered, f"guidance names a specific agent or tool: {banned}")

    def test_points_at_the_entry_skill(self):
        # The guidance is the deterministic half of the entry skill's trigger:
        # description matching is a bet, but this hook only runs when the
        # session really is in a Casper terminal.
        self.assertIn("Read the `casper` skill", TEXT)

    def test_ends_with_newline(self):
        self.assertTrue(TEXT.endswith("\n"))

if __name__ == "__main__":
    unittest.main()
