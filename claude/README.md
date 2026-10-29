# Claude Code settings

The permissions deny rules and sandbox configuration are based on
[trailofbits/claude-code-config](https://github.com/trailofbits/claude-code-config)
and additional research.

Run the commands below from the repository root.

`~/.claude/settings.json` is a generated regular file because Claude Code and
Orca rewrite it in place. `./install` runs `claude/sync-settings.sh merge` using
two sources:

- `claude/settings.json` owns shared permissions, sandbox policy, status line,
  common UI preferences, and marketplaces.
- `claude/settings.machine-1.json` or `claude/settings.machine-2.json` owns
  caffeinate hooks, notification preferences, remote-control startup, and the
  complete plugin map. Machine-2 omits Superpowers, the two Sunscrapers plugins,
  and SDLC Toolkit because they aren't installed there. Reconcile machine-2's
  live settings before applying them there.

`DOTFILES_MACHINE` selects the machine, falling back to the repository's
gitignored `.machine` file for direct script calls. A top-level key must belong
to exactly one source file; duplicate ownership is rejected. Owned values
replace live values wholesale, including plugin and marketplace maps. Keep each
machine's complete plugin map in its machine file. If marketplaces need to
differ by machine, move that entire map from the shared file into both machine
files too.

- Edit the appropriate source, then run `./install` to apply it.
- Run `claude/sync-settings.sh status` to see drift by owning file, unowned live
  keys, and unrecognised hooks.
- Run `claude/sync-settings.sh export` to pull app changes back into their owning
  source files, then review with `git diff`. The other machine's file is
  untouched. Changes to shared maps affect both machines.
- Live-only top-level keys pass through and are never exported. `model`,
  `modelSettings`, and `autoMode` remain app-owned. To claim a new key, add it to
  the appropriate source with any value, then run export.
- Inside `hooks`, groups matching `VENDOR_HOOK_MARKERS` in the sync script belong
  to third parties. Merge preserves Orca groups; export excludes them. Other
  groups belong to the source owning `hooks`: merge replaces them, and export
  pulls them back. Export unknown hooks before merging if you want to keep them.
- Keep `"hooks": {}` in a machine file to disable caffeinate while preserving
  Orca hooks and retaining ownership.
- `claude/test-sync-settings.sh` runs fixture tests without touching `~/.claude`.
