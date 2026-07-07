#!/usr/bin/env python3
import json, os, subprocess, sys, tempfile, unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "hooks", "notification.py")


def make_stub_casper(stub_dir):
    stub_path = os.path.join(stub_dir, "casper")
    with open(stub_path, "w") as f:
        f.write(
            "#!/usr/bin/env bash\n"
            "printf '%s\\n' \"$@\" >> \"$CASPER_LOG\"\n"
            "printf -- '---\\n' >> \"$CASPER_LOG\"\n"
        )
    os.chmod(stub_path, 0o755)


class TestNotification(unittest.TestCase):
    def setUp(self):
        self.stub_dir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.stub_dir, "log")
        make_stub_casper(self.stub_dir)
        self.env = dict(os.environ)
        self.env["PATH"] = self.stub_dir + ":" + self.env["PATH"]
        self.env["CASPER_LOG"] = self.log_path

    def run_hook(self, payload):
        subprocess.run(
            [sys.executable, SCRIPT], input=json.dumps(payload), text=True,
            env=self.env, timeout=5,
        )

    def log_tail(self):
        if not os.path.exists(self.log_path):
            return ""
        with open(self.log_path) as f:
            return f.read()

    def test_forwards_message_field_verbatim(self):
        self.run_hook({"message": "Custom text"})
        expected = "notify\n--message\nCustom text\n---\n"
        self.assertEqual(self.log_tail(), expected)

    def test_permission_prompt_maps_to_friendly_text(self):
        self.run_hook({"notification_type": "permission_prompt"})
        expected = "notify\n--message\nClaude needs your permission to continue\n---\n"
        self.assertEqual(self.log_tail(), expected)

    def test_idle_prompt_maps_to_friendly_text(self):
        self.run_hook({"notification_type": "idle_prompt"})
        expected = "notify\n--message\nClaude is waiting for your input\n---\n"
        self.assertEqual(self.log_tail(), expected)

    def test_auth_success_is_skipped(self):
        self.run_hook({"notification_type": "auth_success"})
        self.assertEqual(self.log_tail(), "")

    def test_unknown_type_falls_back_to_generic_message(self):
        self.run_hook({"notification_type": "something_new"})
        expected = "notify\n--message\nClaude needs your attention\n---\n"
        self.assertEqual(self.log_tail(), expected)

    def test_no_fields_at_all_falls_back_to_generic_message(self):
        self.run_hook({})
        expected = "notify\n--message\nClaude needs your attention\n---\n"
        self.assertEqual(self.log_tail(), expected)


if __name__ == "__main__":
    unittest.main()
