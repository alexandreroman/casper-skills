import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from hooks.lib.guidance import TEXT

GUIDANCE_MD = os.path.join(ROOT, ".opencode", "plugin", "guidance.md")

class TestGuidanceSync(unittest.TestCase):
    def test_opencode_copy_matches_the_source(self):
        with open(GUIDANCE_MD) as f:
            self.assertEqual(f.read(), TEXT,
                "regenerate: python3 -c \"import sys;sys.path.insert(0,'.');"
                "from hooks.lib.guidance import TEXT;"
                "open('.opencode/plugin/guidance.md','w').write(TEXT)\"")

if __name__ == "__main__":
    unittest.main()
