import json, os, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load = lambda *p: json.load(open(os.path.join(ROOT, *p)))

class TestManifests(unittest.TestCase):
    def test_plugin_name_is_stable(self):
        self.assertEqual(load(".claude-plugin", "plugin.json")["name"], "casper")

    def test_marketplace_name_is_stable(self):
        # Together with plugin.json's name this fixes the Claude Code registry
        # key at "casper@casper"; the Casper app probes for that exact literal.
        self.assertEqual(load(".claude-plugin", "marketplace.json")["name"], "casper")

    def test_homepage_points_at_the_repo(self):
        self.assertIn("casper-skills", load(".claude-plugin", "plugin.json")["homepage"])
        # The marketplace entry's own homepage is the link users actually
        # click from a marketplace listing, so it is checked independently
        # of plugin.json's.
        marketplace = load(".claude-plugin", "marketplace.json")
        self.assertIn("casper-skills", marketplace["plugins"][0]["homepage"])

    def test_versions_agree(self):
        plugin = load(".claude-plugin", "plugin.json")["version"]
        entry = load(".claude-plugin", "marketplace.json")["plugins"][0]["version"]
        self.assertEqual(plugin, entry)
        self.assertEqual(load("package.json")["version"], plugin)

    def test_package_main_is_the_opencode_plugin(self):
        self.assertEqual(load("package.json")["main"], ".opencode/plugin/casper.js")

    def test_package_declares_no_dependencies(self):
        pkg = load("package.json")
        self.assertNotIn("dependencies", pkg)

    def test_package_is_an_es_module(self):
        self.assertEqual(load("package.json")["type"], "module")

    def test_opencode_plugin_version_constant_matches_package(self):
        # The Casper app probes the installed plugin file for this line to
        # decide whether the integration is current, so it must not drift.
        import re
        src = open(os.path.join(ROOT, ".opencode", "plugin", "casper.js")).read()
        m = re.search(r'export const CASPER_PLUGIN_VERSION = "([^"]+)"', src)
        self.assertIsNotNone(m, "casper.js must declare CASPER_PLUGIN_VERSION on one line")
        self.assertEqual(m.group(1), load("package.json")["version"])

if __name__ == "__main__":
    unittest.main()
