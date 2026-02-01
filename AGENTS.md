# AGENTS.md - Agentic Coding Guidelines

This repository contains personal dotfiles managed with [Dotbot](https://github.com/anishathalye/dotbot). Dotbot is included as a git submodule and is only used as a symlink management tool - do not modify dotbot's source code.

## Build/Test/Install Commands

### Dotfiles Installation

```bash
# Full dotfiles installation (runs Dotbot with install.conf.yaml)
./install

# Install with specific config file
./install -c install.conf.yaml

# Dry run with verbose output
./install -v

# Force color output
./install --force-color
```

### Mackup (macOS App Settings Backup/Restore)

```bash
cd mackup

# Backup app settings to iCloud
make backup

# Restore app settings from iCloud
make restore
```

### Homebrew Setup

```bash
# Run Homebrew installation script
homebrew/install.sh
```

## Code Style Guidelines

### Shell Scripts
- **Shebang**: Use `#!/usr/bin/env bash` or `#!/usr/bin/env zsh`
- **Safety**: Always use `set -e` to exit on error
- **Style**: Follow existing scripts in `homebrew/install.sh` and the main `install` script
- **Quotes**: Quote variables properly: `"${VAR}"`
- **Functions**: Use lowercase with underscores
- **Comments**: Use `#` for comments, keep concise

### Zsh Configuration
- **Location**: Files in `zsh/` directory with `.symlink` extension
- **Variables**: Use UPPERCASE for exported variables, lowercase for local
- **Theme**: powerlevel9k (managed as git submodule in `zsh/themes/`)
- **Plugins**: zsh-autosuggestions, zsh-syntax-highlighting (git submodules)
- **Structure**: Keep machine-specific settings in `.local` files

### Configuration Files
- **Format**: YAML for Dotbot configs (`install.conf.yaml`)
- **Symlinks**: All dotfiles end with `.symlink` extension
- **Paths**: Use relative paths from repository root
- **Local overrides**: Use `.local` suffix for machine-specific configs (e.g., `gitconfig.local.symlink`)

### Git Configuration
- **User info**: Store in `gitconfig.local.symlink` (not committed)
- **Global settings**: Place in `git/gitconfig.symlink`
- **Ignore patterns**: Maintain in `git/gitignore.symlink`

## Project Structure

```
dotfiles/
├── install                    # Main installation script (runs Dotbot)
├── install.conf.yaml          # Dotbot configuration - defines symlinks
├── dotbot/                    # Git submodule - DO NOT MODIFY
├── zsh/                       # Zsh shell configuration
│   ├── zshrc.symlink         # Main zsh config
│   ├── zshenv.symlink        # Environment variables
│   ├── zprofile.symlink      # Login shell config
│   ├── themes/               # Git submodules (powerlevel9k)
│   └── plugins/              # Git submodules (autosuggestions, syntax-highlighting)
├── git/                       # Git configuration
├── vim/                       # Vim configuration
├── homebrew/                  # macOS Homebrew setup scripts
├── mackup/                    # macOS app settings backup/restore
├── ssh/                       # SSH configuration
├── gpg/                       # GPG configuration
├── conda/                     # Conda configuration
├── hg/                        # Mercurial configuration
└── pypi/                      # PyPI configuration
```

## Git Submodules

**Important**: These are external dependencies - do not modify their code:
- `dotbot/` - Symlink management tool
- `zsh/themes/powerlevel9k/` - Zsh theme
- `zsh/plugins/zsh-autosuggestions/` - Zsh auto-suggestions
- `zsh/plugins/zsh-syntax-highlighting/` - Zsh syntax highlighting

**Managing submodules:**
```bash
# Initialize all submodules
git submodule update --init --recursive

# Update submodules to latest remote commits
git submodule update --recursive --remote

# Sync submodule URLs after .gitmodules changes
git submodule sync --recursive
```

## Common Tasks

### Adding a New Dotfile:
1. Create the config file with `.symlink` extension in the appropriate directory
2. Add a link entry in `install.conf.yaml`:
   ```yaml
   - link:
       ~/.configfilename: directory/filename.symlink
   ```
3. Run `./install` to create the symlink
4. Test that the symlink works correctly

### Adding Machine-Specific Configuration:
1. Create a file with `.local.symlink` suffix (e.g., `gitconfig.local.symlink`)
2. Add to `install.conf.yaml` with `create: true` if the parent directory needs creation:
   ```yaml
   - link:
       ~/.gitconfig.local:
           create: true
           path: git/gitconfig.local.symlink
   ```
3. These files are gitignored and won't be committed

### Adding a New Zsh Plugin:
1. Add as git submodule: `git submodule add <url> zsh/plugins/plugin-name`
2. Source the plugin in `zsh/zshrc.symlink`
3. Run `./install` to update

### Modifying Zsh Configuration:
1. Edit files in `zsh/` with `.symlink` extension
2. Source the changes: `source ~/.zshrc` or open a new terminal
3. Keep changes minimal and well-commented

## Security Notes

- **Never commit secrets**: API keys, passwords, tokens should never be in this repo
- **Use .local files**: Store sensitive or machine-specific data in `.local` files (gitignored)
- **GPG keys**: Use `gpg/import.sh` and `gpg/export.sh` for key management
- **SSH keys**: Never commit SSH private keys; only commit `ssh/config.symlink` for configuration

## Installation Flow

1. Clone the repository
2. Run `./install` to set up all symlinks via Dotbot
3. Run `homebrew/install.sh` to set up Homebrew (macOS)
4. Run `cd mackup && make restore` to restore app settings (optional)
