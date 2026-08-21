"""Pin what this repo claims about the `casper` CLI against the real thing.

Everything else in the suite tests this plugin against itself. This one test
talks to the installed `casper`, because the failure it exists for cannot be
caught any other way: a reference file that understates the CLI. A synopsis
missing a flag does not look broken — it reads as a complete description, and
an agent that reads it comes away believing the flag does not exist. That
happened: `casper workspace new`'s synopsis omitted `--workspace` while
`delete`'s carried it, so the file argued against itself, and a session
concluded it could not create a workspace in another Space, then built a
workaround around that conclusion.

Skipped, loudly, when `casper` is not on PATH — it is only reachable inside a
terminal Casper opened, so run the suite from one to get this coverage.
"""
import os, re, shutil, subprocess, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_MD = os.path.join(ROOT, "skills", "casper", "references", "workspace.md")


def casper_help(*path):
    proc = subprocess.run(["casper", "help", *path], capture_output=True, text=True)
    return proc.stdout


def subcommands_of(*path):
    """The subcommand names `casper help <path>` lists, in CLI order."""
    block = casper_help(*path).split("SUBCOMMANDS:", 1)
    if len(block) == 1:
        return []
    names = []
    for line in block[1].splitlines():
        match = re.match(r"^  (\S+)\s{2,}", line)
        if match:
            names.append(match.group(1))
        elif line.strip().startswith("See '"):
            break
    return names


def usage_of(*path):
    for line in casper_help(*path).splitlines():
        if line.startswith("USAGE: "):
            return line[len("USAGE: "):]
    return ""


@unittest.skipIf(shutil.which("casper") is None,
                 "casper is not on PATH; run this suite from a Casper terminal")
class TestWorkspaceReference(unittest.TestCase):
    def setUp(self):
        with open(WORKSPACE_MD) as f:
            self.text = f.read()

    def test_the_synopses_carry_every_flag_the_cli_accepts(self):
        # The exact regression. Checked against `casper help`, not against a
        # copy of it, so it cannot pass by agreeing with a stale snapshot.
        for sub in ("new", "delete"):
            with self.subTest(sub=sub):
                flags = set(re.findall(r"--[a-z-]+", usage_of("workspace", sub)))
                self.assertTrue(flags, f"casper help workspace {sub} reported no flags")
                synopsis = next(
                    (line for line in self.text.splitlines()
                     if line.startswith(f"casper workspace {sub}")), None)
                self.assertIsNotNone(synopsis, f"no synopsis line for casper workspace {sub}")
                for flag in flags:
                    self.assertIn(flag, synopsis or "",
                                  f"casper workspace {sub}'s synopsis understates the CLI")

    def test_every_subcommand_the_cli_offers_is_documented(self):
        # The CLI can also grow past the reference, and a surface documented
        # as smaller than it is teaches an agent a command does not exist.
        for sub in subcommands_of("workspace"):
            with self.subTest(sub=sub):
                self.assertIn(f"casper workspace {sub}", self.text)

    def test_the_absent_subcommands_are_still_absent(self):
        # The reference tells the reader `close` and `merge` do not exist and
        # names the five-step procedure instead. Nothing enforces that at
        # runtime — the CLI's own non-zero exit status is the signal an agent
        # is expected to act on — so this claim has to stay true on its own,
        # and it is the only thing standing between a guess and the wrong
        # conclusion drawn from it.
        real = set(subcommands_of("workspace"))
        for sub in ("close", "merge"):
            with self.subTest(sub=sub):
                self.assertNotIn(sub, real)
        self.assertIn("There is no `casper workspace close` subcommand", self.text)


if __name__ == "__main__":
    unittest.main()
