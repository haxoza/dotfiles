# Codex configuration

This directory stores the Codex settings we want to keep across installs and
machines. The sync commands copy settings between these files and
`~/.codex/config.toml`, the file Codex uses while you work.

Choose your model in Codex as usual. The sync commands preserve that choice.

## Everyday commands

From the repository root, enter this directory:

```bash
cd codex
```

Then use:

| Command | What it does |
| --- | --- |
| `make status` | Shows differences between these files and your current Codex settings. Changes nothing. |
| `make merge` | Applies settings from this directory to Codex. |
| `make export` | Saves changes made in Codex back to the appropriate files here. |
| `make test` | Runs tests using temporary files. |

Running just `make` shows status too. These commands use Homebrew's `uv`, which
is included in the Brewfile.

**After editing a file here**, run `make merge` to apply it. The repository's
main installer also runs this step.

**After changing settings in Codex**, run `make export`, then review
`git diff -- .`. Check `trusted.local.toml` separately if private settings changed;
Git ignores that file.

If you're unsure which version to keep, start with `make status`. It calls a
setting “drifted” when the two versions differ. Merge keeps the version in this
directory; export keeps the version currently used by Codex.

## Which file should I edit?

| File | Put these settings here |
| --- | --- |
| `common.toml` | Settings shared by both Macs: approval and sandbox rules, reasoning preferences, and the terminal status line. |
| `config.machine-1.toml` | Machine-1's desktop preferences and plugin selections. |
| `config.machine-2.toml` | Machine-2's desktop preferences and plugin selections. |
| `trusted.local.toml` | This Mac's private project trust, paths, hooks, integrations, and local app state. Never commit it. |

Export updates the shared file, the selected machine's file, and the private
local file as needed. It leaves the other machine's file alone. Remember that
changes to `common.toml` will also apply on the other Mac when you merge there.

Settings added by Codex that we don't manage stay in the live config. They survive
merge and usually aren't exported. Private settings such as new project trust
entries are an exception: export saves them in `trusted.local.toml` automatically.
If that file is missing, export can create it from this Mac's current settings.

## Migrating an existing checkout or worktree

The commands need to know which Mac you're using. They read the repository's
`.machine` file unless you set `DOTFILES_MACHINE` in your shell. The only accepted
values are `machine-1` and `machine-2`.

A new worktree may be missing both `.machine` and `trusted.local.toml`. Select
the actual machine, then capture its existing settings before applying anything.
Run these commands from `codex/`:

```bash
export DOTFILES_MACHINE=machine-1
make status
make export
git diff -- .
```

Use `machine-2` on the other Mac. Review the exported files, including the private
local file. Then apply the settings:

```bash
make merge
```

On a fresh installation with no live config yet, skip export and use `make merge`
to create it. Never copy one Mac's private trust settings to the other.

**Machine-2 still needs its first review.** Its tracked file starts with the old
shared desktop and plugin settings. Export and review its actual settings on
that Mac before merging.

Use this targeted workflow when setting up a worktree. The full repository
installer also changes other apps' settings and requires the repository's
`.machine` file.

## Backups and the old symlink

Before changing an existing live config, merge saves its contents beside it in
`~/.codex/config.toml.<timestamp>.<unique suffix>.bak`.

If your config is still a symlink to the old generated repository file, merge
replaces that link with a regular file Codex can edit. The old target and all
existing backups stay intact. Export only reads the live file, so you can review
its settings before making this switch.

Keep the backups for recovery. New live files, private exports, and backups are
readable and writable only by your user (`0600`).

The old `generate-config.sh` command has been replaced by `make merge`.

## Adding or moving settings

Each managed setting must belong to one source file. If the same setting appears
in two sources, the command stops and asks you to resolve the overlap.

Most tables are replaced as a whole. In particular, the machine file must contain
its **complete plugin selection**, including disabled plugins. Merge replaces the
live plugin table with that selection.

`tui` and `desktop` are handled one field at a time. This lets shared
`tui.status_line` coexist with private TUI state and new fields added by Codex.
Both dotted keys and ordinary TOML tables work.

<details>
<summary>Less common cases and exact field names</summary>

- To start managing another setting, add it to the appropriate source file.
  You can then export to capture its current value from Codex.
- Keep `model` out of the source files; the script rejects it so your model choice
  stays under Codex's control.
- These fields can only go in `trusted.local.toml`: `projects`, `mcp_servers`,
  `hooks`, `notify`, `marketplaces`, `model_providers`, `model_instructions_file`,
  `tui.screen_reader_detection_done`, and `tui.model_availability_nux`.
- If a table such as `sandbox_workspace_write` needs private paths, move the whole
  table to the local file. Don't split it between shared and local files.
- If an individual value disappears from the live config, export removes it from
  its source. Missing tables become empty tables, so the source still manages them.

</details>

## Implementation and tests

Both Python scripts declare their dependencies inline. `uv` provides the same
pinned TOMLKit version for each; there are no Python packages to install manually.
The script parses and validates TOML before writing. When nothing has changed,
merge and export leave the files untouched.

`make test` covers merge, export, status, machine selection, backups, and migration
from the old symlink, all with temporary config files.

For development, `CODEX_CONFIG_SOURCE_DIR` overrides the source directory and
`CODEX_CONFIG_LIVE_FILE` overrides the live file. Otherwise the live file is
`${CODEX_HOME:-$HOME/.codex}/config.toml`.

For Codex's own settings, see the official [configuration guide](https://learn.chatgpt.com/docs/config-file/config-basic),
[field reference](https://learn.chatgpt.com/docs/config-file/config-reference), and
[plugin documentation](https://developers.openai.com/plugins/build/plugins).

## Homebrew updates

`dev-update` runs `clear-homebrew-quarantine.sh` after upgrading Homebrew packages.
This avoids repeated macOS first-open prompts for the Codex CLI. The script checks
that the binary belongs to the Homebrew Codex cask and verifies its OpenAI
signature before removing the quarantine attribute from that binary. Homebrew's
download checksum check still applies.
