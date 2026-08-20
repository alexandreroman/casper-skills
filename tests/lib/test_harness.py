import subprocess, unittest
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

if __name__ == "__main__":
    unittest.main()
