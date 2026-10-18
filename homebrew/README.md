# Homebrew

`Brewfile` lists shared packages, grouped by purpose. `Brewfile.machine-1` and
`Brewfile.machine-2` include it and add machine-specific packages. Keep taps before
package entries and preserve package options when reorganizing categories.

Run commands from this directory:

```bash
make install           # Bootstrap Homebrew
make install-packages  # Select the machine using ../.machine
make dump              # Write Brewfile.snapshot.local
```

Override the machine with `make install-packages MACHINE=machine-2`. A missing or
unknown machine alias stops installation. For direct Homebrew commands, pass
`--file=homebrew/Brewfile.machine-1` (or `machine-2`) from the repository root.
Use the complete machine Brewfile for cleanup, rather than the shared file alone.

`Brewfile.snapshot.local` is gitignored and overwritten by each dump. Compare it
with `Brewfile` and incorporate desired changes manually to preserve categories:

```bash
diff -u Brewfile Brewfile.snapshot.local
```

Brewfiles record package choices, not exact version locks. See the
[Homebrew Bundle documentation](https://docs.brew.sh/Brew-Bundle-and-Brewfile).
