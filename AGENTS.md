## Purpose

- Personal macOS dotfiles managed by Dotbot via `install.conf.yaml`
- Most tracked config sources live in feature directories and end with `.symlink`

## Do Not Touch

- Do not modify `dotbot/`; it is a vendored git submodule
- Do not commit secrets, private keys, tokens, or machine-specific credentials
- Edit `claude/settings.symlink.json`, not `~/.claude/settings.json`

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
