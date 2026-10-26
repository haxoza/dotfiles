# dotfiles

Personal macOS dotfiles managed with [Dotbot](https://github.com/anishathalye/dotbot).

This repo installs shell and tool configuration by symlinking tracked files into `$HOME`. It also includes a few companion workflows for Homebrew package management and Mackup-based app settings restore.

## What's here

- `install` bootstraps the Dotbot submodule and applies `install.conf.yaml`
- `zsh/` contains the main shell setup, sourced helper files, and prompt/tooling config
- `git/`, `vim/`, `ssh/`, `gpg/`, `conda/`, `hg/`, `pypi/`, `cursor/`, `starship/` hold symlinked app configs
- `claude/` holds Claude Code settings — permissions deny rules and sandbox config based on [trailofbits/claude-code-config](https://github.com/trailofbits/claude-code-config) and own research. `claude/settings.json` is merged into `~/.claude/settings.json` rather than symlinked, see [Claude Code settings](#claude-code-settings)
- `homebrew/` contains Homebrew bootstrap and `Brewfile` helpers
- `aerospace/` holds full machine-specific window manager configs; see [AeroSpace](aerospace/README.md)
- `mackup/` stores macOS application preferences managed with Mackup

## Managed links

`install.conf.yaml` currently links:

- `~/.zshenv`, `~/.zshrc`, `~/.zprofile`
- `~/.gitconfig`, `~/.gitconfig.local`, `~/.gitignore`
- `~/.vimrc`
- `~/.aerospace.toml`, selected using `.machine`
- `~/.ssh/config`, `~/.ssh/config.local`, and the machine-selected 1Password agent config
- `~/.gnupg/gpg.conf`, `~/.gnupg/gpg-agent.conf`
- `~/.condarc`, `~/.hgrc`, `~/.hgrc.local`, `~/.pypirc`
- `~/.config/starship.toml`
- `~/.cursor/sandbox.json`

## Setup

Clone the repo with submodules, restore the [private settings](#private-settings-in-1password), then run the installer:

```bash
git clone --recurse-submodules <repo-url> ~/dev/projects/dotfiles
cd ~/dev/projects/dotfiles
# Set this checkout's machine alias (choose the matching entry in machines.yaml).
printf '%s\n' machine-2 > .machine
./1password/sync.py restore
./install
```

Useful variants:

```bash
./install -v
./install --force-color
```

The installer syncs and initializes the bundled `dotbot/` submodule automatically before applying links.
It requires a valid `.machine` and restored private SSH config before making
changes. Both SSH wrappers select the 1Password agent and support encrypted
local keys with macOS Keychain; machine-2's agent key list starts empty. See
[SSH setup](ssh/README.md) for key selection and recovery.

## Shell stack

The shell setup is centered on `zsh`:

- `zsh/zshenv.symlink` loads Homebrew and `fnm`
- `zsh/zprofile.symlink` reapplies Homebrew after macOS `path_helper`
- `zsh/zshrc.symlink` loads `zinit`, caches `starship init`, and sources all `zsh/*.zsh` helper files

Both machines use Apple Silicon with Homebrew at `/opt/homebrew`.
Homebrew and the tools in the Brewfile are required. Tool paths use
`HOMEBREW_PREFIX`, set by `brew shellenv`. `zshrc` resolves its symlink to locate
this checkout and uses `starship` for the prompt.

Git loads `~/.gitconfig.local` after all shared defaults, so machine-specific
values take precedence. GPG is resolved through `PATH`; set `gpg.program` in
the local config if a machine needs a specific executable.

## Homebrew

Bootstrap Homebrew:

```bash
homebrew/install.sh
```

Manage packages from `homebrew/Brewfile`:

```bash
cd homebrew
make install-packages
make dump
```

`dev-update` also verifies the Homebrew Codex CLI signature and clears its quarantine attribute after upgrading. See [Codex configuration](codex/README.md) for details.

## Mackup

Restore or back up macOS app settings:

```bash
cd mackup
make restore
make backup
```

## Claude Code settings

`~/.claude/settings.json` is a generated regular file because Claude Code and Orca rewrite it in place. `./install` runs `claude/sync-settings.sh merge` using two sources:

- `claude/settings.json` owns shared permissions, sandbox policy, status line, common UI preferences, and marketplaces.
- `claude/settings.machine-1.json` or `claude/settings.machine-2.json` owns caffeinate hooks, notification preferences, remote-control startup, and the complete plugin map. Machine-2 omits Superpowers, the two Sunscrapers plugins, and SDLC Toolkit because they aren't installed there. Reconcile machine-2's live settings before applying them there.

`DOTFILES_MACHINE` selects the machine, falling back to the repository's gitignored `.machine` file for direct script calls. A top-level key must belong to exactly one source file; duplicate ownership is rejected. Owned values replace live values wholesale, including plugin and marketplace maps. Keep each machine's complete plugin map in its machine file. If marketplaces need to differ by machine, move that entire map from the shared file into both machine files too.

- Edit the appropriate source, then run `./install` to apply it.
- Run `claude/sync-settings.sh status` to see drift by owning file, unowned live keys, and unrecognised hooks.
- Run `claude/sync-settings.sh export` to pull app changes back into their owning source files, then review with `git diff`. The other machine's file is untouched. Changes to shared maps affect both machines.
- Live-only top-level keys pass through and are never exported. `model`, `modelSettings`, and `autoMode` remain app-owned. To claim a new key, add it to the appropriate source with any value, then run export.
- Inside `hooks`, groups matching `VENDOR_HOOK_MARKERS` in the sync script belong to third parties. Merge preserves Orca groups; export excludes them. Other groups belong to the source owning `hooks`: merge replaces them, and export pulls them back. Export unknown hooks before merging if you want to keep them.
- Keep `"hooks": {}` in a machine file to disable caffeinate while preserving Orca hooks and retaining ownership.
- `claude/test-sync-settings.sh` runs fixture tests without touching `~/.claude`.

## Customization patterns

- Put machine-specific or sensitive values in `.local` files such as `git/gitconfig.local.symlink`
- Keep new managed files in their domain directory with a `.symlink` suffix
- Add new links in `install.conf.yaml` using repo-relative paths
- Use `create: true` when a target parent directory may not exist

Examples already ignored from git include `git/gitconfig.local.symlink`, `hg/hgrc.local.symlink`, and `pypi/pypirc.symlink`.

## Private settings in 1Password

Gitignored settings and the shared GPG signing key are backed up in 1Password.
Use [`1password/sync.py`](1password/sync.py) with `status`, `restore`, or `update`
for machine-specific settings, and `restore-gpg` for the shared signing key.
[`1password/machines.yaml`](1password/machines.yaml) maps machine aliases to vaults
and items. See the [private settings instructions](1password/README.md) for setup
and machine selection.

The gitignored root `.machine` file stores this checkout's machine alias as one
line. It is shared local configuration for repository tools; `sync.py` uses it
unless overridden with `--machine`.

## Adding a new dotfile

1. Create the source file in the appropriate directory with a `.symlink` suffix.
2. Add a mapping in `install.conf.yaml`.
3. Run `./install`.
4. Verify the symlink and the target application behavior.

## Notes

- Do not edit `dotbot/`; it is a vendored submodule.
- Avoid committing secrets, private keys, tokens, or machine-specific credentials.
