# Casper diff

When the user explicitly asks to see a diff — the full diff or one for a
particular file ("montre-moi le diff", "fais voir ce qui a changé dans ce
fichier", "je veux revoir le diff avant de commit") — open it in Casper's
diff view, in addition to or instead of printing it as text:

```bash
casper diff open          # full diff
casper diff open <file>   # scrolled to one file
```

When the user explicitly asks to close it ("ferme le diff", "close the diff
view", "cache le diff") — collapse it instead:

```bash
casper diff close
```

If the command fails or `casper` isn't found, fall back to the normal
`git diff` output.

There is no automatic trigger before every commit — these commands only fire
when the user asks.
