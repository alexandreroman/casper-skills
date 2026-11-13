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

    def test_plugin_does_not_declare_the_standard_hooks_file(self):
        # Claude Code loads hooks/hooks.json on its own; naming it again in
        # manifest.hooks makes the plugin fail to install with a duplicate
        # hooks file error. manifest.hooks is only for extra hook files.
        self.assertNotIn("hooks", load(".claude-plugin", "plugin.json"))

    def test_package_exports_both_opencode_parts(self):
        # opencode ignores `main`: a plugin directory loads only through
        # `exports` (or root-level server/index/tui files), and without the
        # `./tui` part nothing drives the sidebar on opencode's shared
        # server. Measured on opencode 2.3.0, which loaded nothing at all
        # from this package while it had only `main`.
        exports = load("package.json")["exports"]
        self.assertEqual(exports["."], "./.opencode/plugin/casper.js")
        self.assertEqual(exports["./tui"], "./.opencode/plugin/tui.js")
        for target in (exports["."], exports["./tui"]):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, target)), target)

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
