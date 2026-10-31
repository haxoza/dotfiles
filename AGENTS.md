## Purpose

- Personal macOS dotfiles managed by Dotbot via `install.conf.yaml`
- Most tracked config sources live in feature directories and end with `.symlink`
- Private settings live in 1Password per machine, GPG is shared. Use IDs rather than personal names in public references.

## Do Not Touch

- Do not modify `dotbot/`; it is a vendored git submodule
- Do not commit secrets, private keys, tokens, or machine-specific credentials
- Edit `claude/settings.json` or `claude/settings.machine-*.json` and run `./install`; never edit `~/.claude/settings.json` directly.
  It is a merged file, not a symlink. Pull app-side changes back with `claude/sync-settings.sh export`
- Codex sources are `codex/common.toml`, `codex/config.machine-*.toml`, and the gitignored
  `codex/trusted.local.toml`. `~/.codex/config.toml` is a merged app-writable regular file;
  model selection stays app-owned. Reconcile app changes with `make -C codex export`
  before merging. Use `status` to inspect ownership/drift; keep live and legacy generated backups.
  For Codex-only changes use `make -C codex merge`, not the full installer. A new worktree
  needs an explicit `DOTFILES_MACHINE` or its own `.machine`; never borrow another machine's trust.

## Repo Conventions

- Add new managed files in the appropriate directory with a `.symlink` suffix
- Register new links in `install.conf.yaml` using repo-relative paths
- Use `create: true` when the target parent directory may not exist
- Keep machine-specific overrides in `.local.symlink` files when applicable and keep them gitignored
- Shell scripts should use `#!/usr/bin/env bash` or `#!/usr/bin/env zsh`, `set -e`, and properly quoted variables
- Zsh helper files live in `zsh/*.zsh` and are sourced from `zsh/zshrc.symlink`

## Commit Format

- Follow Conventional Commits: `type(scope): description`
- Common types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
