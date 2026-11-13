import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hooks.lib import codex_server


class TestBelongs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        self.ws = os.path.join(self.root, "proj-a")
        self.sibling = os.path.join(self.root, "proj-a-b")
        for d in (self.ws, os.path.join(self.ws, "sub"), self.sibling):
            os.makedirs(d)

    def tearDown(self):
        self.tmp.cleanup()

    def listing(self, path=None):
        return [{"workspace": "other-id", "name": "other", "path": "/elsewhere"},
                {"workspace": "ws-id", "name": "proj-a", "path": path or self.ws}]

    def test_session_in_the_workspace_belongs(self):
        self.assertIs(codex_server.belongs(self.listing(), "ws-id", self.ws), True)

    def test_session_in_a_subdirectory_belongs(self):
        self.assertIs(codex_server.belongs(self.listing(), "ws-id",
                                           os.path.join(self.ws, "sub")), True)

    def test_session_elsewhere_does_not(self):
        self.assertIs(codex_server.belongs(self.listing(), "ws-id", self.root), False)

    def test_a_sibling_sharing_the_prefix_does_not(self):
        # /x/proj-a-b is not inside /x/proj-a, however the strings compare.
        self.assertIs(codex_server.belongs(self.listing(), "ws-id", self.sibling), False)

    def test_the_workspace_name_also_identifies_it(self):
        self.assertIs(codex_server.belongs(self.listing(), "proj-a", self.ws), True)

    def test_paths_compare_resolved(self):
        link = os.path.join(self.root, "link")
        os.symlink(self.ws, link)
        self.assertIs(codex_server.belongs(self.listing(path=link), "ws-id", self.ws), True)

    def test_what_cannot_be_checked_is_unknown(self):
        # Unknown lets the hook run: a check that cannot be made must not
        # switch the integration off.
        self.assertIsNone(codex_server.belongs(None, "ws-id", self.ws))
        self.assertIsNone(codex_server.belongs({"error": "x"}, "ws-id", self.ws))
        self.assertIsNone(codex_server.belongs(self.listing(), "", self.ws))
        self.assertIsNone(codex_server.belongs(self.listing(), "missing", self.ws))
        no_path = [{"workspace": "ws-id", "name": "proj-a"}]
        self.assertIsNone(codex_server.belongs(no_path, "ws-id", self.ws))

    def test_warning_tells_the_agent_to_stay_off_casper_and_how_to_fix_it(self):
        self.assertIn("Do not run `casper`", codex_server.WARNING)
        self.assertIn("codex --no-daemon", codex_server.WARNING)


if __name__ == "__main__":
    unittest.main()
