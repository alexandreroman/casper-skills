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

    def test_message_field_preferred_within_allowlist(self):
        # A real payload message wins over the canned FRIENDLY text, but only
        # for an allowlisted type — the message alone never triggers a notify.
        self.run_hook({"notification_type": "permission_prompt", "message": "Custom text"})
        expected = "status\nset\nblocked\n---\nnotify\n--message\nCustom text\n---\n"
        self.assertEqual(self.log_tail(), expected)

    def test_message_field_alone_is_silent(self):
        # No notification_type at all is not in the allowlist: stay silent.
        self.run_hook({"message": "Custom text"})
        self.assertEqual(self.log_tail(), "")

    def test_permission_prompt_maps_to_friendly_text(self):
        self.run_hook({"notification_type": "permission_prompt"})
        expected = (
            "status\nset\nblocked\n---\n"
            "notify\n--message\nClaude needs your permission to continue\n---\n"
        )
        self.assertEqual(self.log_tail(), expected)

    def test_idle_prompt_is_silent(self):
        self.run_hook({"notification_type": "idle_prompt"})
        self.assertEqual(self.log_tail(), "")

    def test_elicitation_dialog_sets_blocked_status(self):
        self.run_hook({"notification_type": "elicitation_dialog"})
        expected = (
            "status\nset\nblocked\n---\n"
            "notify\n--message\nClaude needs additional input\n---\n"
        )
        self.assertEqual(self.log_tail(), expected)

    def test_auth_success_is_skipped(self):
        self.run_hook({"notification_type": "auth_success"})
        self.assertEqual(self.log_tail(), "")

    def test_unknown_type_is_silent(self):
        self.run_hook({"notification_type": "something_new"})
        self.assertEqual(self.log_tail(), "")

    def test_no_fields_at_all_is_silent(self):
        self.run_hook({})
        self.assertEqual(self.log_tail(), "")


if __name__ == "__main__":
    unittest.main()
