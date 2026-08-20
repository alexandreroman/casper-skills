import subprocess, unittest
from harness import CasperStub

class TestCasperStub(unittest.TestCase):
    def test_records_argv(self):
        with CasperStub() as stub:
            subprocess.run(["casper", "status", "set", "blocked"], env=stub.env())
            self.assertEqual(stub.calls, [["status", "set", "blocked"]])

if __name__ == "__main__":
    unittest.main()
