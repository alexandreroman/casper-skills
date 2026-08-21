import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from hooks.lib import guidance

GUIDANCE_MD = os.path.join(ROOT, ".opencode", "plugin", "guidance.md")

REGENERATE = ("regenerate: python3 -c \"import sys;sys.path.insert(0,'.');"
              "from hooks.lib import guidance;"
              "open('.opencode/plugin/guidance.md','w').write(guidance.render())\"")


class TestGuidanceSync(unittest.TestCase):
    def test_opencode_copy_matches_the_source(self):
        # opencode's plugin points at this file rather than printing text, so
        # it ships the default rendering: the skill's path stays relative
        # there, because nothing writes into the file at runtime.
        with open(GUIDANCE_MD) as f:
            self.assertEqual(f.read(), guidance.render(), REGENERATE)

    def test_no_rendering_leaves_the_placeholder_behind(self):
        # A placeholder surviving into an agent's context is worse than no
        # path at all: it names a file that does not exist.
        for rendered in (guidance.render(), guidance.render("/plugins/casper")):
            self.assertNotIn("{skill_path}", rendered)
            self.assertIn(guidance.SKILL_PATH, rendered)

    def test_the_absolute_path_is_used_when_the_plugin_root_is_known(self):
        self.assertIn("/plugins/casper/skills/casper/SKILL.md",
                      guidance.render("/plugins/casper"))

    def test_the_path_it_names_is_the_skill_that_ships(self):
        # The one way this guidance can be actively harmful: sending every
        # session in every Casper workspace to a file that is not there.
        self.assertTrue(os.path.isfile(os.path.join(ROOT, guidance.SKILL_PATH)))


if __name__ == "__main__":
    unittest.main()
