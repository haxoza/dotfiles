# dotfiles

Personal macOS dotfiles managed with [Dotbot](https://github.com/anishathalye/dotbot).

This repo installs shell and tool configuration by symlinking tracked files into `$HOME`. It also includes a few companion workflows for Homebrew package management and Mackup-based app settings restore.

## What's here

- `install` bootstraps the Dotbot submodule and applies `install.conf.yaml`
- `zsh/` contains the main shell setup, sourced helper files, and prompt/tooling config
- `git/`, `vim/`, `ssh/`, `gpg/`, `conda/`, `hg/`, `pypi/`, `cursor/`, `starship/` hold symlinked app configs
- `claude/` holds Claude Code settings — permissions deny rules and sandbox config based on [trailofbits/claude-code-config](https://github.com/trailofbits/claude-code-config) and own research. `claude/settings.json` is merged into `~/.claude/settings.json` rather than symlinked, see [Claude Code settings](#claude-code-settings)
- `homebrew/` contains Homebrew bootstrap and `Brewfile` helpers
- `mackup/` stores macOS application preferences managed with Mackup

## Managed links

`install.conf.yaml` currently links:

- `~/.zshenv`, `~/.zshrc`, `~/.zprofile`
- `~/.gitconfig`, `~/.gitconfig.local`, `~/.gitignore`
- `~/.vimrc`
- `~/.ssh/config`
- `~/.gnupg/gpg.conf`, `~/.gnupg/gpg-agent.conf`
- `~/.condarc`, `~/.hgrc`, `~/.hgrc.local`, `~/.pypirc`
- `~/.config/starship.toml`
- `~/.cursor/sandbox.json`

## Setup

Clone the repo with submodules, then run the installer:

```bash
git clone --recurse-submodules <repo-url> ~/dev/projects/dotfiles
cd ~/dev/projects/dotfiles
./install
```

Useful variants:

```bash
./install -v
./install --force-color
```

The installer syncs and initializes the bundled `dotbot/` submodule automatically before applying links.

## Shell stack

The shell setup is centered on `zsh`:

- `zsh/zshenv.symlink` loads Homebrew and `fnm`
- `zsh/zprofile.symlink` reapplies Homebrew after macOS `path_helper`
- `zsh/zshrc.symlink` loads `zinit`, caches `starship init`, and sources all `zsh/*.zsh` helper files

This repo currently expects a Homebrew-installed `zinit` at `/opt/homebrew/opt/zinit/zinit.zsh` and uses `starship` for the prompt.

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

## Mackup

Restore or back up macOS app settings:

```bash
cd mackup
make restore
make backup
```

## Claude Code settings

`~/.claude/settings.json` is a generated file, not a symlink, because Claude Code and Orca rewrite it in place. `./install` runs `claude/sync-settings.sh merge`, which overlays the keys tracked in `claude/settings.json` onto the live file and passes everything else through, including Orca's hook entries.

- Edit `claude/settings.json`, then run `./install` to apply it.
- Run `claude/sync-settings.sh export` to pull changes made in the app (approved permissions, plugins) back into the tracked file, then review with `git diff`.
- `model` is deliberately not tracked: Claude Code rewrites it between sessions, so it passes through as an app-owned key.
- Run `claude/sync-settings.sh status` to see drifted keys, unowned live keys, and hook groups that are neither tracked nor vendor-marked.
- A top-level key present in `claude/settings.json` is repo-owned and replaced wholesale on merge. To start tracking a key the app added, put it in the tracked file with any value and run export.
- Inside `hooks`, groups whose command matches a marker in `VENDOR_HOOK_MARKERS` (in `claude/sync-settings.sh`) belong to a third party and pass through; all other groups are repo-owned.
- `claude/test-sync-settings.sh` runs the fixture tests for the script.

## Customization patterns

- Put machine-specific or sensitive values in `.local` files such as `git/gitconfig.local.symlink`
- Keep new managed files in their domain directory with a `.symlink` suffix
- Add new links in `install.conf.yaml` using repo-relative paths
- Use `create: true` when a target parent directory may not exist

Examples already ignored from git include `git/gitconfig.local.symlink`, `hg/hgrc.local.symlink`, and `pypi/pypirc.symlink`.

## Adding a new dotfile

1. Create the source file in the appropriate directory with a `.symlink` suffix.
2. Add a mapping in `install.conf.yaml`.
3. Run `./install`.
4. Verify the symlink and the target application behavior.

## Notes

- Do not edit `dotbot/`; it is a vendored submodule.
- Avoid committing secrets, private keys, tokens, or machine-specific credentials.
