import json, os, subprocess, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from harness import CasperStub

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "session-start.py")

SKILL = "skills/casper/SKILL.md"

def run_hook(stub, payload, **env):
    return subprocess.run(
        [HOOK], input=json.dumps(payload), env=stub.env(**env),
        capture_output=True, text=True, cwd=ROOT,
    )

def run_hook_rootless(stub, **root_env):
    """Run the hook with both agents' plugin-root variables cleared first.

    The test process inherits whichever one its own harness exported, so the
    fallback can only be exercised from a known-empty starting point.
    """
    env = stub.env()
    for var in ("CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT"):
        env.pop(var, None)
    env.update(root_env)
    return subprocess.run(
        [HOOK], input=json.dumps({"source": "startup"}), env=env,
        capture_output=True, text=True, cwd=ROOT,
    )

class TestSessionStart(unittest.TestCase):
    def test_fresh_start_clears_everything(self):
        with CasperStub() as stub:
            run_hook(stub, {"source": "startup"})
            self.assertEqual(stub.calls, [
                ["status", "set", "idle"],
                ["progress", "clear"],
                ["info", "clear"],
            ])

    def test_clear_source_also_clears_info(self):
        with CasperStub() as stub:
            run_hook(stub, {"source": "clear"})
            self.assertIn(["info", "clear"], stub.calls)

    def test_resume_keeps_the_info_panel(self):
        with CasperStub() as stub:
            run_hook(stub, {"source": "resume"})
            self.assertEqual(stub.calls, [
                ["status", "set", "idle"],
                ["progress", "clear"],
            ])

    def test_compact_keeps_the_info_panel(self):
        with CasperStub() as stub:
            run_hook(stub, {"source": "compact"})
            self.assertNotIn(["info", "clear"], stub.calls)

    def test_prints_the_guidance(self):
        with CasperStub() as stub:
            proc = run_hook(stub, {"source": "startup"})
            self.assertIn("casper notify --message", proc.stdout)

    def test_the_guidance_names_the_observed_failure_mode(self):
        # SessionStart stdout is the one thing every session provably sees,
        # so the thing an agent must not do belongs in it by name.
        with CasperStub() as stub:
            proc = run_hook(stub, {"source": "startup"})
            self.assertIn("casper --help", proc.stdout)
            self.assertIn("before your first `casper` command", proc.stdout)

    def test_claude_codes_plugin_root_resolves_the_skill_path(self):
        with CasperStub() as stub:
            proc = run_hook_rootless(stub, CLAUDE_PLUGIN_ROOT="/plugins/casper")
            self.assertIn("/plugins/casper/" + SKILL, proc.stdout)

    def test_codexs_own_plugin_root_resolves_the_skill_path(self):
        # Codex's native name is PLUGIN_ROOT; CLAUDE_PLUGIN_ROOT is only its
        # compatibility mirror, so the guidance must not depend on the mirror.
        with CasperStub() as stub:
            proc = run_hook_rootless(stub, PLUGIN_ROOT="/plugins/casper")
            self.assertIn("/plugins/casper/" + SKILL, proc.stdout)

    def test_no_plugin_root_still_names_the_skill(self):
        with CasperStub() as stub:
            proc = run_hook_rootless(stub)
            self.assertIn(SKILL, proc.stdout)

    def test_malformed_stdin_is_survivable(self):
        with CasperStub() as stub:
            proc = subprocess.run(
                [HOOK], input="not json", env=stub.env(),
                capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn(["info", "clear"], stub.calls)

    def test_outside_casper_makes_no_calls(self):
        with CasperStub() as stub:
            env = stub.env()
            env.pop("CASPER_WORKSPACE_ID", None)
            subprocess.run([HOOK], input=json.dumps({"source": "startup"}),
                           env=env, capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(stub.calls, [])

if __name__ == "__main__":
    unittest.main()
