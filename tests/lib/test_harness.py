import json, subprocess, unittest
from harness import CasperStub

class TestCasperStub(unittest.TestCase):
    def test_records_argv(self):
        with CasperStub() as stub:
            subprocess.run(["casper", "status", "set", "blocked"], env=stub.env())
            self.assertEqual(stub.calls, [["status", "set", "blocked"]])

    def test_multi_word_argument_survives(self):
        with CasperStub() as stub:
            subprocess.run(["casper", "notify", "--message", "run the test suite"], env=stub.env())
            self.assertEqual(stub.calls, [["notify", "--message", "run the test suite"]])

    def test_trailing_empty_argument_survives(self):
        with CasperStub() as stub:
            subprocess.run(["casper", "notify", "--message", ""], env=stub.env())
            self.assertEqual(stub.calls, [["notify", "--message", ""]])

    def test_a_read_verb_answers_from_its_canned_reply(self):
        with CasperStub() as stub:
            env = stub.env(**CasperStub.replies(status="blocked", bar=True))
            out = subprocess.run(["casper", "status", "get"], env=env,
                                 capture_output=True, text=True)
            self.assertEqual(json.loads(out.stdout)["status"], "blocked")
            out = subprocess.run(["casper", "progress", "get"], env=env,
                                 capture_output=True, text=True)
            self.assertEqual(json.loads(out.stdout)["progress"]["current"], 2)
            self.assertEqual(stub.calls, [["status", "get"], ["progress", "get"]])

    def test_an_unanswered_read_verb_prints_nothing(self):
        # What a `casper` too old for the verb, or a stopped app, looks like.
        with CasperStub() as stub:
            out = subprocess.run(["casper", "progress", "get"], env=stub.env(),
                                 capture_output=True, text=True)
            self.assertEqual(out.stdout, "")
            self.assertEqual(out.returncode, 0)

    def test_no_bar_is_answered_as_an_explicit_null(self):
        with CasperStub() as stub:
            out = subprocess.run(["casper", "progress", "get"],
                                 env=stub.env(**CasperStub.replies(bar=False)),
                                 capture_output=True, text=True)
            self.assertIsNone(json.loads(out.stdout)["progress"])

    def test_an_argument_cannot_compose_an_env_var_name(self):
        # The reply lookup only ever builds a name from plain lowercase verbs.
        with CasperStub() as stub:
            env = stub.env(**CasperStub.replies(status="blocked"))
            env["CASPER_STUB_OUT_notify_--message"] = "leak"
            out = subprocess.run(["casper", "notify", "--message", "x"], env=env,
                                 capture_output=True, text=True)
            self.assertEqual(out.stdout, "")

if __name__ == "__main__":
    unittest.main()
